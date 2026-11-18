# CyberLord Free Video Discovery

This update adds an authenticated `/videos` page and a Videos link in the signed-in navigation.

- Search uses YouTube's public search page; no YouTube Data API key is required.
- Users can paste a YouTube video ID or URL and play it in a privacy-enhanced embed.
- Video IDs are validated before embedding.
- This feature does not generate original AI videos and does not use Agnes or a GPU.
- Original AI video generation remains unavailable until a genuinely free GPU runtime or other compute is connected.

No new Python dependencies or Render environment variables are required.
