# CyberLord AI setup (Gemini + Groq)

The CyberLord tutor and the main AI assistant answer through a provider chain: **Gemini (if `GEMINI_API_KEY` is set) -> Groq (if `GROQ_API_KEY` is set) -> built-in knowledge base**. The first configured key wins; on error or timeout (12s) the server silently moves to the next provider in the chain, and the built-in knowledge base is last. No key is stored in this repo. Do NOT paste a real key into any file here.

## Option 1: Gemini (primary, when configured)

1. Open Google AI Studio (aistudio.google.com) and create a free Gemini API key (no card required).
2. On Render, open the **CyberLord Domain Intelligence V2** service, go to **Environment**, and add:
   - Key: `GEMINI_API_KEY`
   - Value: your Gemini API key (never commit it to GitHub).
3. Optionally add `GEMINI_MODEL` to switch the model (default is `gemini-2.5-flash`). Leave it unset to use the default.
4. Save. Render redeploys. If Gemini errors or times out, the chain moves on automatically; nothing is shown to the user.

## Option 2: Groq (backup, when configured)

Groq offers a free tier with no card required, and it speaks the same OpenAI-style API, so it slots in as the second provider with only one new env var.

1. Go to Groq Console at https://console.groq.com and sign up (email is enough; no card needed for the free tier).
2. Create an API key in the dashboard and copy it.
3. On Render, open the **CyberLord Domain Intelligence V2** service, go to **Environment**, and add:
   - Key: `GROQ_API_KEY`
   - Value: your Groq API key (never commit it to GitHub).
4. Optionally add `GROQ_MODEL` to switch the model (default is `llama-3.3-70b-versatile`, the 70B Llama 3.3 model). Leave it unset to use the default.
5. Save. Render redeploys. Groq is used only when Gemini is not configured or fails; if Groq also fails, the built-in knowledge base answers instead, with no user-visible fallback message.

## Where it sits in the chain

- Both the lesson tutor panels and the full-page `/tutor` dashboard call the server endpoint `/api/ai-assistant`.
- The server tries `GEMINI_API_KEY` first (Google Generative Language API, `gemini-2.5-flash` by default, 12-second timeout).
- If Gemini is unset or fails, it tries `GROQ_API_KEY` second (OpenAI-compatible endpoint `https://api.groq.com/openai/v1/chat/completions`, `llama-3.3-70b-versatile` by default, 12-second timeout).
- If both are unset or fail, the built-in knowledge base (`cyberlord_ai.py`) answers.
- Failures are logged server-side only; the user never sees which provider is active or that a fallback happened.
- Keys never appear in browser JavaScript, templates or static files.

## Voice (no key needed)

The speaker ("Listen") buttons use the browser's built-in Web Speech API (`speechSynthesis`), which is free and works on phones and desktops. Where the browser does not support it, the buttons simply do not appear.
