"""Agnes Video 2.5 Flash async generation shared by CyberLord channels.

The API key is read only from the server environment. Jobs are held in-process;
Render's web service should run one Gunicorn worker unless a shared job store is added.
"""
from __future__ import annotations

import base64
import os
import threading
import time
import uuid
from typing import Any

import requests

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()


def _base_url() -> str:
    return os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com").strip().rstrip("/")


def _model() -> str:
    return os.getenv("AGNES_VIDEO_MODEL", "agnes-video-2.5-flash").strip() or "agnes-video-2.5-flash"


def _duration() -> str:
    try:
        value = int(os.getenv("AGNES_VIDEO_DURATION_SECONDS", "5"))
    except (TypeError, ValueError):
        value = 5
    return str(max(4, min(12, value)))


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
        # Never expose API keys, raw video bytes, or provider internals.
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
        _set(job_id, status="failed", progress=100, error="Video generation is not configured. Add AGNES_API_KEY in Render Environment.")
        return

    model = _model()
    duration = _duration()
    clean_prompt = str(prompt or "").strip()[:4000]
    if not clean_prompt:
        _set(job_id, status="failed", progress=100, error="Please describe the video you want to create.")
        return

    payload: dict[str, Any] = {
        "model": model,
        "prompt": clean_prompt,
        "mode": "img2video" if image else "text",
        "seconds": duration,
        "size": "720P",
        "aspect_ratio": os.getenv("AGNES_VIDEO_ASPECT_RATIO", "16:9").strip(),
        "n": 1,
    }
    if image:
        mime = image.get("mime_type", "image/jpeg")
        data = image.get("data", "")
        if mime not in ("image/jpeg", "image/png", "image/webp") or not data:
            _set(job_id, status="failed", progress=100, error="The attached image could not be used. Please upload a JPG, PNG or WEBP image.")
            return
        payload["first_frame"] = "data:%s;base64,%s" % (mime, data)

    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    try:
        _set(job_id, status="submitting", progress=8, message="Submitting your video request to Agnes…")
        response = requests.post(_base_url() + "/v1/videos", headers=headers, json=payload, timeout=(15, 90))
        if not response.ok:
            try:
                detail = (response.json().get("error") or {}).get("message") or response.text
            except Exception:
                detail = response.text
            raise RuntimeError("Agnes rejected the video request (HTTP %s): %s" % (response.status_code, str(detail)[:350]))
        created = response.json()
        video_id = created.get("video_id") or created.get("id") or created.get("task_id")
        if not video_id:
            raise RuntimeError("Agnes accepted the request but did not return a video task ID.")
        _set(job_id, status="processing", progress=15, provider_task_id=str(video_id), message="Agnes is generating your video…")

        deadline = time.time() + int(os.getenv("AGNES_VIDEO_TIMEOUT_SECONDS", "720"))
        poll_delay = 2
        result = None
        while time.time() < deadline:
            time.sleep(poll_delay)
            poll = requests.get(
                _base_url() + "/agnesapi",
                headers={"Authorization": "Bearer " + api_key},
                params={"video_id": str(video_id), "model_name": model},
                timeout=(15, 45),
            )
            if poll.status_code == 429:
                poll_delay = min(15, poll_delay * 2)
                continue
            if poll.status_code in (408, 500, 502, 503, 504):
                poll_delay = min(15, poll_delay * 2)
                continue
            poll.raise_for_status()
            result = poll.json()
            state = str(result.get("status") or (result.get("data") or {}).get("status") or "processing").lower()
            if state in ("failed", "error", "cancelled", "canceled"):
                detail = result.get("error") or result.get("message") or "Agnes could not complete this video."
                raise RuntimeError(str(detail)[:350])
            if state in ("completed", "complete", "succeeded", "success"):
                break
            with _LOCK:
                old = _JOBS.get(job_id, {}).get("progress", 15)
            _set(job_id, status="processing", progress=min(92, old + 3), message="Agnes is rendering your video…")
            poll_delay = min(8, max(2, poll_delay))
        else:
            raise TimeoutError("Agnes is taking longer than expected. Please try again later.")

        provider_url = (result or {}).get("url") or ((result or {}).get("metadata") or {}).get("url")
        if not provider_url:
            data = (result or {}).get("data") or {}
            provider_url = data.get("url") or (data.get("metadata") or {}).get("url")
        if not provider_url or not str(provider_url).startswith("https://"):
            raise RuntimeError("Agnes marked the task complete but did not return a valid video URL.")
        _set(job_id, status="downloading", progress=96, message="Preparing your video for preview and download…", provider_url=provider_url)
        media = requests.get(provider_url, timeout=(20, 180))
        media.raise_for_status()
        if not media.content or len(media.content) > int(os.getenv("AGNES_VIDEO_MAX_BYTES", str(150 * 1024 * 1024))):
            raise RuntimeError("The generated video is empty or exceeds CyberLord's configured download limit.")
        mime = media.headers.get("Content-Type", "video/mp4").split(";")[0].strip().lower()
        if not mime.startswith("video/"):
            mime = "video/mp4"
        _set(job_id, status="completed", progress=100, message="Your video is ready.", video_bytes=media.content,
             mime_type=mime, filename="cyberlord-generated-video.mp4", provider_url=None)
    except Exception as exc:
        message = str(exc)
        # Avoid accidentally echoing request headers or credentials in logs/status.
        _set(job_id, status="failed", progress=100, error=message[:450], message="Video generation failed.")


def start_video_job(prompt: str, owner_id: str | None = None, image: dict[str, str] | None = None) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id, "owner_id": str(owner_id) if owner_id is not None else None,
            "status": "queued", "progress": 2, "message": "Your video request is queued…",
            "created_at": time.time(), "updated_at": time.time(), "filename": "cyberlord-generated-video.mp4",
        }
    thread = threading.Thread(target=_run_job, args=(job_id, prompt, image), daemon=True, name="agnes-video-" + job_id[:8])
    thread.start()
    return job_id
