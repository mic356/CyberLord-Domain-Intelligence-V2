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
