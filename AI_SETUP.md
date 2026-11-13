# CyberLord AI setup (Gemini)

The CyberLord tutor and the main AI assistant use Google Gemini when a key is set, and fall back to the built-in knowledge base when no key is set or Gemini fails. No key is stored in this repo. Do NOT paste a real key into any file here.

## Where to paste the key (Render)

1. Open Render dashboard and select the **CyberLord Domain Intelligence V2** service.
2. Go to **Environment** in the left sidebar.
3. Add (or edit) a variable:
   - Key: `GEMINI_API_KEY`
   - Value: your Gemini API key from Google AI Studio (never commit it to GitHub).
4. Optionally add `GEMINI_MODEL` to switch the model (default is `gemini-2.5-flash`, a flash-class model). Leave it unset to use the default.
5. Save. Render redeploys the service. The tutor and AI answers will then come from Gemini; if Gemini is unavailable or errors, the site automatically falls back to the built-in answers.

## How it works

- Both the lesson tutor panels and the full-page `/tutor` dashboard call the server endpoint `/api/ai-assistant`.
- The server checks for `GEMINI_API_KEY` in the environment. When set, it calls the Google Generative Language API (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`) with a 12-second timeout.
- On any error (bad key, timeout, empty reply), the server logs a warning and returns the built-in answer instead, so the site keeps working.
- The key never appears in browser JavaScript, templates or static files.

## Voice (no key needed)

The speaker ("Listen") buttons use the browser's built-in Web Speech API (`speechSynthesis`), which is free and works on phones and desktops. Where the browser does not support it, the buttons simply do not appear.
