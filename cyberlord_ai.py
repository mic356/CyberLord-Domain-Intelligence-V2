"""Free CyberLord knowledge assistant with curated cybersecurity guidance and public vulnerability lookups.
No paid LLM or API key is required. External lookups use public NVD/CISA feeds when reachable.
"""
import re
import requests
from datetime import datetime, timezone

TOPICS = [
("using cyberlord platform tools", "CYBERLORD USER GUIDE: Start from the dashboard and choose the module that matches the question. Domain Security Scan reviews public DNS, TLS, HTTP security headers and cookie posture. Subdomain Intelligence checks common hostnames. Email Security reviews MX, SPF, DMARC and DKIM posture. DNS Intelligence looks up selected DNS records. Technology Fingerprint reports visible technology hints. IP Intelligence reviews public IP and registration context. Phone Intelligence reports number-format, region, carrier and timezone hints only; it does not locate a person's live position. Individual Email Review checks syntax and domain mail posture. Breach Exposure depends on the configured provider. Attack Surface Map combines available inventory checks. CVE Intelligence provides evidence-led vulnerability context. Compare Domains highlights differences. Limited Port Scanner requires an available configured Kali worker and explicit authorisation. Some tools are plan-gated. Always read each tool's on-screen guide, confirm you have permission, submit the target, wait for the result and review evidence, limitations and remediation. Scan results are indicators, not proof of compromise."),
("cyberlord payments subscriptions account", "CYBERLORD ACCOUNT AND BILLING GUIDE: Free accounts can access free modules. Pro is NGN 6,300 or 4.50 USDT for 30 days. Pro Plus is NGN 12,600 or 9.00 USDT for 30 days. Prices are fixed, not live currency conversions. USDT payment supports the displayed TRC20 and BEP20 networks; select the exact network used. The server verifies transaction details before activation. Bank transfers are submitted for review and remain pending until independently confirmed. A screenshot, receipt or reference by itself does not activate a plan. Paystack is temporarily disabled. Do not send passwords, OTPs, wallet seed phrases or private keys to the assistant. For account-specific support contact michaelelvistito@gmail.com."),
("cybersecurity foundations", "Cybersecurity is the practice of protecting systems, networks, applications and information from unauthorised access, disruption or alteration. Start with the CIA triad: confidentiality (only authorised people can read data), integrity (data stays correct) and availability (systems remain usable). Learn identity and access management, asset inventory, secure configuration, patching, backups, logging, network segmentation and incident response. A threat is a possible cause of harm; a vulnerability is a weakness; an exploit uses a weakness; risk combines likelihood and impact. Use defence in depth rather than relying on one product."),
("networking tcp ip", "Networking foundation: an IP address identifies a network interface; a port identifies a service endpoint on a host. TCP is connection-oriented and provides ordered reliable delivery; UDP is connectionless and has lower protocol overhead. A subnet/prefix defines the network portion of an address. A router moves packets between networks; a switch forwards frames within a LAN; DNS maps names to records; DHCP leases network configuration. Learn IPv4/IPv6, CIDR, ARP, ICMP, routing, NAT, VLANs, TCP handshake, TLS and common ports."),
("ports services", "Common ports: 20/21 FTP (legacy, unencrypted unless protected); 22 SSH; 23 Telnet (insecure); 25 SMTP; 53 DNS; 80 HTTP; 110 POP3; 123 NTP; 143 IMAP; 443 HTTPS; 445 SMB; 465/587 mail submission; 993 IMAPS; 995 POP3S; 3306 MySQL; 3389 RDP; 5432 PostgreSQL; 5900 VNC; 6379 Redis; 8080 alternate HTTP. A port being open only means something accepted a connection; it does not prove a vulnerability. Verify service identity and exposure."),
("reconnaissance osint", "Reconnaissance collects information before an assessment. Passive reconnaissance uses public sources without directly probing the target; active reconnaissance sends queries or traffic to the target and needs explicit scope/permission. Document domain ownership, DNS records, subdomains, certificates, public technology indicators and exposed services. Validate findings, record timestamps and sources, minimise collection of personal data, and do not treat an exposed hostname as proof of a weakness."),
("nmap", "Nmap is a network discovery and service-auditing tool. Begin only with an owned or explicitly authorised target. Useful concepts: `nmap -sn <scope>` host discovery; `nmap -sT <host>` TCP connect scan; `sudo nmap -sS <host>` SYN scan where permitted; `nmap -sV <host>` service/version detection; `nmap -p 22,80,443 <host>` selected ports; `nmap -p- <host>` all TCP ports; `nmap -oN scan.txt <host>` save normal output. `-O` attempts OS detection and is not a port option. `open`, `closed` and `filtered` describe scan observations, not security verdicts. Avoid aggressive scripts or broad scans without written scope."),
("web security http", "HTTP is a request/response protocol. A request includes method, path, headers and sometimes a body. Responses include status, headers and content. 2xx generally means success; 3xx redirection; 4xx client/request issue; 5xx server issue. HTTPS protects traffic with TLS. Review security headers such as Content-Security-Policy, Strict-Transport-Security, X-Content-Type-Options and frame-ancestors/X-Frame-Options. A missing header is context-dependent and not automatically an exploitable vulnerability."),
("owasp top 10", "OWASP Top 10 is an awareness document for major web application risk categories. Study broken access control, cryptographic failures, injection, insecure design, security misconfiguration, vulnerable/outdated components, identification/authentication failures, software/data integrity failures, security logging/monitoring failures and SSRF (the exact categories vary by edition). Mitigations include server-side authorisation checks, parameterised queries, output encoding, secure defaults, dependency management, strong session handling and tested logging."),
("sql injection", "SQL injection occurs when untrusted input changes the structure of a database query. Defend with parameterised queries/prepared statements, least-privileged database accounts, safe ORM use, input validation and error handling that does not expose internals. Do not rely on blacklist filters. Test only in a deliberately vulnerable lab or with written authorisation; never extract or alter real user data."),
("cross site scripting xss", "Cross-site scripting (XSS) occurs when attacker-controlled content executes as script in another user's browser. Types include stored, reflected and DOM-based XSS. Defences: context-aware output encoding, safe templating, sanitisation with a well-maintained allowlist library when HTML is intentionally allowed, Content Security Policy as defence-in-depth, and avoiding dangerous DOM sinks. HttpOnly cookies reduce cookie theft via JavaScript but do not fix XSS itself."),
("authentication sessions", "Authentication establishes who a user is; authorisation decides what they may do. Use modern password hashing (Argon2id, scrypt or bcrypt with suitable parameters), MFA, rate limits, secure recovery, least privilege and server-side access checks. Session cookies should normally use Secure, HttpOnly and an appropriate SameSite setting; rotate session identifiers after login/privilege changes and expire sessions. Never log passwords, OTPs, recovery codes or session tokens."),
("burp suite zap", "Burp Suite and OWASP ZAP are web application testing proxies. They let an authorised tester inspect and replay HTTP requests, understand cookies/headers, map application routes and test input handling. Start with passive observation and a test account. Keep scope restricted to approved hosts; disable active scanning unless expressly authorised. A proxy finding is a lead to validate, not proof by itself."),
("metasploit", "Metasploit is a penetration-testing framework with modules for auxiliary checks, exploits, payloads and post-exploitation. Use it only in a lab or under explicit written authorisation. Understand module options, target compatibility, impact and cleanup before running anything. Prefer safe validation and document evidence; do not launch payloads against third-party systems."),
("wireshark", "Wireshark captures and analyses network packets. Learn capture vs display filters, Ethernet/IP/TCP/UDP, DNS, TLS handshakes, retransmissions, latency and protocol conversations. Example display filters include `dns`, `tcp.port == 443`, `ip.addr == 192.0.2.10` and `http`. HTTPS content is encrypted; captures usually reveal metadata unless decryption keys are deliberately configured. Protect packet captures because they may contain personal or confidential data."),
("linux kali", "Kali Linux is a Debian-based distribution for security testing. Learn shell navigation (`pwd`, `ls`, `cd`), files (`cp`, `mv`, `cat`, `less`), permissions (`chmod`, `chown`), processes (`ps`, `top`), networking (`ip addr`, `ip route`, `ss -tulpn`), package updates (`sudo apt update && sudo apt full-upgrade`) and logs. Understand commands before running them; avoid piping untrusted remote scripts into a root shell. In VirtualBox NAT, a guest address such as 10.0.2.15 is commonly a private VM address."),
("dns whois", "DNS records: A maps a name to IPv4; AAAA to IPv6; CNAME aliases; MX identifies mail exchangers; NS identifies authoritative name servers; TXT carries text such as SPF/verification; CAA restricts certificate authorities; PTR supports reverse lookup; SOA describes zone metadata. WHOIS/RDAP provides domain registration data where available, but privacy redaction is common. DNSSEC adds authenticity validation; it does not encrypt DNS. Use more than one resolver when investigating inconsistent answers."),
("tls certificates", "TLS provides encryption, integrity and server authentication. Check certificate hostname/SAN, validity dates, chain, trusted issuer, protocol versions and renewal. A certificate being present does not guarantee the whole application is secure. Prefer current TLS configurations and disable obsolete protocols/ciphers. HSTS tells browsers to use HTTPS after policy is learned; deploy carefully with valid HTTPS across included subdomains."),
("vulnerability management cve cvss", "A CVE identifier names a publicly recorded vulnerability; it does not by itself say whether a specific asset is affected. Confirm product, version, configuration, exposure and vendor advisory. CVSS estimates technical severity, not complete business risk. Prioritise internet exposure, exploit availability, known exploitation, asset criticality and compensating controls. Patch, mitigate, retest and document. CPE/product matching can be imperfect."),
("incident response", "A practical incident-response lifecycle: prepare; identify and analyse; contain; eradicate; recover; then conduct lessons learned. Preserve evidence, record timestamps/time zones, isolate affected systems proportionately, protect backups and credentials, notify the right internal/legal/regulatory contacts, and avoid destructive cleanup before evidence is preserved. Rotate secrets from a trusted device after containment."),
("malware ransomware", "Malware includes trojans, worms, viruses, spyware, rootkits and ransomware. Defences include patching, least privilege, application control, endpoint detection, email/web filtering, network segmentation, MFA and offline/immutable backups. For suspected ransomware, isolate affected systems from networks, preserve evidence, activate incident response and restore only from verified clean backups. Do not execute unknown samples on a normal workstation."),
("cloud security", "Cloud security responsibilities are shared between provider and customer. Secure identity first: MFA, least privilege, short-lived credentials and audited role assignments. Protect storage from public exposure, encrypt data, segment networks, centralise logs, scan images/dependencies, manage secrets in a vault and continuously review configuration. Understand the exact service model (IaaS/PaaS/SaaS) and responsibility boundary."),
("cryptography", "Cryptography concepts: encryption is reversible with the correct key; hashing is designed to be one-way; a MAC authenticates data with a shared secret; digital signatures provide integrity and origin authentication. Symmetric encryption uses a shared key; public-key cryptography uses a key pair. Use vetted libraries and authenticated encryption such as AES-GCM or ChaCha20-Poly1305; do not invent algorithms or reuse nonces where prohibited."),
("secure coding", "Secure coding practices: validate inputs by type/length/range; encode outputs for their context; use parameterised database queries; enforce authorisation on the server for every object/action; protect CSRF-sensitive state changes; use safe file handling; avoid secrets in source control; pin and update dependencies; handle errors safely; write security tests; review changes and log security events without logging secrets."),
("soc siem", "A Security Operations Centre (SOC) monitors and investigates security events. A SIEM aggregates logs from endpoints, identity, firewalls, DNS, cloud and applications, then correlates them into alerts. Analysts triage severity, validate evidence, scope affected assets, investigate timelines, contain threats and document outcomes. Alert severity is a prioritisation signal, not proof of compromise; tune detections to reduce false positives."),
("threat intelligence mitre attack", "MITRE ATT&CK is a knowledge base of adversary tactics and techniques observed in real-world activity. Tactics describe the adversary's goal; techniques describe how it may be achieved. Use ATT&CK to map detections, identify telemetry gaps, plan purple-team exercises and communicate behaviours. It is not a checklist of vulnerabilities and a technique mapping does not prove an intrusion occurred."),
("email security phishing", "Email security includes SPF (authorised sending hosts), DKIM (cryptographic message signing) and DMARC (policy/reporting based on domain alignment). These controls reduce spoofing but do not stop every phishing message. Use MFA, secure mail gateways, user reporting, attachment/link controls and clear incident procedures. Verify unusual payment or credential requests through a separate trusted channel."),
("mobile security", "Mobile security basics: keep OS/apps updated, install from trusted stores, review permissions, use screen locks and device encryption, enable remote wipe where appropriate, avoid unknown profiles/APKs, protect backups and use MFA. For enterprise devices, use mobile device management and separate work data. Treat SMS codes as vulnerable to SIM-swap and phishing; prefer phishing-resistant MFA when available."),
("digital forensics", "Digital forensics aims to preserve and analyse evidence reliably. Document authority and scope, maintain chain of custody, capture hashes, preserve originals, work on verified copies, record tools/versions and timestamps, and avoid altering evidence. Memory, disk, network and cloud evidence each have different volatility and collection requirements. Follow applicable law and organisational policy."),
("privacy governance", "Security governance connects controls to business risk, law and accountability. Maintain an asset inventory, data classification, retention rules, access reviews, vendor assessments, incident plans, business continuity and tested recovery. Collect only data needed for a defined purpose, limit access, protect it and honour applicable privacy obligations."),
("api security", "API security: authenticate clients appropriately, authorise every object and function server-side, validate schemas and sizes, rate-limit, use TLS, protect secrets, avoid verbose errors, inventory endpoints, monitor abuse and test version/deprecation controls. BOLA/IDOR occurs when a user can access another user's object because object-level permission checks are missing. Never trust client-side role flags."),
("container kubernetes", "Container security: use minimal trusted base images, scan dependencies, run as non-root, drop unnecessary capabilities, use read-only filesystems where practical, avoid privileged containers, protect registries and secrets, sign/verify images and monitor runtime behaviour. In Kubernetes, apply RBAC least privilege, network policies, pod security controls, admission policies and audit logging."),
("sqlmap", "sqlmap automates detection and validation of SQL injection in authorised test environments. Start by understanding the request, parameter and application behaviour; use a deliberately vulnerable lab or written scope. Prefer low-impact detection settings, avoid data extraction or destructive options, and capture reproducible evidence. Defend with parameterised queries, least privilege and safe error handling."),
("gobuster directory enumeration", "Gobuster is used for authorised discovery of directories, files, DNS names or virtual hosts. Directory enumeration can create substantial traffic and may expose sensitive paths; obtain approval, set sensible rate limits and avoid brute forcing third-party systems. Treat discovered paths as leads and verify access controls without accessing private data."),
("nikto web server scanner", "Nikto performs web-server checks for potentially risky files, outdated components and configuration issues. Its results often include false positives and informational findings. Use it only on approved hosts, validate each result manually and avoid interpreting a banner or missing file as proof of compromise."),
("searchsploit exploit database", "SearchSploit is a local search interface for the Exploit-DB archive. Use it to research whether public proof-of-concept material exists for a product/version. Read the advisory and source carefully, confirm affected versions and prerequisites, and do not run exploit code against systems without explicit authorisation. A matching search result is not proof that a target is vulnerable."),
("password auditing john hashcat", "John the Ripper and Hashcat are password-auditing tools. Use them only with hashes you own or are authorised to audit. Understand hash formats, salts, work factors and legal/privacy requirements. Defences include unique long passwords, MFA, breached-password screening, rate limiting and modern password hashing such as Argon2id, scrypt or bcrypt."),
("python programming", "Python is useful for security automation, parsing logs, calling APIs and writing small assessment helpers. Learn variables, data structures, functions, exceptions, modules, virtual environments, HTTP requests and JSON. Validate input, set request timeouts, handle errors, avoid hard-coded secrets, pin dependencies and write tests. Never execute untrusted code simply because an online answer recommends it."),
("firewalls ids ips", "A firewall enforces traffic policy between networks or hosts. IDS detects suspicious activity; IPS can actively block it. Use default-deny where practical, restrict management interfaces, segment critical systems, log meaningful events and review rules regularly. Detection quality depends on good telemetry, tuning and response processes."),
("zero trust", "Zero Trust is an architectural approach that avoids implicit trust based solely on network location. Authenticate and authorise explicitly, apply least privilege, verify device and session context, segment access, monitor continuously and assume a breach is possible. It is a programme of identity, device, network and data controls—not a single product."),
("wireless wifi security", "Secure Wi-Fi with WPA3 where supported (or WPA2-AES on legacy devices), strong unique passphrases, updated router firmware, disabled WPS where appropriate, guest-network isolation and a changed admin password. Avoid exposing router administration to the internet. Only assess wireless networks you own or have explicit permission to test."),
("git github secrets", "For secure Git/GitHub workflows, never commit API keys, passwords, private keys, tokens or production database credentials. Use environment variables or a secrets manager, restrict repository access, enable MFA, review dependencies and rotate any secret that was exposed. Add secret scanning and remove secrets from history where necessary; deleting a file in a later commit does not invalidate a leaked credential."),
("career learning", "A practical beginner roadmap: 1) networking and TCP/IP; 2) Linux command line; 3) HTTP/DNS/TLS; 4) Python basics and Git; 5) Nmap and Wireshark in your own lab; 6) web security fundamentals and OWASP; 7) log analysis and incident response; 8) write clear reports with scope, evidence, impact, limitations and remediation. Build a legal home lab and a portfolio of reproducible, non-destructive assessments."),
]

SOURCES = [
("NIST National Vulnerability Database", "https://nvd.nist.gov/"),
("CISA Known Exploited Vulnerabilities Catalog", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"),
("MITRE ATT&CK", "https://attack.mitre.org/"),
("OWASP", "https://owasp.org/"),
("CIS Controls", "https://www.cisecurity.org/controls"),
("NIST Cybersecurity Framework", "https://www.nist.gov/cyberframework"),
("FIRST CVSS", "https://www.first.org/cvss/"),
("PortSwigger Web Security Academy", "https://portswigger.net/web-security"),
]


def _tokens(s):
    return set(re.findall(r"[a-z0-9+#.-]{2,}", (s or "").lower()))


def _topic_matches(query):
    q = _tokens(query)
    ranked = []
    for title, body in TOPICS:
        keys = _tokens(title)
        score = len(q & keys)
        # Related technical vocabulary can identify a topic even if the title differs.
        body_keys = _tokens(body)
        score += min(4, len(q & body_keys) // 5)
        if score:
            ranked.append((score, title, body))
    ranked.sort(reverse=True)
    return ranked[:3]


def _live_cve(query):
    match = re.search(r"CVE-\d{4}-\d{4,7}", query, re.I)
    if not match:
        return None
    cve = match.group(0).upper()
    try:
        r = requests.get("https://services.nvd.nist.gov/rest/json/cves/2.0", params={"cveId": cve}, timeout=8, headers={"User-Agent": "CyberLord-Assistant/1.0"})
        r.raise_for_status()
        items = r.json().get("vulnerabilities", [])
        if not items:
            return f"Live NVD lookup: I couldn't find {cve} in the current response. Check the identifier and try the NVD website."
        c = items[0].get("cve", {})
        desc = next((x.get("value", "") for x in c.get("descriptions", []) if x.get("lang") == "en"), "No English description returned.")
        metrics = c.get("metrics", {})
        cvss = "CVSS score not present in the returned record."
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                data = metrics[key][0].get("cvssData", {})
                cvss = f"CVSS {data.get('version', '')}: {data.get('baseScore', 'n/a')} ({data.get('baseSeverity', 'severity not supplied')})"
                break
        return f"LIVE NIST NVD RESULT — {cve}\nStatus: {c.get('vulnStatus', 'not specified')}\n{desc[:1100]}\n{cvss}\nPublished: {c.get('published', 'not listed')} | Last modified: {c.get('lastModified', 'not listed')}\n\nThis record does not prove your system is affected. Match the exact product, version, configuration and vendor advisory before deciding what to patch. Source: https://nvd.nist.gov/vuln/detail/{cve}"
    except Exception:
        return "I couldn't reach the live NIST NVD service just now. The connection may be unavailable; try again later or search the identifier at https://nvd.nist.gov/."


def _live_kev(query):
    try:
        r = requests.get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", timeout=8, headers={"User-Agent": "CyberLord-Assistant/1.0"})
        r.raise_for_status()
        vulns = r.json().get("vulnerabilities", [])
        if not vulns:
            return "The CISA feed responded but did not contain vulnerability entries."
        chosen = vulns[-8:]
        lines = ["LIVE CISA KNOWN EXPLOITED VULNERABILITIES FEED — 8 recent catalog entries:"]
        for v in reversed(chosen):
            lines.append(f"• {v.get('cveID','CVE unknown')} — {v.get('vendorProject','')} {v.get('product','')} | Added {v.get('dateAdded','')} | Due {v.get('dueDate','')}")
        lines.append("\nCatalog inclusion means CISA lists evidence of exploitation in the wild; it does not mean every environment is affected. Check asset inventory and vendor guidance. Source: https://www.cisa.gov/known-exploited-vulnerabilities-catalog")
        return "\n".join(lines)
    except Exception:
        return "I couldn't reach CISA's live Known Exploited Vulnerabilities feed right now. Visit https://www.cisa.gov/known-exploited-vulnerabilities-catalog and try again later."


def answer(query, history=None):
    q = (query or "").strip()
    low = q.lower()
    if not q:
        return "Ask me a cybersecurity, technology or CyberLord question and I'll help you work through it."
    live = _live_cve(q)
    if live:
        return live
    if any(x in low for x in ("latest exploited", "known exploited", "cisa kev", "recent kev", "latest cve feed")):
        return _live_kev(q)
    if any(x in low for x in ("hello", "hi", "hey", "good morning", "good evening")) and len(q.split()) < 6:
        return "Hello! 👋 I'm CyberLord Intelligence Assistant. I can explain cybersecurity concepts, tools, networks, web security, cloud, incident response, and help interpret scan results. I can also look up individual CVEs in the live NIST NVD and recent entries in CISA's exploited-vulnerability catalog when those services are reachable. What are you investigating today?"
    if any(x in low for x in ("cyberlord plan", "subscription", "pro plus", "payment", "paystack", "bank transfer", "usdt")):
        return ("CYBERLORD ACCOUNT & PLANS\nPro: ₦6,300 or 4.50 USDT for 30 days. Pro Plus: ₦12,600 or 9.00 USDT for 30 days. USDT networks supported by the current dashboard are TRC20 and BEP20; Paystack is temporarily disabled.\nA receipt, screenshot or bank reference alone does not activate a subscription. Payment must be independently verified by the server-side payment process. I cannot approve payments or change accounts. Never share passwords, OTPs, private keys or seed phrases in chat. For account-specific help contact michaelelvistito@gmail.com.")
    matches = _topic_matches(q)
    if matches:
        out = ["CYBERLORD KNOWLEDGE RESPONSE", "Here's a structured explanation based on the closest matching knowledge areas:\n"]
        for i, (_, title, body) in enumerate(matches, 1):
            out.append(f"{i}. {title.title()}\n{body}")
        out.append("\nPRACTICAL NEXT STEP\nTell me your operating system, tool, exact error or sanitized scan output and I can make the explanation more specific. Remove passwords, tokens, personal data and private keys before sharing.")
        out.append("\nREFERENCE LIBRARY\n" + "\n".join(f"• {name}: {url}" for name, url in SOURCES[:5]))
        return "\n\n".join(out)
    return ("I can help, but I don't want to invent an answer. I have built-in guidance across networking, Linux/Kali, Nmap, web security, OWASP, vulnerabilities, CVEs, cloud, cryptography, SOC operations, incident response, forensics, secure coding and more.\n\nCould you narrow the question to the system, tool, error message or concept? You can paste sanitized output and I'll explain it step by step. For current vulnerability records, ask about a specific CVE (for example, CVE-2024-XXXX) or ask for the latest CISA known-exploited entries.\n\nFor safety, I can assist with authorised testing and defensive learning, not unauthorised access or harm.")
