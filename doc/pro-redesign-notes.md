# pro-redesign notes (not a live page)

Branch `pro-redesign` only. Nothing merged to main, no deployment.

## Email exposure check
Source: Hudson Rock free keyless endpoint
`https://www.hudsonrock.com/api/json/v2/stats/website-results/email?email=...`
Verified live 2026-11-12 (returns JSON, no key). Infostealer-compromise
intelligence, not a named-breach list. HIBP unauthenticated endpoints are
not free; breach.directory and cib.db.rip were unreachable from our network.
Logic lives in `check_email_exposure()` (pluggable, never raises, honest
`source_unavailable` state). Copy states the scope plainly: not listed does
not mean safe everywhere. Free tier shows verdict plus count of saved
accounts at risk; full record (date, computer name, service counts) is
PRO-gated. Anonymous checks are not stored. Ongoing monitoring is labeled
coming soon, it does not exist yet.

## Design
Dark security aesthetic kept, now tokenised in `static/style.css`:
type scale, spacing scale, surface/colour roles, focus-visible rings,
consistent buttons, cleaner cards, professional empty states. Homepage hero
restructured plus an email-check section. No routes removed, no features
removed.

## AI assistant
Openers shortened to senior-operator voice, generic one-line field notes
added for phishing/nmap/password/ransomware/dns/linux/owasp/cve, and 5 new
topics (email exposure response, SPF/DKIM/DMARC, spoofability check,
passkeys, security.txt). Typing indicator and GEMINI_API_KEY hook kept.
Payment approval is still never handled in chat.

## Interaction board
Found: `templates/interaction_board.html` and `interaction_thread.html`.
Polished with the same tokens (two-column layout, compose pane, post
cards created from plain markup, empty state). Form fields and the 260-char
truncation logic unchanged.
