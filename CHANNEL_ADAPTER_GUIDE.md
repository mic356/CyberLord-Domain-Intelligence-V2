# CyberLord channel adapter guide

CyberLord uses one provider-neutral messaging processor for all external chat platforms.
The Dashboard AI and Academy Tutor remain the two personas; a platform adapter must
not create a second AI prompt, image model, conversation store, or billing system.

## Current adapters

- Telegram: `/webhooks/telegram`
- WhatsApp Cloud API: `/webhooks/whatsapp`

Both adapters normalize incoming text and image messages, download media using the
provider's authenticated media API, and pass the normalized event to
`_process_messaging_event(channel, external_id, event_id, text_in, images)` in
`app.py`. Results are sent through `_deliver_messaging_result(...)` with the
provider's text and image delivery callbacks.

## Add a future platform

For Discord, Slack, Messenger, a mobile app, or another approved provider:

1. Add a provider-specific webhook/connector route and verify its signature or
   authentication token before processing anything.
2. Normalize the provider's message into: a stable channel slug (16 characters or
   fewer), the provider's stable user/chat ID, a unique event/message ID, text or
   caption, and optional image objects.
3. Download image media from the provider using its authenticated media endpoint.
   Accept only JPEG, PNG, or WEBP; enforce a 5 MB download limit before base64 encoding.
4. Call `_process_messaging_event(channel, external_id, event_id, text_in, images)`.
5. Deliver the returned text and any generated image using
   `_deliver_messaging_result(result, send_text_callback, send_image_callback)`.
6. Keep provider credentials in environment variables; never hard-code or commit them.
7. Add webhook signature, duplicate-delivery, image upload, image generation and
   account-linking tests for that provider before enabling it in production.

The shared processor provides the same image analysis, image generation/editing,
persona selection, account linking, duplicate protection and AI routing regardless
of provider. A provider adapter is still required: a future platform is not
automatically connected merely by adding its name.

## Shared history and personas

When two messaging channels are linked to the same CyberLord website account,
their conversation history is shared by account and persona (Dashboard AI history
is separate from Tutor history). Unlinked chats keep private, channel-specific
histories. `/reset` clears the active persona's shared history for a linked account.

## Image message behaviour

- An incoming image with a caption is analysed against that caption.
- An incoming image without a caption receives a general image-analysis request.
- Send `/image <description>` or `generate an image of <description>` to create an
  image. Attach a reference image with the generation instruction to request an edit.
- Generated images are returned as media through the platform's image-send API.

Image capabilities require `GEMINI_API_KEY` and a Gemini image model available to
the configured account. Provider file-size, message-window, media-format, quota,
and pricing restrictions still apply.
