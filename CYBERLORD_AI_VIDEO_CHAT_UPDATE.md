# CyberLord AI video chat update

- Dashboard AI and Academy Tutor can return YouTube discovery cards directly inside their existing chats.
- Selecting a result plays it in the chat when API search results are available.
- `YOUTUBE_API_KEY` is optional. Without it, a direct YouTube search link is still provided; thumbnails are not fabricated.
- Both AI personas use the same optional original-video generation handler.
- Dashboard AI's video brief is for general educational/creative topics.
- Academy Tutor's video brief is for beginner-friendly, defensive cybersecurity education.
- Agnes remains optional. No GPU subscription or paid fallback has been added.
- If generation cannot be queued, CyberLord clearly says original generation is unavailable and offers existing videos instead.
- Never commit API keys or `.env` files to GitHub.

Original AI video rendering still requires an available generation provider and its compute capacity. This update does not create a free GPU.
