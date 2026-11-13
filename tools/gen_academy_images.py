#!/usr/bin/env python3
"""Generate Academy SVG diagrams + course covers (original art, no external assets)."""
import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "academy")
os.makedirs(OUT, exist_ok=True)

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def diagram(title, steps, caption):
    W, BW, BH, GAP = 640, 520, 54, 28
    x = (W-BW)//2
    y0 = 84
    H = y0 + len(steps)*(BH+GAP) + 30
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" class="academy-img">']
    s.append('<rect width="100%" height="100%" rx="14" fill="#0b1220"/>')
    s.append(f'<text x="{W//2}" y="40" fill="#f5f7fb" font-family="Arial,sans-serif" font-size="21" font-weight="bold" text-anchor="middle">{esc(title)}</text>')
    s.append(f'<rect x="40" y="56" width="{W-80}" height="2" rx="1" fill="#32d6a0"/>')
    y = y0
    for i, (h, b) in enumerate(steps):
        s.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="10" fill="#101a2e" stroke="#32d6a0" stroke-width="1.5"/>')
        s.append(f'<text x="{W//2}" y="{y+24}" fill="#f5f7fb" font-family="Arial,sans-serif" font-size="15" font-weight="bold" text-anchor="middle">{esc(h)}</text>')
        s.append(f'<text x="{W//2}" y="{y+44}" fill="#9fb0c8" font-family="Arial,sans-serif" font-size="12" text-anchor="middle">{esc(b)}</text>')
        if i < len(steps)-1:
            s.append(f'<line x1="{W//2}" y1="{y+BH}" x2="{W//2}" y2="{y+BH+16}" stroke="#32d6a0" stroke-width="2"/>')
            s.append(f'<polygon points="{W//2-6},{y+BH+16} {W//2+6},{y+BH+16} {W//2},{y+BH+27}" fill="#32d6a0"/>')
        y += BH + GAP
    s.append(f'<text x="{W//2}" y="{H-10}" fill="#7e8ea8" font-family="Arial,sans-serif" font-size="11" text-anchor="middle">{esc(caption)}</text>')
    s.append('</svg>')
    return "\n".join(s)

def cover(title, subtitle, motif):
    W, H = 800, 400
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)} cover" class="course-cover">']
    s.append('<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1220"/><stop offset="1" stop-color="#12303a"/></linearGradient></defs>')
    s.append('<rect width="100%" height="100%" fill="url(#g)"/>')
    for gx in range(0, W, 64):
        s.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{H}" stroke="#1e2e4a" stroke-width="1"/>')
    for gy in range(0, H, 64):
        s.append(f'<line x1="0" y1="{gy}" x2="{W}" y2="{gy}" stroke="#1e2e4a" stroke-width="1"/>')
    s.append(motif)
    s.append(f'<text x="48" y="{H-96}" fill="#ffffff" font-family="Arial,sans-serif" font-size="40" font-weight="bold">{esc(title)}</text>')
    s.append(f'<text x="48" y="{H-52}" fill="#32d6a0" font-family="Arial,sans-serif" font-size="20">{esc(subtitle)}</text>')
    s.append(f'<rect x="48" y="{H-34}" width="120" height="5" rx="2.5" fill="#32d6a0"/>')
    s.append('</svg>')
    return "\n".join(s)

DIAGRAMS = {
"networking-essentials": ("TCP: a conversation UDP: postcards", [
    ("Client sends SYN", "wants to talk"),
    ("Server replies SYN-ACK", "agrees and picks a sequence"),
    ("Client sends ACK", "connection open"),
    ("Data flows both ways", "ordered, retransmitted if lost"),
    ("FIN exchange", "both sides close cleanly"),
], "TCP is reliable and ordered. UDP skips all of this: fire-and-send."),
"kali-linux-basics": ("Safe terminal habits", [
    ("pwd / ls / cd", "know where you are"),
    ("whoami / ip addr", "know your account and network"),
    ("Read the help first", "man and --help before new tools"),
    ("Run untrusted scripts in a VM", "never pipe unknown code to bash as root"),
], "Rule one: only practise in your own lab or systems you may test."),
"nmap-fundamentals": ("Nmap port states", [
    ("open", "service accepted the connection"),
    ("closed", "host replied, nothing listening"),
    ("filtered", "firewall dropped probes, state unknown"),
], "Filtered is not closed. It means you cannot tell."),
"http-tls-headers": ("A request and its locked reply", [
    ("Browser sends GET /login", "method, path, headers"),
    ("Server checks the request", "status code + security headers"),
    ("Browser enforces the headers", "HSTS, CSP, X-Content-Type-Options"),
    ("TLS wraps everything", "encrypted in transit, server authenticated"),
], "Status codes describe the answer. Headers describe the rules."),
"cve-triage": ("CVE triage in four gates", [
    ("Gate 1 - Product match", "is it the same software?"),
    ("Gate 2 - Version match", "affected range or backported fix?"),
    ("Gate 3 - Exposure", "internet-facing or isolated lab?"),
    ("Gate 4 - Impact", "what breaks if it is exploited?"),
], "A CVE number alone proves nothing. Pass all four gates first."),
"security-reporting": ("A finding that holds up", [
    ("Title + asset + scope", "what, where, was it in scope?"),
    ("Evidence you can re-run", "exact steps, commands, output"),
    ("Impact in plain words", "what an attacker gains"),
    ("Fix + retest", "remediation, then verify it worked"),
], "Separate what you saw from what you assume."),
"owasp-top10": ("OWASP Top 10 mindset", [
    ("Broken access control", "can the user see what they should not?"),
    ("Injection & crypto flaws", "does input reach the database unchecked?"),
    ("Insecure design & logging gaps", "was it built safe and logged after?"),
], "Ten categories that cause most real breaches. Think attacker, build defender."),
"xss-explained": ("How cross-site scripting works", [
    ("Attacker plants a script", "in a comment field, profile, or URL"),
    ("Victim loads the page", "script runs in the victim's browser"),
    ("Script steals the session", "cookies, keystrokes, or actions as the victim"),
    ("Defense: escape + CSP", "encode output, block inline scripts"),
], "XSS turns your users' browsers into the attacker's tool."),
"sqli-deep-dive": ("SQL injection, step by step", [
    ("User input goes into a query", "' OR 1=1 -- in a login field"),
    ("Query logic changes", "the database returns rows it should not"),
    ("Data leaks out", "dumped via errors, union results, or timing"),
    ("Defense: parameterised queries", "never build SQL from raw input"),
], "If input can change the query, the query is yours to break."),
"auth-flaws": ("Authentication flaws", [
    ("Weak or reused passwords", "no rate limit, no MFA"),
    ("Session token leaks", "XSS, logs, or plain HTTP"),
    ("Insecure recovery flow", "predictable reset tokens, verbose errors"),
    ("Defense: MFA + secure sessions", "HttpOnly, Secure, SameSite, expiry"),
], "Most account takeovers start at login, not in the database."),
"secure-code-review": ("Review a login endpoint", [
    ("What comes in?", "types, length, encoding, auth state"),
    ("What happens next?", "query shape, permission check order"),
    ("What goes out?", "error detail, timing, logging"),
    ("Write it down", "observations, assumptions, retest plan"),
], "Read the flow before you judge the code."),
"tcp-handshake": ("The TCP handshake", [
    ("SYN - client", "I would like to talk"),
    ("SYN-ACK - server", "me too, here is my sequence"),
    ("ACK - client", "connection established"),
], "Three packets before a single byte of data moves."),
"firewalls-vpn": ("Firewall + VPN place in the path", [
    ("Traffic hits the firewall", "allow, deny, or log by rule"),
    ("VPN tunnel opens", "traffic encrypted inside the tunnel"),
    ("Server answers through the tunnel", "decrypted only at the far end"),
], "Firewalls filter. VPNs encrypt. Neither replaces the other."),
"packet-analysis": ("Reading a packet capture", [
    ("Frame start", "timestamp, size, direction"),
    ("Header fields", "addresses, ports, protocol"),
    ("Payload peek", "what the bytes actually say"),
    ("Pattern check", "repeats, anomalies, exfiltration"),
], "Wireshark answers: who talked, when, and what they said."),
"dns-security": ("DNS records an attacker wants", [
    ("A / AAAA to host", "where the domain points"),
    ("MX to mail server", "where mail is delivered"),
    ("TXT carries SPF + DKIM", "who may send mail, how it is signed"),
    ("CAA limits certificates", "who may issue TLS for the domain"),
], "DNS is the phonebook, the map, and the mail permission slip."),
"spf-dkim-dmarc-deep": ("Email authentication flow", [
    ("Sender signs with DKIM", "private key signs the message"),
    ("Receiver checks SPF", "is this IP allowed to send?"),
    ("Receiver checks DKIM", "does the signature verify?"),
    ("Receiver applies DMARC", "reject, quarantine, or pass?"),
], "Three checks together stop most lookalike-domain spoofing."),
"phishing-anatomy": ("Anatomy of a phishing email", [
    ("Hook: urgent lure", "account locked, invoice due, prize won"),
    ("Spoof: lookalike sender", "off by one letter, wrong domain"),
    ("Trap: fake login page", "harvests password and MFA code"),
    ("Payload: account takeover", "spam, fraud, or lateral phishing"),
], "Read the sender domain, not the display name."),
"social-engineering": ("Social engineering plays", [
    ("Pretexting", "a made-up story that earns trust"),
    ("Urgency + authority", "the boss, the bank, the deadline"),
    ("Baiting", "free prize, free tool, free download"),
    ("Vishing & smishing", "the same tricks by voice and text"),
], "People are not the weakest link. Process is."),
"forensics-process": ("Incident response lifecycle", [
    ("Prepare", "backups, runbooks, who to call"),
    ("Detect + analyse", "what happened, who, and how far"),
    ("Contain", "stop the spread without destroying evidence"),
    ("Eradicate + recover", "remove the cause, restore, watch"),
    ("Lessons learned", "write it down, fix the process"),
], "Order matters: contain before you rebuild."),
"evidence-handling": ("Handling evidence properly", [
    ("Capture first", "images, logs, screenshots, memory"),
    ("Hash everything", "SHA-256 proves nothing changed since"),
    ("Chain of custody", "who held it, when, and why"),
    ("Work on copies", "never analyse the original"),
], "Evidence you cannot prove you kept is evidence you do not have."),
"ir-playbook": ("Your first 24 hours of an incident", [
    ("Hour 0 - triage", "confirm it is real, name an owner"),
    ("Hour 1 - contain", "isolate, block, revoke sessions"),
    ("Hours 2-8 - scope", "who is affected, what data, how did it start"),
    ("Hour 24 - comms", "what you know, what you do not, next update"),
], "Slow down, write everything, communicate early."),
"secplus-roadmap": ("Security+ road map", [
    ("Domain 1 - concepts", "vocabulary, tools, attacks"),
    ("Domain 2 - architecture", "systems, networks, identity"),
    ("Domain 3 - operations", "monitoring, IR, governance"),
    ("Exam day", "performance-based questions, timed"),
], "One cert at a time. Depth beats collecting badges."),
"ceh-vs-blue-team": ("Red team, blue team, and purple", [
    ("Red team", "thinks like the attacker"),
    ("Blue team", "defends, detects, responds"),
    ("Purple team", "runs exercises and closes the gaps live"),
], "CEH teaches attack. Blue team jobs teach defence. You need both."),
"cv-and-interview": ("A junior security CV that works", [
    ("Evidence over adjectives", "labs, projects, certs, tools used"),
    ("One page, tailored", "match the job description keywords"),
    ("Interview prep", "walk through one project in detail"),
    ("Salary talk", "research the local market, name a range"),
], "Hiring managers scan for proof. Show your work."),
"lab-building": ("Build a home security lab", [
    ("Virtualiser: VirtualBox or VMware", "isolated VMs you own"),
    ("Kali + a target VM", "attacker practice, safe target"),
    ("Snapshot before you break", "rollback in seconds"),
    ("Network: host-only or lab LAN", "no route to the internet unless needed"),
], "A lab you control is the only place to learn offensive skills safely."),
"web-access-control": ("Access control: who may see what", [
    ("Login: who are you?", "identity checked once"),
    ("Authorisation: what may you touch?", "checked on every request"),
    ("IDOR: change the number", "another customer's data appears"),
    ("Fix: ownership check", "deny unless the server proves permission"),
], "Authentication is not authorisation. Check both, every time."),
"crypto-misconfig": ("Misconfiguration: the easy wins", [
    ("Default credentials", "admin / admin still live"),
    ("Debug mode in production", "stack traces and paths leak"),
    ("Verbose errors", "a map for the attacker"),
    ("Hardening checklist", "change defaults, strip detail, close pages"),
], "Most misconfigurations are one setting away from fixed."),
"csrf-ssrf": ("CSRF vs SSRF", [
    ("CSRF: victim's browser forged", "cookies attached automatically"),
    ("SSRF: server fetches attacker URL", "server used as a proxy inside"),
    ("Enter: metadata endpoint", "169.254.169.254 answers with secrets"),
    ("Fix: SameSite + allowlist", "tokens for CSRF, fixed hosts for SSRF"),
], "One rides a user. The other rides your server."),
"secure-design": ("Design flaw + logging gap", [
    ("Feature works as coded", "called twice, refunds twice"),
    ("No abuse case in mind", "the design flaw, not a bug"),
    ("No failed-attempt logs", "credential stuffing invisible"),
    ("Fix: design + event logging", "idempotency, who/what/when/outcome"),
], "If you did not design for abuse, abuse designs you."),
"wifi-vpn-advanced": ("Wireless + VPN risk points", [
    ("WPA2 short passphrase", "offline dictionary crack"),
    ("WPA3 + long passphrase", "the cost goes up fast"),
    ("Split tunnelling", "some traffic skips the tunnel"),
    ("VPN ends at the endpoint", "TLS handles the rest of the way"),
], "A VPN protects the path, not the endpoint."),
"soc-logs": ("SOC triage loop", [
    ("Telemetry arrives", "auth, flows, endpoint, cloud"),
    ("Triage: noise or incident?", "decide in minutes"),
    ("Detection rule", "condition, threshold, window"),
    ("Tune or retire", "unread alerts protect nothing"),
], "Detection is a loop: watch, decide, tune, repeat."),
"what-is-cybersecurity": ("Cybersecurity in one picture", [
    ("Confidentiality", "only the right people can read it"),
    ("Integrity", "it is the same as when it was sent"),
    ("Availability", "it works when you need it"),
    ("CIA triad", "the three promises every defence keeps"),
], "Three promises. Everything in this academy protects one of them."),
"why-hackers-attack": ("What attackers actually want", [
    ("Money", "ransom, fraud, stolen accounts"),
    ("Data to sell", "passwords, cards, identity packs"),
    ("Access and footholds", "a door into a bigger target"),
    ("Notoriety or curiosity", "fame, bragging rights, practice"),
], "Most attacks are business. A few are personal. All are preventable."),
"how-the-internet-works": ("Your message across the internet", [
    ("You type a name", "the browser asks DNS for an address"),
    ("Packets take the road", "routers pass them hop by hop"),
    ("A server answers", "the page comes back the same way"),
    ("TLS locks the envelope", "nobody on the road can read it"),
], "Names, packets, and locks. That is the whole trick."),
"stay-safe-device": ("Petty theft vs digital theft", [
    ("Lock your screen", "and use a real passphrase"),
    ("Update everything", "patches close the open doors"),
    ("Check the sender", "not just the display name"),
    ("Back up, then back up again", "ransomware cannot encrypt what is offline"),
], "Four habits stop most everyday digital crime."),
}

COVERS = {
"course-foundations": ("Cybersecurity Foundations", "Start here - free", '<g><path d="M640 150 L640 210 Q640 260 575 285 Q510 260 510 210 L510 150 L575 120 Z" fill="none" stroke="#32d6a0" stroke-width="7"/><g transform="translate(552,168)"><rect x="0" y="18" width="46" height="34" rx="8" fill="none" stroke="#f5f7fb" stroke-width="6"/><path d="M8 18 V8 Q23 -8 38 8 V18" fill="none" stroke="#f5f7fb" stroke-width="6"/><circle cx="23" cy="34" r="5" fill="#32d6a0"/></g></g>'),
"course-webapp": ("Web Application Security", "PRO course", '<g transform="translate(500,92)"><rect x="0" y="0" width="250" height="170" rx="14" fill="#101a2e" stroke="#32d6a0" stroke-width="4"/><rect x="0" y="0" width="250" height="34" rx="12" fill="#1b2a4a"/><circle cx="24" cy="17" r="7" fill="#ff7a7a"/><circle cx="50" cy="17" r="7" fill="#ffc17c"/><circle cx="76" cy="17" r="7" fill="#32d6a0"/><text x="34" y="86" font-family="Courier,monospace" font-size="22" fill="#55e0ae">&#60;script&#62;</text><text x="34" y="118" font-family="Courier,monospace" font-size="22" fill="#9fb0c8">input OR 1=1</text><text x="34" y="150" font-family="Courier,monospace" font-size="22" fill="#ffc17c">escape output!</text></g>'),
"course-network": ("Network Security", "PRO course", '<g stroke="#32d6a0" stroke-width="3"><line x1="560" y1="200" x2="660" y2="120"/><line x1="560" y1="200" x2="660" y2="280"/><line x1="660" y1="120" x2="720" y2="200"/><line x1="660" y1="280" x2="720" y2="200"/><line x1="560" y1="200" x2="720" y2="200"/></g><g fill="#f5f7fb"><circle cx="560" cy="200" r="14" fill="#32d6a0"/><circle cx="660" cy="120" r="10"/><circle cx="660" cy="280" r="10"/><circle cx="720" cy="200" r="14" fill="#32d6a0"/></g>'),
"course-email": ("Email & Phishing Defense", "PRO PLUS course", '<g transform="translate(500,100)"><rect x="0" y="10" width="240" height="150" rx="12" fill="#101a2e" stroke="#32d6a0" stroke-width="4"/><path d="M6 22 L120 100 L234 22" fill="none" stroke="#f5f7fb" stroke-width="4"/><path d="M195 118 L195 150 Q195 168 172 176 Q150 168 150 150 L150 118 L172 108 Z" fill="#12303a" stroke="#32d6a0" stroke-width="4"/><path d="M162 138 l8 8 l16 -16" stroke="#32d6a0" stroke-width="4" fill="none"/></g>'),
"course-forensics": ("Digital Forensics & IR", "PRO PLUS course", '<g transform="translate(520,96)"><circle cx="110" cy="110" r="78" fill="rgba(50,214,160,0.08)" stroke="#32d6a0" stroke-width="5"/><line x1="168" y1="168" x2="232" y2="232" stroke="#32d6a0" stroke-width="12" stroke-linecap="round"/><text x="52" y="96" font-family="Courier,monospace" font-size="20" fill="#55e0ae">10:41:33</text><text x="52" y="126" font-family="Courier,monospace" font-size="20" fill="#f5f7fb">login OK</text><text x="52" y="156" font-family="Courier,monospace" font-size="20" fill="#ffc17c">anomaly!</text></g>'),
"course-career": ("Career Path & Certifications", "PRO PLUS course", '<g transform="translate(510,90)"><rect x="0" y="130" width="220" height="16" rx="8" fill="#1b2a4a"/><rect x="0" y="130" width="160" height="16" rx="8" fill="#32d6a0"/><text x="0" y="110" font-family="Arial,sans-serif" font-size="18" fill="#9fb0c8">helpdesk</text><text x="60" y="80" font-family="Arial,sans-serif" font-size="18" fill="#9fb0c8">SOC analyst</text><text x="130" y="50" font-family="Arial,sans-serif" font-size="18" fill="#55e0ae">Security+</text><circle cx="178" cy="24" r="18" fill="#32d6a0"/><text x="170" y="32" font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="#0b1220">S+</text></g>'),
}

all_slugs = []
for name, (t, steps, cap) in DIAGRAMS.items():
    open(os.path.join(OUT, name + ".svg"), "w").write(diagram(t, steps, cap))
    all_slugs.append(name + ".svg")
for name, (t, sub, motif) in COVERS.items():
    open(os.path.join(OUT, name + ".svg"), "w").write(cover(t, sub, motif))
    all_slugs.append(name + ".svg")
print(f"wrote {len(all_slugs)} svg files into {OUT}")
