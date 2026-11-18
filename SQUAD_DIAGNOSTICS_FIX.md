CYBERLORD SQUAD CHECKOUT DIAGNOSTICS PATCH

This patch does not change plan prices, payment amounts, payment channels,
or subscription activation rules.

Changes:
- Logs safe, actionable Squad API errors (HTTP status and response body).
- Logs connection failures, rejected API responses, and missing checkout URLs.
- Never logs the Squad Authorization header or secret key.
- Logs a clear SQUAD_INIT_SUCCESS marker when a checkout URL is received.

After uploading this project to GitHub and allowing Render to deploy:
1. Open Render > your CyberLord service > Logs.
2. Search for SQUAD_.
3. Click one Squad plan button once.
4. Inspect the new SQUAD_API_HTTP_ERROR, SQUAD_API_REJECTED,
   SQUAD_API_CONNECTION_ERROR, SQUAD_INIT_NO_CHECKOUT_URL, or
   SQUAD_INIT_SUCCESS entry.
5. If an error response is shown, share the log text after checking that
   no credentials or personal customer data are present.

Keep SQUAD_SECRET_KEY only in Render Environment. Never commit it to GitHub.
Keep SQUAD_ENV=live only when using the live Squad Secret Key.
For a sandbox test, use the matching sandbox secret key and SQUAD_ENV=sandbox.
