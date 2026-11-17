# CyberLord Super Mode upgrade

This upgrade adds a unified Super Mode workspace to the existing CyberLord application. It is additive: existing dashboard, Academy, Tutor, scan tools, payments, user accounts, WhatsApp/Telegram webhook routes and monitoring files are retained.

## New workspace

Open **Super Mode** from the signed-in navigation at `/super-mode`.

- **Document understanding:** uploads PDF, DOCX, XLSX, PPTX, CSV, Markdown and TXT. Maximum 8 MB per file. Extracted text is passed to Gemini for analysis and is not written to a public file store. PDFs with selectable text are supported. Scanned/image-only PDFs need OCR and are not yet supported by this text-extraction path.
- **YouTube research:** search public video metadata with the YouTube Data API, or retrieve and summarize a transcript when the video has a transcript available. Search requires `YOUTUBE_API_KEY`. Transcript retrieval can fail if captions are disabled, unavailable, region-restricted or blocked by YouTube.
- **Voice notes:** browser recording uploads an audio note for Gemini transcription. Requires microphone permission, HTTPS and `GEMINI_API_KEY`. Supported MIME types are validated server-side; max 15 MB. Existing browser speech recognition and click-to-play speech synthesis remain available in Dashboard AI and Tutor.
- **Task agent:** creates a structured plan only. It does not execute external actions. Sending messages, publishing, payments, deleting, deploying, committing, changing accounts or other consequential actions must remain behind explicit approval and a separate authorized integration.
- **Readiness:** shows whether optional providers are configured. It is not a live guarantee of provider uptime, quota or permissions.

## Existing capabilities retained

- Gemini-first / Groq fallback AI provider chain.
- Google Search grounding for supported live research requests.
- Per-user memory and existing Academy learning/progress features.
- Image analysis, natural-language image generation/editing, Wikimedia/Openverse image discovery.
- Existing optional short video generation adapter (Google Cloud Vertex AI; can incur charges and requires its existing credentials).
- Downloadable PDF, DOCX, XLSX, PPTX, CSV, Markdown and TXT generation.
- Existing WhatsApp and Telegram adapters route messages through the shared CyberLord messaging processor. Linked-account requirements and provider webhook configuration still apply.
- Existing scheduled monitoring worker and monitoring UI.

## Render Environment variables

Keep secrets in Render → service → Environment. Never commit them to GitHub.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | AI reasoning, document analysis, audio transcription, vision and Gemini image features |
| `GEMINI_MODEL` | Optional text model override |
| `GEMINI_AUDIO_MODEL` | Optional audio-capable Gemini model override; defaults to `GEMINI_MODEL` |
| `GEMINI_TTS_MODEL` | Optional Gemini text-to-speech model; defaults to `gemini-2.5-flash-preview-tts` (must be enabled for your key) |
| `GEMINI_TTS_VOICE` | Optional prebuilt TTS voice name; defaults to `Kore` |
| `YOUTUBE_API_KEY` | YouTube Data API v3 public video search |
| `GROQ_API_KEY` | Existing fallback text provider |
| `GOOGLE_CLOUD_PROJECT` and `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Existing optional Vertex AI video generation adapter |
| `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` | Existing optional Cloudflare image fallback |

After adding dependencies, commit the updated `requirements.txt` and deploy the existing Render service. No new Render service is needed for this workspace.

## Safety and known limits

- Document and voice uploads are size-limited and processed in the request. Do not upload passwords, private keys, payment credentials or other secrets.
- A scanned PDF may need OCR; this release does not claim OCR support for image-only PDF pages.
- YouTube API quota and transcript availability are controlled by Google/YouTube.
- Video generation is not an unlimited free feature. Provider billing, region and model access apply.
- Agent planning is not autonomous execution. A plan is returned with `planning_only` status.
- Cross-platform chat history still depends on correctly linking the Telegram/WhatsApp identity to the CyberLord account and on successful provider webhook delivery.
- Provider credentials and external integrations have not been live-tested as part of this source-code build.

## Roadmap coverage (honest implementation status)

| Roadmap area | Status in this ZIP |
| --- | --- |
| Advanced reasoning, provider fallback and per-user memory | Existing provider chain and memory are retained; Super Mode document analysis adds a grounded, source-limited prompt. A separate multi-model judge/self-check pipeline is not included. |
| Internet research and YouTube | Existing Gemini Search grounding is retained; YouTube search and transcript summarization are added with API/dependency setup. |
| Advanced vision and OCR | Existing image understanding is retained. OCR for image-only/scanned PDFs and handwriting-specific OCR are not included in this release. |
| Video intelligence | Existing optional short video generation is retained; YouTube transcript-based video summarization is added. Uploading arbitrary MP4s for full video analysis is not included. |
| File intelligence | Existing file creation is retained; document text extraction and Gemini analysis are added. |
| Voice | Existing browser speech input/playback is retained; browser-recorded audio-note transcription is added. WhatsApp/Telegram voice-note ingestion and generated audio-file replies are not included yet. |
| Autonomous agent | Task planning and approval warnings are added. It does not execute tasks or perform external account actions. |
| Learning/training center | Existing Academy, Tutor, quizzes and progress features are retained. |
| Shared platform intelligence | Existing shared messaging processor and linked-account flow are retained. Provider delivery and cross-platform sync still require real credentials, account linking and webhook configuration. |
| Reliability/security monitoring | Existing monitoring worker/UI are retained; Super Mode adds a provider-configuration readiness endpoint. This is not an uptime SLA or complete observability platform. |

This ZIP is a safe additive integration step, not a claim that every future capability is fully autonomous or available without provider setup.

## Additional multimodal features in this revision

- **Scanned PDF OCR:** if a PDF has no selectable text, the app sends the PDF bytes directly to Gemini's multimodal endpoint and asks it to read the scan. OCR output can contain recognition errors; verify important figures, names and legal/financial text against the original.
- **Uploaded video analysis:** Super Mode accepts MP4, MOV and WEBM clips up to 20 MB and sends them to Gemini for visual analysis. This is a short-clip feature, not a long-video editor or guaranteed full-frame forensic tool. Provider model support, duration limits, quota and account access apply.
- **WhatsApp and Telegram voice-note input:** incoming audio media is downloaded through the official provider API, transcribed by Gemini and passed to the existing shared messaging processor. This requires the same working webhook credentials plus `GEMINI_API_KEY`. Unsupported audio formats or provider media expiry can prevent transcription.
- **Generated spoken replies in the browser:** the Super Mode Speak button requests Gemini audio output. Configure `GEMINI_TTS_MODEL` (default `gemini-2.5-flash-preview-tts`) and optionally `GEMINI_TTS_VOICE` (default `Kore`). The selected model must be enabled for the API key. The response audio codec is provider-defined; browser support can vary.

These changes do not claim automatic voice-note replies from WhatsApp/Telegram. Their incoming voice notes are transcribed and answered as text; the browser Super Mode can play generated speech. Platform-specific audio encoding and outbound audio policy need a separate tested adapter before sending voice messages back through those channels.
