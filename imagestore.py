"""Image generation + private upload helpers for CyberLord.

Pure module (no Flask / DB) so it can be unit tested:
- sanitize_upload(): size/type checks, decode, EXIF-orient, re-encode (strips all metadata)
- ObjectStorage: S3-compatible external storage (Cloudflare R2, Backblaze B2, AWS S3, ...)
- providers: ImageProvider interface, GeminiImageProvider (+ registry for adding a dedicated one)
Nothing here guesses endpoints: model names / bucket settings come from env vars.
"""
import base64
import os
import secrets
from io import BytesIO

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = int(os.getenv("IMAGE_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_PIXELS = 25_000_000
MAX_SIDE = 4096
ALLOWED_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow raises DecompressionBombError above 2x this


class ImageError(Exception):
    """User-safe error message."""


def sanitize_upload(raw, max_bytes=None):
    """Return (clean_bytes, mime, ext, width, height). Raises ImageError.

    Type is decided from the decoded content, never the filename or client MIME.
    Re-encoding from pixels drops EXIF/GPS/ICC/XMP/comments and any appended payload.
    """
    max_bytes = max_bytes or MAX_UPLOAD_BYTES
    if not raw:
        raise ImageError("No file received.")
    if len(raw) > max_bytes:
        raise ImageError("File is too large (max %d MB)." % (max_bytes // (1024 * 1024)))
    try:
        probe = Image.open(BytesIO(raw))
        fmt = probe.format
        probe.verify()
        img = Image.open(BytesIO(raw))
        if fmt not in ALLOWED_FORMATS:
            raise ImageError("Only JPEG, PNG or WebP images are allowed.")
        if getattr(img, "is_animated", False):
            img.seek(0)
        img.load()
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ImageError("That file is not a valid image.")
    if img.width * img.height > MAX_PIXELS:
        raise ImageError("Image dimensions are too large.")
    img = ImageOps.exif_transpose(img)
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    mime, ext = ALLOWED_FORMATS[fmt]
    out = BytesIO()
    if fmt == "JPEG":
        clean = Image.new("RGB", img.size)
        clean.paste(img.convert("RGB"))
        clean.save(out, "JPEG", quality=90, optimize=True)
    elif fmt == "PNG":
        mode = "RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB"
        clean = Image.new(mode, img.size)
        clean.paste(img.convert(mode))
        clean.save(out, "PNG", optimize=True)
    else:
        clean = Image.new("RGBA", img.size)
        clean.paste(img.convert("RGBA"))
        clean.save(out, "WEBP", quality=90)
    data = out.getvalue()
    if len(data) > max_bytes * 2:
        raise ImageError("Image is too large after processing.")
    return data, mime, ext, clean.width, clean.height


def new_object_key(user_id, ext):
    """Unguessable key namespaced by user. Never built from user input."""
    return "u%d/%s.%s" % (int(user_id), secrets.token_urlsafe(24), ext)


# ---------------- storage ----------------
class ObjectStorage:
    """S3-compatible storage. Env: IMAGE_S3_BUCKET, IMAGE_S3_ACCESS_KEY_ID,
    IMAGE_S3_SECRET_ACCESS_KEY, optional IMAGE_S3_ENDPOINT_URL (R2/B2/etc), IMAGE_S3_REGION.
    Bucket must stay PRIVATE; the app streams images to their owner only."""

    def __init__(self, client=None, bucket=None):
        self.bucket = bucket or os.getenv("IMAGE_S3_BUCKET", "").strip()
        self._client = client

    @staticmethod
    def configured():
        return all(os.getenv(k, "").strip() for k in ("IMAGE_S3_BUCKET", "IMAGE_S3_ACCESS_KEY_ID", "IMAGE_S3_SECRET_ACCESS_KEY"))

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=os.getenv("IMAGE_S3_ENDPOINT_URL", "").strip() or None,
                region_name=os.getenv("IMAGE_S3_REGION", "").strip() or "auto",
                aws_access_key_id=os.getenv("IMAGE_S3_ACCESS_KEY_ID", "").strip(),
                aws_secret_access_key=os.getenv("IMAGE_S3_SECRET_ACCESS_KEY", "").strip(),
                config=Config(signature_version="s3v4", retries={"max_attempts": 3}, connect_timeout=5, read_timeout=20),
            )
        return self._client

    def put(self, key, data, mime):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime, CacheControl="private, max-age=0")

    def get(self, key):
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)


class MemoryStorage:
    """Test double with the same interface."""
    def __init__(self):
        self.items = {}
    def put(self, key, data, mime): self.items[key] = (data, mime)
    def get(self, key): return self.items[key]
    def delete(self, key): self.items.pop(key, None)


# ---------------- providers ----------------
class ImageProvider:
    name = ""
    def available(self): raise NotImplementedError
    def generate(self, prompt):
        """Return raw image bytes. Raise ImageError with a user-safe message."""
        raise NotImplementedError


class GeminiImageProvider(ImageProvider):
    """Uses the same generateContent endpoint the site already uses for text.
    The image-capable model id is NOT hardcoded: set GEMINI_IMAGE_MODEL.
    Request/response shape (responseModalities + inlineData) is from Google's
    documented generateContent image output; verify against current docs before deploy."""
    name = "gemini"

    def available(self):
        return bool(os.getenv("GEMINI_API_KEY", "").strip() and os.getenv("GEMINI_IMAGE_MODEL", "").strip())

    def generate(self, prompt):
        key = os.getenv("GEMINI_API_KEY", "").strip()
        model = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
                headers={"Content-Type": "application/json", "x-goog-api-key": key},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
                timeout=(8, 90))
            r.raise_for_status()
            for cand in r.json().get("candidates") or []:
                for part in (cand.get("content") or {}).get("parts") or []:
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])
        except requests.RequestException:
            raise ImageError("The image service is unavailable right now. Try again shortly.")
        except (ValueError, KeyError):
            raise ImageError("The image service returned an unreadable response.")
        raise ImageError("No image was produced for that prompt. Try rewording it.")


class DedicatedProviderStub(ImageProvider):
    """Slot for the second provider. Not implemented on purpose: its endpoint/model/auth
    were not verified (research allowance exhausted). Implement generate() once confirmed,
    set IMAGE_PROVIDER_ORDER=gemini,dedicated and the matching key env var."""
    name = "dedicated"
    def available(self): return False
    def generate(self, prompt): raise ImageError("Provider not configured.")


PROVIDERS = {"gemini": GeminiImageProvider, "dedicated": DedicatedProviderStub}


def generate_image(prompt, providers=None):
    """Try providers in IMAGE_PROVIDER_ORDER (default gemini). Returns (bytes, provider_name)."""
    if providers is None:
        order = [p.strip() for p in os.getenv("IMAGE_PROVIDER_ORDER", "gemini").split(",") if p.strip()]
        providers = [PROVIDERS[n]() for n in order if n in PROVIDERS]
    last = None
    for p in providers:
        if not p.available():
            continue
        try:
            return p.generate(prompt), p.name
        except ImageError as e:
            last = e
    raise last or ImageError("Image generation is not configured yet.")
