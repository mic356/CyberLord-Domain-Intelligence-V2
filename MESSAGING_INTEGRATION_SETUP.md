# CyberLord WhatsApp and Telegram integration

This integration adds official webhook adapters to the existing Flask app. Both channels call the existing `/api/ai-assistant` implementation internally, preserving the current Gemini -> Groq -> built-in fallback chain and the two existing personas. The original dashboard and Academy pages are unchanged.

## Environment variables

Configure these in Render (Dashboard -> your web service -> Environment). Never commit real values to GitHub.

### Telegram
- `TELEGRAM_BOT_TOKEN`: token from the official BotFather bot setup.
- `TELEGRAM_WEBHOOK_SECRET`: a long random secret (letters, digits, `_` and `-`; Telegram accepts 1-256 characters).

After deployment, set the webhook to `https://YOUR-DOMAIN/webhooks/telegram` and supply the same secret token in Telegram's `setWebhook` request as `secret_token`. For example, run this locally after replacing the placeholders (do not commit the token):

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://YOUR-DOMAIN/webhooks/telegram" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

The webhook endpoint rejects requests unless the secret is configured and matches.

### WhatsApp Cloud API
- `WHATSAPP_ACCESS_TOKEN`: Meta WhatsApp Cloud API access token.
- `WHATSAPP_PHONE_NUMBER_ID`: the WhatsApp Cloud API phone-number ID (not the displayed phone number).
- `WHATSAPP_VERIFY_TOKEN`: a private string you choose; use the same value in Meta webhook verification.
- `WHATSAPP_APP_SECRET`: Meta app secret; required to validate incoming webhook signatures.
- `WHATSAPP_API_VERSION`: optional Graph API version; defaults to `v26.0`. Update it to a currently supported version in your Meta app when needed.

In Meta for Developers, configure the callback URL as `https://YOUR-DOMAIN/webhooks/whatsapp`, enter the verify token, and subscribe the WhatsApp Business Account to the `messages` webhook field. Add/verify a test recipient and complete Meta's required business/app setup before production messaging. WhatsApp free-form replies are subject to Meta's customer-service messaging window; outside that window, an approved message template may be required.

## Chat commands

- `/main` selects the existing CyberLord Dashboard AI.
- `/tutor` selects the existing CyberLord Academy Tutor.
- `/reset` clears the recent database-backed conversation context.
- `/link CODE` securely links this chat to the currently signed-in CyberLord account.
- `/unlink` disconnects this chat from the website account.
- `/help` shows the commands.

Messages without a command go to the currently selected persona. Each new chat starts with the Dashboard AI.

## Operational notes

- This is an adapter, not a replacement website or AI engine.
- Tutor access requires account linking; usernames, display names, email addresses and phone numbers are not used to prove identity.
- Linked messaging tutor requests use the same website account's Tutor Pro expiry and 10-question daily free allowance.
- Conversation context, persona selection, link mappings and webhook duplicate detection are stored in SQL tables.
- WhatsApp production messaging still requires a configured Meta WhatsApp Business Cloud API number, valid credentials, webhook subscription and Meta verification.
- Webhook endpoints require HTTPS in production. Keep all tokens in Render environment variables, not source files.

## GitHub safety

Review `.gitignore` before committing. Do not upload `.env`, database files, API tokens, Meta app secrets, or Telegram bot tokens. Rotate any credential that has ever been committed publicly.

## Updating the existing GitHub repository

This package is an update to the existing `mic356/CyberLord-Domain-Intelligence-V2` project, not a new application. Extract the ZIP and upload/replace its project files in that existing repository (keep the repository's current `main` branch and Render service). Do not run `git init`, do not create a second repository, and do not replace the existing Render service. Review the changed files before committing. Never upload `.env`, database files, API tokens, Telegram bot tokens or Meta app secrets. Once the changes are committed to the connected branch, Render can deploy through its existing GitHub integration.

Keep your existing `DATABASE_URL`, `SECRET_KEY`, Gemini/Groq keys, Telegram bot token and Telegram webhook secret unchanged. For WhatsApp, add the Meta values listed above to Render Environment. Existing database tables and subscription records are preserved; the new messaging and receipt tables are created additively on startup.


## Account linking and shared Tutor Pro (implemented)

Customers must sign in to the existing CyberLord website and open **Account → Messaging** (`/account/messaging`). Generate an eight-digit, one-time code and send `/link CODE` to the Telegram bot or WhatsApp business number. Codes expire after 10 minutes, are stored as hashes, can only be used once, and link by the verified channel chat identifier—not by username or phone/email matching. Link attempts are rate-limited. Use `/unlink` in the chat or the website Disconnect button to revoke a connection.

Linked Telegram and WhatsApp Academy Tutor requests run through the same website AI tutor endpoint and use the same database `TutorUsage` daily counter (10 free questions per UTC day) and the linked website account's `tutor_pro_expires_at` entitlement. Tutor Pro remains a separate 30-day add-on. Messaging history, selected persona, and webhook event de-duplication are database-backed.

## Bank transfer receipt uploads

The OPay and Union Bank payment forms accept an optional JPG, PNG, WEBP or PDF receipt (maximum 5 MB). Files are stored in the configured SQL database, not Render's temporary filesystem. Admins can view an uploaded receipt from the payment card. Bank transfers remain pending until a human verifies the funds and approves the payment; uploading a receipt never activates a subscription. Existing USDT TRC20/BEP20 transaction verification is unchanged.

## WhatsApp production configuration

The WhatsApp Cloud API webhook is available at `https://cyberlord.name.ng/webhooks/whatsapp`. Configure the Meta app's webhook subscription for the `messages` field and set these Render environment variables: `WHATSAPP_VERIFY_TOKEN` (a random value you choose), `WHATSAPP_APP_SECRET` (Meta app secret, used to validate `X-Hub-Signature-256`), `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and optionally `WHATSAPP_API_VERSION` (defaults to `v26.0`). The webhook rejects POST requests if `WHATSAPP_APP_SECRET` is absent. WhatsApp will not work until a Meta WhatsApp Business Cloud API number and credentials are configured and Meta verifies the callback.

Keep all bot tokens and app secrets in Render Environment. Never put them in source code or share them in chat.
