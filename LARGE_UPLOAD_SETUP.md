# CyberLord large-file uploads (up to 2 GB per file)

This upgrade adds a separate, authenticated multipart uploader. Large file bytes go from the browser directly to a private Cloudflare R2 bucket; Flask receives only small control requests. The server streams the stored object to the Gemini Files API for analysis and deletes the R2 object afterwards. It does not make every existing chat attachment endpoint 2 GB: the normal dashboard/tutor image and messaging endpoints keep their provider/platform-specific limits.

## 1. Create a private Cloudflare R2 bucket

1. In Cloudflare Dashboard, open **R2 Object Storage** and create a bucket (for example `cyberlord-private-uploads`).
2. Keep the bucket private. Do not enable public access or publish a custom domain for this bucket.
3. Create an R2 API token with **Object Read & Write** permission scoped only to this bucket. Copy the Access Key ID and Secret Access Key once.
4. Copy your Cloudflare account ID.
5. In the bucket settings, add a CORS policy. Replace `https://cyberlord.name.ng` with the exact website origin users open (add the Render domain too if users access it directly):

```json
[
  {
    "AllowedOrigins": ["https://cyberlord.name.ng", "https://cyberlord-domain-intelligence.onrender.com"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

The browser must be allowed to read the `ETag` response header for each multipart part. Keep origins limited to your actual site domains.

## 2. Add Render environment variables

In the existing Render web service, open **Environment** and add:

- `R2_ACCOUNT_ID` = your Cloudflare account ID
- `R2_ACCESS_KEY_ID` = the R2 Access Key ID
- `R2_SECRET_ACCESS_KEY` = the R2 Secret Access Key
- `R2_BUCKET_NAME` = your private bucket name
- `CYBERLORD_LARGE_FILE_MAX_BYTES` = `2147483648`

Keep the existing `GEMINI_API_KEY`. Do not put any of these secret values in GitHub, HTML, JavaScript, or this ZIP. Save changes and let the existing Render service redeploy.

## 3. Supported large-file analysis formats

The large uploader accepts MP4, MOV, WEBM, MPEG, PDF, JPG, JPEG, PNG, WEBP, MP3, WAV, M4A, OGG, DOCX, XLSX, PPTX, TXT, MD and CSV. Video, audio, PDF and image files can use the provider-supported 2 GB path, subject to Gemini's current per-file, project storage, model, duration and quota restrictions. Office and text documents are extracted server-side and are limited to 50 MB for safe parsing; extracted text is sent to Gemini. WhatsApp and Telegram retain their own platform download/media limits.

Google's Gemini Files API currently documents a 2 GB per-file limit on the free tier, but account/project total storage and model-specific limits also apply. This is not unlimited storage or guaranteed 2 GB processing for every model/file type. Check Google's current API limits before increasing the cap.

## 4. Recommended bucket lifecycle

Configure an R2 lifecycle rule to abort incomplete multipart uploads after 1 day. This clears abandoned multipart parts if a browser closes or loses connection before completion. The application deletes the completed R2 object after processing. Keep the bucket private and use a bucket-scoped token.

## 5. Deploy through the existing GitHub repository

Upload the changed files from the ZIP into the existing repository and same branch, replacing matching files:

- `app.py`
- `requirements.txt`
- `templates/super_mode.html`
- `super_mode.py`
- `user_memory.py`
- `artificial_brain.py`
- `test_artificial_brain.py`
- `test_super_mode.py`
- `LARGE_UPLOAD_SETUP.md`

Do not delete unrelated repository files. Render should deploy from the existing service and branch. After deployment, set the environment variables above, then open Super Mode and try a small test file first before attempting a very large upload.

## Notes / limitations

- Upload is multipart and shows progress. The browser stores the session in local storage and can query completed R2 parts after a reload. To resume, reselect the exact same file in the same browser. A session can still expire or be removed by storage lifecycle rules.
- The 2 GB ceiling applies to this dedicated large uploader, not every existing form, bot or channel. Office and text documents are capped at 50 MB.
- Gemini may reject a file even when R2 accepts it. A provider's file size, duration, model and quota limits always win.
- Large uploads may consume R2 storage/operations and Gemini quota. Monitor usage and billing in the provider dashboards.
