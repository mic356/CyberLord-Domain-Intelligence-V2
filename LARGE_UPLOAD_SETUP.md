# CyberLord large-file uploads (up to 2 GB per file)

The unified Dashboard AI attachment flow uses an authenticated multipart uploader. Large file bytes go directly from the browser to a **private Backblaze B2 bucket** using its S3-compatible API; Flask receives only small control requests. The server streams the stored object to the Gemini Files API for analysis and deletes the temporary B2 object afterwards. This does not make every existing chat attachment endpoint 2 GB: dashboard/tutor image and messaging endpoints keep their provider/platform-specific limits.

## 1. Create a private Backblaze B2 bucket

1. Sign in to the [Backblaze B2 Console](https://www.backblaze.com/sign-in).
2. Open **Buckets** and create a bucket named `cyberlord-private-uploads` (or another unique name).
3. Set bucket access to **Private**. Do not create a public bucket or public download URL.
4. Note the bucket's region (for example `us-west-004`). The S3 endpoint must match that region, in the form `https://s3.<region>.backblazeb2.com`.
5. Open **Application Keys** and create a key restricted to this bucket. Give it the permissions required for listing, reading, writing and deleting files. Copy the Key ID and Application Key immediately; the secret is not shown again.

## 2. Configure bucket CORS for browser multipart uploads

Use the Backblaze B2 bucket CORS configuration/API to allow only the origins your users actually use. Include both your custom domain and Render domain if both are used. Example policy:

```json
[
  {
    "corsRuleName": "cyberlord-browser-multipart",
    "allowedOrigins": ["https://cyberlord.name.ng", "https://cyberlord-domain-intelligence.onrender.com"],
    "allowedOperations": ["s3_put", "s3_get", "s3_head"],
    "allowedHeaders": ["*"],
    "exposeHeaders": ["ETag"],
    "maxAgeSeconds": 3600
  }
]
```

If the Backblaze console/API presents a different CORS schema, use its documented schema for S3-compatible bucket CORS. The essential requirement is that browser `PUT` requests are allowed and the `ETag` response header is exposed to JavaScript. Restrict origins to your real website origins.

## 3. Add environment variables to the existing Render web service

Open the existing CyberLord web service in Render → **Environment** and add:

- `B2_ENDPOINT_URL` = `https://s3.<your-region>.backblazeb2.com` (replace the region with the bucket's actual region)
- `B2_REGION` = your bucket region, for example `us-west-004`
- `B2_KEY_ID` = the Backblaze Key ID
- `B2_APPLICATION_KEY` = the Backblaze Application Key
- `B2_BUCKET_NAME` = `cyberlord-private-uploads` (or your actual bucket name)
- `CYBERLORD_LARGE_FILE_MAX_BYTES` = `2147483648`

Keep the existing `GEMINI_API_KEY`. Never put credentials in GitHub, HTML, JavaScript, screenshots or this ZIP. Save changes and let the existing Render service redeploy.

## 4. Supported large-file analysis formats and limits

The dedicated uploader accepts MP4, MOV, WEBM, MPEG, PDF, JPG, JPEG, PNG, WEBP, MP3, WAV, M4A, OGG, DOCX, XLSX, PPTX, TXT, MD and CSV. Video, audio, PDF and image files can use the configured up-to-2-GB upload path only where Gemini's current file, duration, model, project-storage and quota limits permit. Office and text documents are extracted server-side and capped at 50 MB for safe parsing. WhatsApp and Telegram retain their own platform download/media limits.

This is not unlimited storage or guaranteed 2-GB processing for every file. Storage capacity, request quotas, network timeouts and AI-provider restrictions still apply. Monitor Backblaze and Gemini usage.

## 5. Incomplete upload cleanup

Configure a B2 lifecycle rule to remove incomplete multipart uploads after an appropriate short period (for example one day), if supported by your bucket/account configuration. The application deletes completed temporary B2 objects after analysis. Keep the bucket private and use a bucket-restricted application key.

## 6. Deploy through the existing GitHub repository

Upload the changed files from this ZIP into the existing repository and same branch, replacing matching files:

- `app.py`
- `templates/base.html`
- `templates/dashboard.html`
- `static/app.js`
- `UNIFIED_AI_CHAT_UPDATE.md`
- `README.md`
- `LARGE_UPLOAD_SETUP.md`

`requirements.txt` already includes `boto3`, which is used for the B2 S3-compatible API. Do not delete unrelated repository files. Render should deploy from the existing service and branch. After deployment, set the environment variables above, then test with a small file before attempting a very large upload.

## Notes and limitations

- Upload uses multipart parts and displays progress. This dashboard attachment implementation uploads in one active browser session. If a network failure interrupts it, start the attachment again; resumable browser-session recovery is not currently wired into the dashboard chat.
- The 2-GB ceiling applies to the unified Dashboard AI large-file attachment path, not every existing form, bot or channel. Office and text documents are capped at 50 MB.
- Gemini may reject a file even when B2 accepts it. Provider file-size, duration, model and quota limits always take priority.
- Large uploads can consume storage and operation allowances and Gemini quota. Check current pricing and account limits before using heavily.
