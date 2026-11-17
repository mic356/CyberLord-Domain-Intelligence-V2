# CyberLord image AI repair

This is a targeted repair to the existing project. It does not replace the site or change its Dashboard AI / Academy Tutor personas.

## Shared image generation
- Dashboard AI continues to use `POST /api/ai-image`.
- Full-page Tutor and Academy lesson Tutor now use `POST /api/tutor-image`.
- Both authenticated endpoints call the same Gemini image-generation/editing helper, `_generate_image_result`.
- Telegram and WhatsApp use that same helper through `_process_messaging_event`, then return generated images using their native media APIs.

## Messaging prompts
Image creation supports `/image <description>` and natural instructions such as `generate an image of ...`, `create a logo for ...`, and `draw an illustration of ...`. Reference-image edits support instructions such as `edit this image to use a dark background` in the image caption.

## Future platforms
`POST /api/channel/message` is a provider-neutral, HMAC-authenticated message-processing endpoint for future platform adapters. Configure `CYBERLORD_CHANNEL_WEBHOOK_SECRET`. A future provider still needs its own authenticated adapter to download incoming media and deliver returned images through its own API. See `CHANNEL_ADAPTER_GUIDE.md`.

## Render configuration
Keep `GEMINI_API_KEY` and `GEMINI_IMAGE_MODEL` in Render Environment. The image model defaults to `gemini-3.1-flash-image`. Check the model's access and quota if image generation returns a provider error. Never commit secrets to GitHub.

## Validation performed
- `python -m py_compile app.py test_messaging_features.py`: passed.
- `node --check static/app.js`: passed.
- Image prompt normalization checks: passed.
- Full Flask integration tests could not run in this workspace because the `phonenumbers` package is not installed. It is listed in `requirements.txt`; run the test after dependencies are installed.
- Live Gemini, Telegram and WhatsApp calls were not made because provider credentials are not available in this workspace.


## Image accuracy and provider fallback update

- Selects `GEMINI_VISION_MODEL` (default `gemini-3.8-flash`) for requests with actual image attachments.
- Adds strict visual-grounding instructions: inspect the supplied pixels, distinguish observations from uncertain interpretations, and do not invent unreadable text or unseen objects.
- Normalizes each attached image to at most 2.5 MB before including it in the Gemini request, reducing the risk of exceeding inline multimodal request limits while retaining up to four images.
- Returns a clear vision-provider error instead of silently falling back to a text-only model when Gemini vision fails.
- Adds Cloudflare Workers AI FLUX.1 schnell as a text-to-image fallback when Gemini image generation is unavailable. It uses a limited daily free allocation; it is not unlimited. Reference-image editing still requires Gemini.
- Combines Wikimedia and Openverse image search results instead of returning early when Wikimedia alone fills the result list.
