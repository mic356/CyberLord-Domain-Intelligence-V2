# CyberLord SEO setup: what is done, what you must do

The code side is finished on the `seo` branch. This file is the part only
you can do, because it needs your Google and Microsoft accounts.

## Already done in code

- `/robots.txt` allows all crawlers, points to the sitemap, and blocks
  private areas (dashboard, admin, payment, API, scan routes, etc.)
- `/sitemap.xml` lists all public pages: home, email exposure check, FAQ,
  the three guides, privacy, terms, refund policy and contact
- Every public page has its own title (under 60 characters) and meta
  description (under 160 characters), a canonical link, and Open Graph /
  Twitter card tags for share previews
- JSON-LD structured data: WebSite + Organization on every page,
  WebApplication on the homepage, FAQPage on the FAQ page (the schema
  matches the visible questions on that page)
- New content pages: `/faq`, `/guides/check-if-email-is-compromised`,
  `/guides/website-security-check`, `/guides/spf-dmarc-setup`
- All new pages are linked in the footer and in the sitemap

## Owner to-do list: Google Search Console (10 minutes)

1. Go to https://search.google.com/search-console and sign in with
   michaelelvistito@gmail.com (or whichever Google account you control).
2. Click "Add property", choose "URL-prefix", and enter
   `https://cyberlord.name.ng/`
3. Google gives you a verification method. Easiest is "HTML tag".
   Copy the `content="..."` value.

## Owner to-do list: Bing Webmaster Tools (5 minutes)

1. Go to https://www.bing.com/webmasters and sign in with a Microsoft
   account.
2. Click "Add a site" and enter `https://cyberlord.name.ng`
3. Bing will offer verification by HTML meta tag. Copy the content value.

## Where to paste the verification meta tag

The verification tag goes in the `<head>` section of `templates/base.html`,
right after the existing `<meta charset="utf-8">` line. Because base.html
is the parent of every page, one paste covers the whole site. Example:

```html
<meta name="google-site-verification" content="YOUR_GOOGLE_VALUE">
<meta name="msvalidate.01" content="YOUR_BING_VALUE">
```

Commit that change to the `seo` branch (or main, if you have merged by
then), push it, and let Render redeploy. Then verify in each console:

- Google: click "Verify" on the property. If it fails, you pasted it in
  the wrong place or the deploy has not finished.
- Bing: click "Verify" the same way.

## How to submit the sitemap

Google Search Console:

1. In the left menu click "Sitemaps".
2. In "Add a new sitemap", enter `sitemap.xml` and press Submit.
3. Google will fetch `https://cyberlord.name.ng/sitemap.xml` and list the
   URLs it found. This is the correct URL; do not paste the full address
   again.

Bing Webmaster Tools:

1. In the left menu click "Sitemaps" (or "Sitemap" under your site).
2. Click "Add a Sitemap" and enter
   `https://cyberlord.name.ng/sitemap.xml`
3. Bing will fetch and count the URLs. Changes are usually picked up
   within a day or two.

## How to request indexing of the new guides

Optionally, in Google Search Console use the URL Inspection tool on
`https://cyberlord.name.ng/faq` and the three guide URLs, then click
"Request indexing". It is not required, since the sitemap does the job,
but it can shave days off first discovery for brand-new pages.

## Realistic expectations

Ranking takes weeks, not days. Google indexes a new site within days of
sitemap submission, but ranking for competitive phrases like "check if my
email is leaked" takes consistent content, incoming links and time, and
the honest estimate is 6 to 12 weeks before you see meaningful traffic.
The new pages deliberately target long-tail phrases ("how to check if your
email has been compromised", "SPF and DMARC setup guide", "free website
security check") where a new site can win sooner. Keep publishing a page
or two a month on real problems your users have, share the guides in
Nigerian tech communities (Nairaland, r/Nigeria, local Telegram groups),
and watch Search Console "Pages" and "Performance" weekly. Everything
in this checklist is free; what it needs from you is about 20 minutes
and patience.
