# CyberLord AI setup (Gemini + Groq)

The CyberLord tutor and the main AI assistant answer through a provider chain: **Gemini (if `GEMINI_API_KEY` is set) -> Groq (if `GROQ_API_KEY` is set) -> built-in knowledge base**. The first configured key wins; on error or timeout (12s) the server silently moves to the next provider in the chain, and the built-in knowledge base is last. No key is stored in this repo. Do NOT paste a real key into any file here.

## Option 1: Gemini (primary, when configured)

1. Open Google AI Studio (aistudio.google.com) and create a free Gemini API key (no card required).
2. On Render, open the **CyberLord Domain Intelligence V2** service, go to **Environment**, and add:
   - Key: `GEMINI_API_KEY`
   - Value: your Gemini API key (never commit it to GitHub).
3. Optionally add `GEMINI_MODEL` to switch the model (default is `gemini-3.8-flash`). Leave it unset to use the default.
4. Save. Render redeploys. If Gemini errors or times out, the chain moves on automatically; nothing is shown to the user.

## Option 2: Groq (backup, when configured)

Groq exposes an OpenAI-compatible API. Whether your account has free usage, what models it can access, and any token charges or rate limits depend on Groq’s current account and model terms.

1. Go to Groq Console at https://console.groq.com and sign up and check the current plan, model access and billing terms shown in your account.
2. Create an API key in the dashboard and copy it.
3. On Render, open the **CyberLord Domain Intelligence V2** service, go to **Environment**, and add:
   - Key: `GROQ_API_KEY`
   - Value: your Groq API key (never commit it to GitHub).
4. Optionally add `GROQ_MODEL` to switch the model (default is `openai/gpt-oss-20b`). Leave it unset to use the default.
5. Save. Render redeploys. Groq is used only when Gemini is not configured or fails; if Groq also fails, the built-in knowledge base answers instead, with no user-visible fallback message.

## Where it sits in the chain

- Both the lesson tutor panels and the full-page `/tutor` dashboard call the server endpoint `/api/ai-assistant`.
- The server tries `GEMINI_API_KEY` first (Google Gemini API, `gemini-3.8-flash` by default, 12-second timeout).
- If Gemini is unset or fails, it tries `GROQ_API_KEY` second (OpenAI-compatible endpoint `https://api.groq.com/openai/v1/chat/completions`, `openai/gpt-oss-20b` by default, 12-second timeout).
- If both are unset or fail, the built-in knowledge base (`cyberlord_ai.py`) answers.
- Provider failures are logged server-side. The JSON response includes a `mode` value so you can distinguish Gemini, Groq and built-in fallback during testing.
- Keys never appear in browser JavaScript, templates or static files.

## Voice (no key needed)

The speaker ("Listen") buttons use the browser's built-in Web Speech API (`speechSynthesis`), which is free and works on phones and desktops. Where the browser does not support it, the buttons simply do not appear.


## Provider notes

- Current default Gemini model: `gemini-3.8-flash`. Confirm that this model is enabled for the Google AI Studio project that owns `GEMINI_API_KEY`.
- Current default Groq model: `openai/gpt-oss-20b`. Groq model availability, account access, rate limits and token charges are controlled by Groq; do not assume API inference is unlimited or free.
- Add both API keys as Render environment variables. Never commit real API keys or `.env` files to GitHub.
- The application tries Gemini first, then Groq, then its built-in knowledge base. A successful HTTP response from `/api/ai-assistant` can still be a built-in fallback; inspect the JSON `mode` field (`gemini`, `groq`, or `built-in-fallback`) to identify which path answered.


## Tutor Pro, Training Terminal and Code Lab

Tutor Pro is an add-on subscription that works alongside Free, PRO and PRO
PLUS. It does not replace the main plan.

- Price: NGN 6,300 per month, or 4.50 USDT (same price as PRO) (USDT wallet address and network
  are shown on the payment page, same as PRO / PRO PLUS).
- Duration: 30 days from manual verification (`activate_subscription` sets
  `tutor_pro_expires_at`; the main `plan` is left untouched).
- Includes: unlimited tutor questions, voice tutor UI, and Code Lab access.
- Free tutor limit: 10 questions per day. The limit is counted in the
  `tutor_usage` table (one row per tutor question, UTC day).
- Manual payment verification flow is unchanged: users submit a payment
  reference, an admin verifies it, and only then is Tutor Pro activated.

### Training Terminal (`/academy/terminal`)

A Kali-dark simulated terminal for the academy. It is a strict whitelist
executor: no shell, no subprocess, no real network and no real filesystem.
Commands are answered from a fixed in-memory practice-lab model. Allowed
commands: help, nmap, dig, whois, ping, ls, cd, cat, pwd, echo, clear and
theharvester (simulated, fictional output). Only the built-in lab host
`lab.local` can be named; any other target is refused. Shell operators
(;, &, |, >, <, backticks, $, parentheses) are rejected outright.

### Code Lab (`/code-lab`, Tutor Pro only)

Learners paste small Python snippets (max 4,000 characters). Snippets run in
a child process (`python -I -c`) with:

- 5 second timeout, CPU and memory rlimits, read-only file size limit.
- Working directory is a fresh temp dir, deleted after the run.
- AST screen blocks forbidden imports (os, sys, subprocess, socket, ctypes,
  importlib, pathlib, shutil, requests, urllib, http, multiprocessing, pty,
  threading, inspect, runpy, webbrowser, builtins, code, codeop, pkgutil)
  and forbidden names/attributes (system, popen, exec, eval, open, compile,
  __import__, fork, spawn, execv, execve, kill, remove, unlink, rmdir,
  mkdir, rename, chmod, chown, symlink, link, urlopen, getattr, and any
  dunder attribute).
- The child also installs a blocked-import guard and disables socket,
  open, eval, exec and compile at runtime as defence in depth.

This is an educational sandbox for practice, not a security boundary for
untrusted code. Keep snippets small and keep the timeouts.


## Image understanding, generation and web pictures

The Dashboard AI, full-page Academy Tutor and lesson tutor panels accept JPG,
PNG and WEBP uploads (up to 25 MB per original image, up to four images per
message). The browser resizes large images and the server normalizes them before
sending them to the vision model. For accurate image analysis, CyberLord uses a
vision-specific Gemini model (`GEMINI_VISION_MODEL`, default `gemini-3.8-flash`)
and an explicit image-grounding instruction that tells the model to describe only
visible evidence, identify uncertainty, and never invent unreadable text. Image bytes are processed for the request
and are not written into the messaging conversation-history table.

Image generation and reference-image editing use Gemini's image model:
- `GEMINI_IMAGE_MODEL` (default: `gemini-3.1-flash-image`)
- `GEMINI_API_KEY` (required)

Users request images and edits naturally in the normal chat input; there is no
separate Generate/Edit button. Generated images are returned to the chat as image
data and are not stored permanently by this feature.

The Dashboard AI and Tutor retrieve public pictures through Wikimedia and
Openverse search. Search results can have different licenses and source terms;
check the linked source before reusing an image commercially. The Tutor can use
Google Search grounding when a learner asks for current information, official
documentation, or online research.

### Messaging image support

Telegram and WhatsApp Cloud API webhook adapters can accept image messages,
download supported media from the platform, and pass it to the same Gemini
vision-capable AI endpoint. A message beginning with `/image`, `generate an
image of`, or `create an image of` requests image generation; an attached image
can be included as a reference for editing. Generated pictures are sent back
using Telegram `sendPhoto` or WhatsApp Cloud API media upload/send.

Image understanding requires `GEMINI_API_KEY` with access to the configured
vision model. Set `GEMINI_VISION_MODEL` to another vision-capable Gemini model if
needed. Image generation can use Gemini first and Cloudflare Workers AI as a
fallback. No provider key is exposed to browser JavaScript.


## Natural image creation from AI answers (latest update)

The Dashboard AI, full-page Tutor, lesson Tutor, WhatsApp and Telegram no longer require a separate Create/Edit button. Users can ask naturally for an image, diagram, infographic or visual in the same message box. The assistant answers first, then the image-generation step uses the actual AI answer as source material for the requested visual. Requests for multiple images/variations are supported up to four images per message to control provider quota. A picture attachment is still analysed normally; it is used as an edit reference only when the user explicitly asks to change or transform it.

Examples: “Explain the TCP handshake with a diagram”, “Turn your explanation into an infographic”, “Create four different logo concepts based on your answer”. Image generation still requires `GEMINI_API_KEY` and an enabled Gemini image model.


## Smart media creation: images, videos and files

CyberLord now routes ordinary natural-language requests through the same AI answer and then creates the requested media from that answer:

- **Find images:** the assistant searches Wikipedia/Wikimedia thumbnails first and broadens to Openverse results when needed. The result cards link to the source; availability and reuse rights depend on each source's license.
- **Create/edit images:** Gemini image generation is used for original images and edits. Requests for multiple variations are supported, with a per-message cap of four images.
- **Create files:** the assistant can make downloadable PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), CSV, Markdown and text files from its answer.
- **Create videos:** short video generation uses Gemini Omni on Google Cloud Vertex AI. This is optional and requires a Google Cloud project with the Vertex AI API enabled, billing enabled, and a service account granted the **Vertex AI User** role.

### Video generation environment variables

Add these in Render → your service → Environment. Do not put service-account JSON in GitHub or in chat.

- `GOOGLE_CLOUD_PROJECT` — your Google Cloud project ID.
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` — the complete service-account JSON key, stored as a secret environment variable.
- `GEMINI_VIDEO_MODEL` — optional; defaults to `gemini-omni-1.2-flash`.
- `GEMINI_VIDEO_DURATION_SECONDS` — optional; defaults to 5 seconds and is capped to 3–15 seconds.

The implementation requests a 720p, 16:9 MP4. Video generation can take several minutes and may incur Google Cloud charges. Model access, regional availability, quotas, safety rules and billing still apply. Without the Google Cloud variables, CyberLord will answer normally and explain that video generation is not configured; it will not pretend a video was created.

Document formats use the Python packages listed in `requirements.txt`. Redeploy after updating dependencies. Large video/file payloads can increase response size and request duration.


## Large image reading update

CyberLord accepts JPG, PNG and WEBP image uploads up to 25 MB each in the web chat. The browser resizes/re-encodes each image before sending it to the AI, and the server validates and normalizes incoming images. Up to four images can be attached in one message. Messaging platforms still enforce their own media download limits, so WhatsApp and Telegram availability depends on the provider and Bot API limits.


## Free/low-cost media provider fallback

### Cloudflare Workers AI image generation

CyberLord can generate text-to-image pictures with Cloudflare Workers AI when
Gemini image generation is unavailable or not configured. Configure these Render
Environment variables (never commit tokens to GitHub):

- `CLOUDFLARE_ACCOUNT_ID` — your Cloudflare account ID.
- `CLOUDFLARE_API_TOKEN` — a token with Account / Workers AI / Read permission.
- `CLOUDFLARE_IMAGE_MODEL` — optional; defaults to `@cf/black-forest-labs/flux-1-schnell`.

Cloudflare documents a 10,000-Neuron daily free allocation on Workers AI Free;
usage depends on model and image settings, and requests can stop after the daily
allowance is exhausted. It is a limited free allowance, not unlimited free use.
The Cloudflare fallback currently generates images from text; reference-image
editing still requires Gemini image generation. See Cloudflare's current pricing
and model documentation before enabling it.

### Free online picture sources

Picture lookup combines Wikipedia/Wikimedia and Openverse results. Results link
to the original landing page and may have different Creative Commons or other
licenses. Users should check attribution and reuse rights before publishing.

### Video generation reality

There is no dependable unlimited free hosted video-generation API. The current
Google Cloud Vertex AI video adapter remains optional and can incur charges. For
a self-hosted open-source route, Wan2.1 provides text-to-video and image-to-video
models, but it requires a compatible GPU and local/hosted GPU infrastructure; it
will not run on an ordinary Render web service without a separate GPU worker.
Do not advertise stock-video search or YouTube playback as AI video generation.
