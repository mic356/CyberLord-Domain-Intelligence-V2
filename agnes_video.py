"""Agnes Video 2.5 async generation for CyberLord.

The API key is read only from AGNES_API_KEY in the server environment.
Jobs are process-local; keep a single Gunicorn worker unless a shared job store
is configured. Logs deliberately omit prompts, credentials, and media contents.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Any

import requests

_LOG = logging.getLogger("cyberlord.agnes")
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()


def _base_url() -> str:
    value = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com").strip().rstrip("/")
    # Accept either the host root or the documented /v1 base without duplicating it.
    if value.endswith("/v1"):
        value = value[:-3]
    return value


def _model() -> str:
    return os.getenv("AGNES_VIDEO_MODEL", "agnes-video-2.5-flash").strip() or "agnes-video-2.5-flash"


def _duration() -> str:
    try:
        value = int(os.getenv("AGNES_VIDEO_DURATION_SECONDS", "5"))
    except (TypeError, ValueError):
        value = 5
    return str(max(4, min(12, value)))


def _payload_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("data")
    return nested if isinstance(nested, dict) else value


def _error_text(data: Any, fallback: str) -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            detail = err.get("message") or err.get("detail")
        else:
            detail = err
        detail = detail or data.get("message") or data.get("detail")
        if detail:
            return str(detail)[:350]
    return fallback


def _set(job_id: str, **values: Any) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(values)
            _JOBS[job_id]["updated_at"] = time.time()


def get_job(job_id: str, owner_id: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job or (owner_id is not None and job.get("owner_id") != str(owner_id)):
            return None
        return {k: v for k, v in job.items() if k not in ("video_bytes", "owner_id", "provider_url")}


def wait_for_job(job_id: str, timeout: int | None = None) -> dict[str, Any] | None:
    deadline = time.time() + (timeout or int(os.getenv("AGNES_VIDEO_TIMEOUT_SECONDS", "720")))
    while time.time() < deadline:
        with _LOCK:
            job = _JOBS.get(job_id)
            if not job:
                return None
            snapshot = dict(job)
        if snapshot.get("status") in ("completed", "failed"):
            return snapshot
        time.sleep(2)
    return get_job(job_id)


def video_bytes(job_id: str) -> tuple[bytes, str, str] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job or job.get("status") != "completed" or not job.get("video_bytes"):
            return None
        return job["video_bytes"], job.get("mime_type", "video/mp4"), job.get("filename", "cyberlord-video.mp4")


def _run_job(job_id: str, prompt: str, image: dict[str, str] | None) -> None:
    api_key = os.getenv("AGNES_API_KEY", "").strip()
    if not api_key:
        message = "Video generation is not configured. Add AGNES_API_KEY in Render Environment and redeploy."
        _LOG.error("job=%s failed: AGNES_API_KEY is not configured", job_id[:8])
        _set(job_id, status="failed", progress=100, error=message, message="Video generation is not configured.")
        return

    model = _model()
    duration = _duration()
    clean_prompt = str(prompt or "").strip()[:4000]
    if not clean_prompt:
        _set(job_id, status="failed", progress=100, error="Please describe the video you want to create.")
        return
    if model not in ("agnes-video-2.5-flash", "agnes-video-2.5"):
        _set(job_id, status="failed", progress=100, error="AGNES_VIDEO_MODEL must be agnes-video-2.5-flash or agnes-video-2.5.")
        _LOG.error("job=%s failed: unsupported configured model=%s", job_id[:8], model)
        return

    payload: dict[str, Any] = {
        "model": model,
        "prompt": clean_prompt,
        "mode": "img2video" if image else "text",
        "seconds": duration,
        "size": "720P",
        "aspect_ratio": os.getenv("AGNES_VIDEO_ASPECT_RATIO", "16:9").strip() or "16:9",
        "n": 1,
    }
    if image:
        mime = image.get("mime_type", "image/jpeg")
        data = image.get("data", "")
        if mime not in ("image/jpeg", "image/png", "image/webp") or not data:
            _set(job_id, status="failed", progress=100, error="Use a JPG, PNG or WEBP image for image-to-video.")
            return
        payload["first_frame"] = "data:%s;base64,%s" % (mime, data)

    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    base = _base_url()
    _LOG.info("job=%s starting model=%s mode=%s duration=%ss base=%s", job_id[:8], model, payload["mode"], duration, base)
    try:
        _set(job_id, status="submitting", progress=8, message="Building your video now…")
        # Agnes can temporarily reject new jobs when its generation queue is full.
        # Retry only this explicit provider response; do not retry ambiguous network
        # failures because the provider may already have accepted those requests.
        queue_retry_delays = (30, 60, 120, 240, 480, 600)  # six retries over about 25 minutes
        for retry_index in range(len(queue_retry_delays) + 1):
            response = requests.post(base + "/v1/videos", headers=headers, json=payload, timeout=(15, 90))
            try:
                created_json = response.json()
            except ValueError:
                created_json = {}

            error_obj = created_json.get("error") if isinstance(created_json, dict) else None
            error_code = (created_json.get("code") if isinstance(created_json, dict) else None)
            if isinstance(error_obj, dict):
                error_code = error_obj.get("code") or error_code
            is_queue_full = str(error_code or "").lower() == "video_queue_full"

            if response.ok:
                break
            if is_queue_full and retry_index < len(queue_retry_delays):
                delay = queue_retry_delays[retry_index]
                next_attempt = retry_index + 2
                _LOG.warning(
                    "job=%s Agnes queue is full; retrying submission attempt=%s/%s in=%ss",
                    job_id[:8], next_attempt, len(queue_retry_delays) + 1, delay,
                )
                _set(
                    job_id,
                    status="retrying",
                    progress=5,
                    message="Building your video now. the free video service is busy, so CyberLord is retrying automatically (attempt %s of %s)…" % (next_attempt, len(queue_retry_delays) + 1),
                )
                time.sleep(delay)
                continue
            detail = _error_text(created_json, response.text or "No error details returned.")
            if is_queue_full:
                raise RuntimeError("Agnes video queue is still full after 6 retries. Your request could not be started; please retry later.")
            raise RuntimeError("Agnes rejected the request (HTTP %s): %s" % (response.status_code, detail[:250]))
        else:
            raise RuntimeError("Agnes could not accept the video request after automatic retries. Please try again later.")
        created = _payload_object(created_json)
        video_id = created.get("video_id") or created.get("id") or created.get("task_id")
        if not video_id:
            raise RuntimeError("Agnes returned HTTP %s but no video_id/task ID. Check Render logs for the response summary." % response.status_code)
        _LOG.info("job=%s submitted successfully provider_task=%s", job_id[:8], str(video_id)[:80])
        _set(job_id, status="processing", progress=15, provider_task_id=str(video_id), message="Building your video…")

        deadline = time.time() + int(os.getenv("AGNES_VIDEO_TIMEOUT_SECONDS", "720"))
        poll_delay = 3
        result: dict[str, Any] = {}
        last_state = "queued"
        while time.time() < deadline:
            time.sleep(poll_delay)
            poll = requests.get(
                base + "/agnesapi",
                headers={"Authorization": "Bearer " + api_key},
                params={"video_id": str(video_id), "model_name": model},
                timeout=(15, 45),
            )
            if poll.status_code == 429 or poll.status_code in (408, 500, 502, 503, 504):
                _LOG.warning("job=%s poll transient HTTP %s; retrying", job_id[:8], poll.status_code)
                poll_delay = min(15, poll_delay * 2)
                continue
            try:
                poll_json = poll.json()
            except ValueError:
                poll_json = {}
            if not poll.ok:
                raise RuntimeError("Agnes status check failed (HTTP %s): %s" % (poll.status_code, _error_text(poll_json, poll.text[:200])))
            result = _payload_object(poll_json)
            state = str(result.get("status") or "processing").lower()
            if state != last_state:
                _LOG.info("job=%s provider_status=%s", job_id[:8], state)
                last_state = state
            if state in ("failed", "error", "cancelled", "canceled"):
                raise RuntimeError(_error_text(result, "Agnes could not complete this video."))
            if state in ("completed", "complete", "succeeded", "success"):
                break
            with _LOCK:
                old = _JOBS.get(job_id, {}).get("progress", 15)
            _set(job_id, status="processing", progress=min(92, old + 3), message="Building your video…")
            poll_delay = min(8, max(3, poll_delay))
        else:
            raise TimeoutError("Agnes did not finish within the configured time. Check Render logs and try again later.")

        provider_url = result.get("url") or (result.get("metadata") or {}).get("url")
        if not provider_url or not str(provider_url).startswith("https://"):
            raise RuntimeError("The video service marked the task complete but did not return a valid HTTPS video URL.")
        _set(job_id, status="downloading", progress=96, message="Preparing your video for preview and download…")
        media = requests.get(provider_url, timeout=(20, 180))
        media.raise_for_status()
        max_bytes = int(os.getenv("AGNES_VIDEO_MAX_BYTES", str(150 * 1024 * 1024)))
        if not media.content or len(media.content) > max_bytes:
            raise RuntimeError("The generated video is empty or exceeds CyberLord's configured download limit.")
        mime = media.headers.get("Content-Type", "video/mp4").split(";")[0].strip().lower()
        if not mime.startswith("video/"):
            mime = "video/mp4"
        _set(job_id, status="completed", progress=100, message="Your video is ready.", video_bytes=media.content,
             mime_type=mime, filename="cyberlord-generated-video.mp4", provider_url=None)
        _LOG.info("job=%s completed; downloaded_bytes=%s", job_id[:8], len(media.content))
    except Exception as exc:
        message = str(exc)
        _set(job_id, status="failed", progress=100, error=message[:450], message="Video generation failed.")
        # Do not log request headers, API key, prompts, or response bodies wholesale.
        _LOG.exception("job=%s failed: %s", job_id[:8], message[:350])


def start_video_job(prompt: str, owner_id: str | None = None, image: dict[str, str] | None = None) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "owner_id": str(owner_id) if owner_id is not None else None,
            "status": "queued", "progress": 2,
            "message": "Your video request is queued…",
            "created_at": time.time(), "updated_at": time.time(),
            "filename": "cyberlord-generated-video.mp4",
        }
    thread = threading.Thread(target=_run_job, args=(job_id, prompt, image), daemon=True, name="agnes-video-" + job_id[:8])
    thread.start()
    _LOG.info("job=%s queued owner_authenticated=%s", job_id[:8], owner_id is not None)
    return job_id
