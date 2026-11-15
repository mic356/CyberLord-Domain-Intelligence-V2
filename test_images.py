import os, sys
from io import BytesIO
import pytest
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import imagestore as ims


def make(fmt="JPEG", size=(40, 30), exif=False):
    b = BytesIO(); im = Image.new("RGB", size, (200, 10, 10))
    kw = {}
    if exif:
        ex = Image.Exif(); ex[0x010F] = "SecretCam"; ex[0x8825] = {1: "N"}; kw["exif"] = ex
    im.save(b, fmt, **kw); return b.getvalue()


def test_strips_exif():
    raw = make(exif=True)
    assert b"SecretCam" in raw
    data, mime, ext, w, h = ims.sanitize_upload(raw)
    assert b"SecretCam" not in data and mime == "image/jpeg" and ext == "jpg" and (w, h) == (40, 30)
    assert not Image.open(BytesIO(data)).getexif()


def test_png_webp_ok():
    for f, m in (("PNG", "image/png"), ("WEBP", "image/webp")):
        assert ims.sanitize_upload(make(f))[1] == m


def test_rejects_non_image_and_disguised():
    for bad in (b"", b"<svg onload=alert(1)>", b"GIF89a" + b"0" * 50, b"%PDF-1.4 x"):
        with pytest.raises(ims.ImageError):
            ims.sanitize_upload(bad)


def test_rejects_gif_and_bmp():
    for f in ("GIF", "BMP"):
        with pytest.raises(ims.ImageError):
            ims.sanitize_upload(make(f))


def test_size_limit():
    with pytest.raises(ims.ImageError):
        ims.sanitize_upload(make(), max_bytes=100)


def test_trailing_payload_removed():
    data = ims.sanitize_upload(make() + b"<?php evil ?>")[0]
    assert b"evil" not in data


def test_key_namespaced_unique():
    a, b = ims.new_object_key(7, "png"), ims.new_object_key(7, "png")
    assert a != b and a.startswith("u7/") and a.endswith(".png")


class Fake(ims.ImageProvider):
    def __init__(self, name, ok, out=b"x"): self.name, self.ok, self.out = name, ok, out
    def available(self): return True
    def generate(self, p):
        if not self.ok: raise ims.ImageError("down")
        return self.out


def test_provider_fallback():
    assert ims.generate_image("a", [Fake("a", False), Fake("b", True, b"img")]) == (b"img", "b")
    with pytest.raises(ims.ImageError):
        ims.generate_image("a", [Fake("a", False)])
    with pytest.raises(ims.ImageError):
        ims.generate_image("a", [ims.DedicatedProviderStub()])


def test_gemini_needs_model_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    assert not ims.GeminiImageProvider().available()


def test_gemini_parses_inline(monkeypatch):
    import base64
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.setenv("GEMINI_IMAGE_MODEL", "m")
    class R:
        def raise_for_status(self): pass
        def json(self): return {"candidates": [{"content": {"parts": [{"text": "hi"}, {"inlineData": {"data": base64.b64encode(b"PNGDATA").decode()}}]}}]}
    monkeypatch.setattr(ims.requests, "post", lambda *a, **k: R())
    assert ims.GeminiImageProvider().generate("p") == b"PNGDATA"


def test_storage_roundtrip():
    s = ims.MemoryStorage(); s.put("k", b"d", "image/png"); assert s.get("k") == (b"d", "image/png"); s.delete("k"); assert "k" not in s.items


# ---- app-level: auth, privacy, daily limit ----
@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "t.db"))
    for k in ("IMAGE_S3_BUCKET", "IMAGE_S3_ACCESS_KEY_ID", "IMAGE_S3_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "x")
    import importlib, app as appmod
    importlib.reload(appmod)
    mem = ims.MemoryStorage(); appmod._image_storage = mem
    monkeypatch.setattr(ims, "generate_image", lambda p, providers=None: (make("PNG"), "fake"))
    appmod.app.config["TESTING"] = True
    with appmod.app.app_context():
        for n in ("a", "b"):
            u = appmod.User(email=n + "@x.com", password_hash="x"); appmod.db.session.add(u)
        appmod.db.session.commit()
    return appmod, mem


def login(c, uid):
    with c.session_transaction() as s:
        s["_user_id"] = str(uid); s["_fresh"] = True; s["image_csrf"] = "tok"


def test_requires_login(client):
    appmod, _ = client
    assert appmod.app.test_client().get("/images").status_code in (302, 401)


def test_csrf_enforced(client):
    appmod, _ = client; c = appmod.app.test_client(); login(c, 1)
    assert c.post("/images/generate", data={"prompt": "cat"}).status_code == 400


def test_generate_private_and_limit(client):
    appmod, mem = client; c = appmod.app.test_client(); login(c, 1)
    for _ in range(30):
        c.post("/images/generate", data={"prompt": "a cat", "csrf_token": "tok"})
    assert len(mem.items) == 30
    c.post("/images/generate", data={"prompt": "a cat", "csrf_token": "tok"})
    assert len(mem.items) == 30  # 31st blocked
    with appmod.app.app_context():
        first = appmod.UserImage.query.first().id
    other = appmod.app.test_client(); login(other, 2)
    assert other.get("/images/%d/file" % first).status_code == 404
    assert c.get("/images/%d/file" % first).status_code == 200


def test_paid_unlimited(client):
    appmod, mem = client
    with appmod.app.app_context():
        u = appmod.db.session.get(appmod.User, 1); u.plan = "pro"
        u.plan_expires_at = appmod.datetime.utcnow() + appmod.timedelta(days=5); appmod.db.session.commit()
    c = appmod.app.test_client(); login(c, 1)
    for _ in range(32):
        c.post("/images/generate", data={"prompt": "a cat", "csrf_token": "tok"})
    assert len(mem.items) == 32


def test_upload_and_delete(client):
    appmod, mem = client; c = appmod.app.test_client(); login(c, 1)
    r = c.post("/images/upload", data={"csrf_token": "tok", "photo": (BytesIO(make(exif=True)), "x.jpg")}, content_type="multipart/form-data")
    assert r.status_code == 302 and len(mem.items) == 1
    assert all(b"SecretCam" not in v[0] for v in mem.items.values())
    c.post("/images/upload", data={"csrf_token": "tok", "photo": (BytesIO(b"<html>"), "x.jpg")}, content_type="multipart/form-data")
    assert len(mem.items) == 1
    with appmod.app.app_context():
        iid = appmod.UserImage.query.first().id
    c.post("/images/%d/delete" % iid, data={"csrf_token": "tok"})
    assert len(mem.items) == 0
