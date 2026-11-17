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
