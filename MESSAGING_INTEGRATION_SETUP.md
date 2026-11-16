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
- `WHATSAPP_APP_SECRET`: Meta app secret; recommended so incoming webhook signatures are validated.
- `WHATSAPP_API_VERSION`: optional Graph API version; defaults to `v26.0`. Update it to a currently supported version in your Meta app when needed.

In Meta for Developers, configure the callback URL as `https://YOUR-DOMAIN/webhooks/whatsapp`, enter the verify token, and subscribe the WhatsApp Business Account to the `messages` webhook field. Add/verify a test recipient and complete Meta's required business/app setup before production messaging. WhatsApp free-form replies are subject to Meta's customer-service messaging window; outside that window, an approved message template may be required.

## Chat commands

- `/main` selects the existing CyberLord Dashboard AI.
- `/tutor` selects the existing CyberLord Academy Tutor.
- `/reset` clears the recent in-process conversation context.
- `/help` shows the commands.

Messages without a command go to the currently selected persona. Each new chat starts with the Dashboard AI.

## Operational notes

- This is an adapter, not a replacement website or AI engine.
- Messaging chats are anonymous channel identities; they are not linked to a CyberLord website account. Website account-specific memory, subscriptions, scan history and private dashboard data are therefore not exposed.
- Recent chat context is kept in process memory (up to 10 messages per chat) and is lost when the service restarts or redeploys. For multi-instance durability, add a shared Redis/database conversation store before scaling horizontally.
- The existing tutor free-question limit is account-based; anonymous messaging users are not charged against a website account's tutor allowance. Consider adding explicit phone-number account linking and abuse controls before opening the bot publicly.
- Webhook endpoints require HTTPS in production. Keep all tokens in Render environment variables, not source files.

## GitHub safety

Review `.gitignore` before committing. Do not upload `.env`, database files, API tokens, Meta app secrets, or Telegram bot tokens. Rotate any credential that has ever been committed publicly.

## Uploading to GitHub

1. Extract the delivered ZIP on your computer.
2. Create a new repository on GitHub (choose Private if the source should not be public).
3. Open a terminal in the extracted project folder and run:

```bash
git init
git add .
git status --short
```

4. Review `git status` carefully. Confirm that no `.env`, database, token, credential, or private file is staged. Then commit and connect your repository:

```bash
git commit -m "Add WhatsApp and Telegram AI integrations"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

5. In Render, connect the GitHub repository to your existing web service. Add the environment variables above in Render's Environment page, then deploy. Keep your existing `DATABASE_URL`, `SECRET_KEY`, AI keys, and other service settings unchanged.
