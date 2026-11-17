"""CyberLord Super Mode helpers: safe document extraction and optional YouTube tools."""
import io, os, re, csv, json, zipfile
from urllib.parse import urlparse, parse_qs
import requests

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_CHARS = 100000
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"}


def extract_document(filename, raw):
    name = os.path.basename(str(filename or "upload"))
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Supported files: PDF, DOCX, XLSX, PPTX, TXT, MD and CSV.")
    if not raw or len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Each document must be between 1 byte and 50 MB.")
    text = ""
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 80:
                raise ValueError("PDFs are limited to 80 pages per upload.")
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            if not text.strip():
                raise ValueError("This PDF has no extractable text. Scanned PDFs need OCR before they can be analysed.")
        except ImportError:
            raise ValueError("PDF reading is not installed on this deployment yet. Redeploy after installing pypdf.")
    elif ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
        for table in doc.tables:
            text += "\n" + "\n".join(" | ".join(c.text for c in row.cells) for row in table.rows)
    elif ext == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        chunks = []
        for ws in wb.worksheets[:12]:
            chunks.append("[Sheet: %s]" % ws.title)
            for row in ws.iter_rows(max_row=500, values_only=True):
                vals = [str(v) if v is not None else "" for v in row]
                if any(vals): chunks.append(" | ".join(vals))
        text = "\n".join(chunks)
    elif ext == ".pptx":
        from pptx import Presentation
        prs = Presentation(io.BytesIO(raw))
        chunks = []
        for i, slide in enumerate(prs.slides[:100], 1):
            chunks.append("[Slide %d]" % i)
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text.strip(): chunks.append(shape.text)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows: chunks.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(chunks)
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    text = re.sub(r"\x00", "", text).strip()
    if not text:
        raise ValueError("No readable text was found in this file.")
    return {"filename": name[:120], "text": text[:MAX_EXTRACTED_CHARS], "truncated": len(text) > MAX_EXTRACTED_CHARS}


def youtube_video_id(value):
    value = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value): return value
    try:
        u = urlparse(value)
        if u.hostname in ("youtu.be", "www.youtu.be"): return u.path.strip("/")[:11]
        if u.hostname and (u.hostname.endswith("youtube.com") or u.hostname.endswith("youtube-nocookie.com")):
            if u.path == "/watch": return parse_qs(u.query).get("v", [""])[0][:11]
            if u.path.startswith(("/embed/", "/shorts/")): return u.path.split("/")[2][:11]
    except Exception: pass
    return ""


def youtube_search(query, limit=6):
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key: return {"configured": False, "items": [], "message": "YouTube search needs YOUTUBE_API_KEY in Render Environment."}
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
        "part": "snippet", "type": "video", "maxResults": max(1, min(int(limit), 10)),
        "q": str(query or "")[:180], "key": key
    }, timeout=12)
    r.raise_for_status()
    items = []
    for row in r.json().get("items", []):
        vid = (row.get("id") or {}).get("videoId")
        sn = row.get("snippet") or {}
        if vid:
            items.append({"video_id": vid, "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                          "description": (sn.get("description") or "")[:500],
                          "published_at": sn.get("publishedAt", ""),
                          "url": "https://www.youtube.com/watch?v=" + vid,
                          "thumbnail": "https://i.ytimg.com/vi/" + vid + "/hqdefault.jpg"})
    return {"configured": True, "items": items}


def youtube_transcript(video_url):
    vid = youtube_video_id(video_url)
    if not vid: raise ValueError("Enter a valid YouTube video URL.")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = api.fetch(vid)
        lines = []
        for item in transcript:
            text = getattr(item, "text", None) or (item.get("text") if isinstance(item, dict) else "")
            if text: lines.append(str(text))
        result = " ".join(lines).strip()
        if not result: raise ValueError("No transcript text was returned for this video.")
        return {"video_id": vid, "url": "https://www.youtube.com/watch?v=" + vid, "transcript": result[:MAX_EXTRACTED_CHARS], "truncated": len(result) > MAX_EXTRACTED_CHARS}
    except ImportError:
        raise ValueError("YouTube transcript support is not installed. Install youtube-transcript-api to enable it.")
    except Exception as exc:
        if isinstance(exc, ValueError): raise
        raise ValueError("A transcript is unavailable for this video, or YouTube blocked the transcript request.")


def build_agent_plan(goal):
    goal = re.sub(r"\s+", " ", str(goal or "")).strip()[:1200]
    if not goal: raise ValueError("Describe what you want CyberLord to accomplish.")
    # Planning only: never executes account, payment, publishing, scanning or external actions.
    steps = [
        {"step": 1, "title": "Understand the goal", "detail": "Clarify the requested outcome, constraints and success criteria."},
        {"step": 2, "title": "Gather information", "detail": "Use only relevant connected tools, public sources or files supplied for this task."},
        {"step": 3, "title": "Prepare the work", "detail": "Draft the analysis, content or files and check them for completeness."},
        {"step": 4, "title": "Review before action", "detail": "Show the result and request approval before any external, destructive, financial or account-changing action."}
    ]
    risk = "approval_required" if re.search(r"pay|purchase|delete|send|publish|post|message|email|scan|attack|exploit|change account|password|deploy|commit", goal, re.I) else "review_recommended"
    return {"goal": goal, "steps": steps, "risk": risk, "requires_approval_before_external_action": True,
            "execution_status": "planning_only", "notice": "This plan has not executed any action."}
