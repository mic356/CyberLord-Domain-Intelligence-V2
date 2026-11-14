"""Free CyberLord knowledge assistant with curated cybersecurity guidance and public vulnerability lookups.
No paid LLM or API key is required. External lookups use public NVD/CISA feeds when reachable.
ai-training-2 adds: live weather (Open-Meteo, keyless), headline news (Google News RSS,
keyless), image search (Wikimedia/Wikipedia, keyless), a much bigger general-knowledge
built-in brain, typo tolerance, and live-aware routing so the main dashboard persona
answers what it can and only falls back when nothing can answer.
"""
import json as _json
import re
import requests
from datetime import datetime, timezone, timedelta

# Curated built-in knowledge assistant for CyberLord AI.
# This is NOT a live LLM on the free path. It is a hand-written answer base, plus
# public lookups when reachable (NIST NVD, CISA KEV). If a Gemini key is set, the
# app route may call Gemini and only fall back to this base when Gemini is absent or fails.
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


# General cybersecurity questions: what is X, how do I harden things, career advice.
("what is phishing", "PHISHING: phishing is a social-engineering attack that tricks people into revealing credentials, financial data, or installing malware. It usually arrives as email, SMS (smishing), messages, or a fake website that looks like a bank, school, or delivery service. Common signs: urgent threats, unexpected attachments or links, spelling mistakes, sender address that almost matches, and requests to bypass normal process. Defences: check the sender real address, hover links before clicking, go to the site directly instead of using the link, enable MFA, and report suspected phishing to your provider or IT team. Never log in through a link in an unsolicited message."),
("server load", "SERVER LOAD: server load is how busy a server is right now. The 1-minute, 5-minute and 15-minute load numbers show roughly how many processes can run or are waiting. One number per CPU core is a rough guide: a load equal to the core count means the server is about fully busy, and a load well above the core count usually means processes are queuing. Check whether the load comes from CPU work or from processes stuck waiting on disk or network. Useful checks on Linux are uptime, top or htop, vmstat, iostat and free. High load is not automatically an attack: traffic spikes, runaway jobs, memory pressure and slow storage can all cause it. For security, watch for unexpected processes, new admin accounts, odd outbound connections and changed files, and correlate load spikes with login and web logs. Defend with patching, least privilege, rate limiting, autoscaling or extra capacity, and alerts on sustained load instead of one-minute spikes."),
("how do i harden a server", "SERVER HARDENING BASICS: patch OS and services promptly; create least-privilege accounts and remove default passwords; disable unused services and ports; restrict SSH/RDP to VPN or allowlists and require MFA; configure a host firewall with deny-by-default; enable automatic security updates; centralise logs and test backups; run services as non-root; set file permissions carefully; disable password auth for SSH keys where possible. Validate changes in a test environment first and document each step."),
("what is a vulnerability", "A vulnerability is a weakness in software, configuration, or process that an attacker may be able to abuse. Examples: outdated software with a known bug, weak or reused passwords, missing access controls, insecure defaults, exposed admin panels. A vulnerability is not the same as an exploit (code that uses it) or a compromise (evidence it was used). Good practice: keep an asset inventory, patch regularly, harden configurations, and scan only systems you own or are authorized to test."),
("difference between vulnerability exploit and threat", "THREAT vs VULNERABILITY vs EXPLOIT: a threat is a possible source of harm (for example, a criminal group or a storm). A vulnerability is a weakness that could be used (an unpatched bug). An exploit is the actual method or code that takes advantage of it. Risk combines the likelihood of a threat using a vulnerability and the impact if it succeeds. Reducing risk can mean patching the vulnerability, adding controls that make exploitation harder, or reducing the impact (backups, segmentation)."),
("what is owasp top 10", "OWASP TOP 10: the Open Worldwide Application Security Project publishes common web application risks. The 2021 edition lists: Broken Access Control, Cryptographic Failures, Injection, Insecure Design, Security Misconfiguration, Vulnerable and Outdated Components, Identification and Authentication Failures, Software and Data Integrity Failures, Security Logging and Monitoring Failures, and Server-Side Request Forgery. Each category is a starting point for secure design, code review, and testing, not a checklist that guarantees safety."),
("owasp top 10 explained", "OWASP Top 10 explained in plain terms: 01 Broken Access Control = users can see or change things they should not. 02 Cryptographic Failures = weak encryption, leaked keys, or sensitive data sent insecurely. 03 Injection = attacker input becomes a command or query. 04 Insecure Design = the design itself is flawed. 05 Security Misconfiguration = default, debug, or overly permissive settings. 06 Vulnerable and Outdated Components = old libraries with known bugs. 07 Authentication Failures = weak logins and sessions. 08 Integrity Failures = untrusted updates or data. 09 Logging Failures = no useful audit trail. 10 SSRF = the server is tricked into requesting internal addresses. Start with access control, injection defences, and patching."),
("what is cve basics", "CVE BASICS: CVE (Common Vulnerabilities and Exposures) is a shared catalogue that gives each public vulnerability a stable ID such as CVE-2024-12345. The ID alone does not tell you much, you also need the description, affected products and versions, severity (CVSS), and the vendor fix. Ask CyberLord AI to look up a specific CVE and it can query the live NIST NVD when reachable. Always match the exact product and version before acting."),
("what is cvss", "CVSS (Common Vulnerability Scoring System) is a standard way to score how severe a vulnerability is on a 0 to 10 scale, based on things like attack complexity, privileges needed, and impact on confidentiality, integrity, and availability. It helps prioritise, but it is a technical severity score, not a complete business risk score. A medium CVSS on an internet-facing system may matter more than a high CVSS on an isolated test box."),
("how do i start a cybersecurity career", "STARTING A CYBERSECURITY CAREER (beginner, Nigeria-friendly): 1) Master networking basics (TCP/IP, DNS, HTTP) and Linux command line. 2) Learn how the web works and the OWASP Top 10. 3) Build a home lab and practise Nmap and Wireshark on systems you own. 4) Learn a scripting language (Python). 5) Do hands-on labs and write up what you learned. 6) Consider entry-level certs later such as CompTIA Security+, Network+ or Linux+. 7) Apply for junior SOC, IT helpdesk, or junior security roles to build experience. Consistency and a portfolio of lab write-ups matter more than any single certificate at the start."),
("what is the difference between ethical hacker and penetration tester", "ETHICAL HACKER vs PENETRATION TESTER: a penetration tester is a type of ethical hacker hired with written permission to test a system and report weaknesses. Ethical hacking is the broader idea of testing with permission. Always get explicit, written scope before any testing. Practice in labs and bug bounty programmes that allow it. Testing a system you do not own without permission is illegal in most countries, including Nigeria."),
("how do i practice cybersecurity legally", "LEGAL PRACTICE ROUTES: build a home lab (VirtualBox + Kali or Ubuntu VMs), use deliberately vulnerable apps like DVWA or Juice Shop, join platforms that host legal lab challenges, read program rules on bug bounty sites and stay inside scope, and only test systems you own or have written permission for. Document what you did and what you learned; that is your portfolio."),
("what is malware", "MALWARE is malicious software: viruses, worms, trojans, ransomware, spyware, and rootkits. It gets in through phishing, unsafe downloads, vulnerable software, or USB devices. Protection: keep software updated, use reputable endpoint protection, avoid unknown attachments and links, use least-privilege accounts, and keep offline or versioned backups so ransomware cannot destroy everything. If you suspect infection, disconnect the device from the network and get help from IT before trying to clean it yourself."),
("what is ransomware", "RANSOMWARE encrypts your files and demands payment for a key, often with threats to leak data. Common entry points are phishing attachments, exposed remote access, and unpatched software. Prevention: patch promptly, enable MFA, segment networks, control email attachments, and keep tested backups that attackers cannot reach. If hit: isolate affected machines, preserve evidence, follow your incident response plan, and contact authorities. Paying is not recommended and is not a guarantee of recovery."),
("what is social engineering", "SOCIAL ENGINEERING means attacking people rather than technology: tricking someone into revealing passwords, approving a payment, or installing software. Tactics include phishing, pretext calls, urgency, and authority claims (for example, someone claiming to be from IT). Defence is process: verify requests through a separate trusted channel, never share codes or passwords, and train staff to slow down and verify. Technical controls help, but good habits stop most attacks."),
("what is vpn and when should i use it", "A VPN (Virtual Private Network) encrypts traffic between your device and a VPN server and hides your IP address from local networks. It is useful on public Wi-Fi and for remote work. It does not make you anonymous to the VPN provider, does not stop malware, and does not prevent phishing. Choose a reputable provider, keep it updated, and still use HTTPS and MFA."),
("what is two factor authentication 2fa mfa", "Two-factor authentication (2FA) and MFA (multi-factor authentication) add a second check besides your password, such as an app code, hardware key, or a push approval. It blocks most account takeover attacks even if your password leaks. Use an authenticator app or hardware key where possible, keep backup codes safe, and never share a code with anyone, including someone claiming to be support."),
("what is a firewall", "A firewall filters network traffic based on rules, allowing safe traffic and blocking the rest. There are host firewalls (on a device) and network firewalls (between networks). Good practice: deny by default, open only what is needed, restrict admin panels, keep rules documented and reviewed, and log what is blocked. A firewall reduces exposure but does not fix vulnerable software."),
("what is endpoint protection edr", "ENDPOINT PROTECTION is software on laptops, servers, and phones that detects and blocks malware, ransomware behaviour, and suspicious processes. Modern EDR (endpoint detection and response) also records activity so analysts can investigate. It works best alongside patching, least privilege, MFA, and backups, not as a replacement for them."),
("what is the cia triad", "THE CIA TRIAD: Confidentiality (only authorized people can read data), Integrity (data stays correct and unaltered), Availability (systems remain usable when needed). Most security decisions balance these three. For example, encryption protects confidentiality, checksums protect integrity, and backups plus redundancy protect availability."),
("what is defence in depth", "DEFENCE IN DEPTH means stacking multiple controls so that if one fails, others still protect you. Example for a website: patching, least privilege, MFA, a web application firewall, input validation, logging, and backups. No single tool makes you safe; layers of simple, well-maintained controls do."),
("what is a zero day vulnerability", "A ZERO-DAY is a vulnerability that is unknown to the vendor and may already be exploited, with no official patch yet. Because there is no fix, defences are mitigations: reduce exposure, patch quickly when a fix appears, use segmentation and monitoring, and follow vendor advisories. This is why keeping systems updated and watching advisories matters."),
("what is a bug bounty", "A BUG BOUNTY is a program where a company invites researchers to find and report vulnerabilities in scope, usually for a reward. Rules are strict: only test what is listed, do not disrupt service, handle data carefully, and report responsibly. Start with reading the program policy carefully and practising in labs first."),
("how do i report a vulnerability responsibly", "RESPONSIBLE DISCLOSURE: tell the owner privately, give reasonable time to fix, include clear steps to reproduce and the impact, avoid accessing or spreading others data, and do not publish proof-of-concept exploits before the vendor agrees. Many sites publish a security contact or use security.txt."),
("what is a strong password", "A STRONG PASSWORD is long, unique, and hard to guess. A passphrase of 4 to 5 random words is easier to remember and harder to crack than a short complex string. Use a password manager, never reuse passwords across sites, and turn on MFA. Change a password immediately if a site reports a breach or you suspect phishing."),
("what is a password manager", "A PASSWORD MANAGER stores encrypted passwords and can generate strong unique ones for each site. It reduces reuse and phishing risk because you fill credentials inside the app rather than typing them anywhere. Choose a reputable one, protect the master password, and store recovery codes safely."),
("what is encryption explained simply", "ENCRYPTION scrambles information so only someone with the key can read it. In transit, TLS (https) encrypts web traffic. At rest, full-disk and database encryption protect stored data. Encryption protects against eavesdropping and theft of devices, but it does not stop phishing, malware on an unlocked device, or someone you willingly give the key to."),
("what is https and tls", "HTTPS is HTTP running over TLS. TLS encrypts traffic, authenticates the server using a certificate, and protects integrity in transit. Look for the padlock and a valid certificate, but remember a padlock only proves the connection is encrypted, not that the site is honest or safe. Keep certificates valid and renew them before expiry."),
("what is dns explained", "DNS (Domain Name System) translates names like cyberlord.name.ng into IP addresses. Records include A/AAAA (addresses), CNAME (alias), MX (mail), TXT (verification and SPF), and NS (name servers). DNS itself is not encrypted by default; DNS-over-HTTPS and DNSSEC add privacy and authenticity in different ways. If a site will not load, DNS is a good place to look first."),
("what is http vs https", "HTTP sends web traffic unencrypted; HTTPS encrypts it with TLS. On HTTP, anyone on the path can read or modify traffic. On HTTPS, the connection is encrypted and the server is authenticated by certificate. Always prefer HTTPS, and treat a padlock as necessary but not sufficient for trust; phishing sites can have valid certificates too."),
("what is an ip address ipv4 ipv6", "An IP address identifies a device or service on a network. IPv4 uses 32 bits (for example 192.168.1.10) and IPv6 uses 128 bits, giving far more addresses and built-in support for modern features. You may see private ranges like 192.168.x.x, 10.x.x.x, and 172.16-31.x.x that are not routable on the public internet."),
("what is nat", "NAT (Network Address Translation) lets many private devices share one public IP by rewriting addresses and ports. It is common in home and office routers. NAT helps with address shortage and hides internal structure, but it is not a security boundary by itself. Do not rely on NAT instead of a firewall and patching."),
("what is subnetting cidr", "A SUBNET is a smaller part of a network. CIDR notation such as 192.168.1.0/24 means the first 24 bits identify the network and the rest identify hosts, giving 256 addresses in that block. /25 gives 128, /26 gives 64, /16 gives 65,536. Subnetting lets you segment networks so problems and attacks stay contained."),
("what is tcp vs udp", "TCP is connection-oriented, ordered, and reliable, used by web, email, and file transfers. UDP is connectionless and faster with no delivery guarantee, used by DNS, streaming, and gaming. Choosing between them is about reliability versus speed and overhead, not about security. Neither encrypts traffic by itself."),
("what is a port in networking", "A PORT is a numbered endpoint that identifies a service on a host, combined with an IP address. Common ones: 22 SSH, 53 DNS, 80 HTTP, 443 HTTPS, 25 SMTP. An open port means something accepted a connection; it does not prove a vulnerability. Only open ports you need and protect the service with updates and authentication."),
("what is ssh", "SSH (Secure Shell) is an encrypted protocol for logging into and managing Linux and Unix servers. Use key-based login, disable password and root login where possible, restrict access to VPN or allowlists, and enable MFA. Keep it patched like any other service."),
("what is linux", "LINUX is a family of open-source operating systems used for servers, desktops, and embedded devices. The command line is its strength: files, permissions, processes, networking, and logs are all managed from the terminal. If you are learning security, Linux basics (the shell, permissions, package updates, and journal logs) are essential."),
("linux basics for beginners", "LINUX BASICS: navigate with cd, ls, pwd; read files with cat, less, head; manage files with cp, mv, mkdir, rm; check permissions with ls -l and change with chmod, chown; see processes with ps, top; check network with ip addr, ip route, ss; read logs with journalctl and files in /var/log; update with sudo apt update and sudo apt full-upgrade on Debian-based systems. Learn the man pages (man <command>) as you go."),
("what is a rootkit", "A ROOTKIT is malware designed to hide itself and give an attacker privileged access. It may hook system functions so files, processes, and network connections disappear from normal tools. Prevention is patching, least privilege, and endpoint protection. If you suspect one, treat the system as untrusted, preserve evidence, rebuild from known-good media, and rotate credentials."),
("what is a botnet", "A BOTNET is a network of compromised devices controlled by an attacker to send spam, launch DDoS attacks, mine cryptocurrency, or steal data. Devices are infected through weak passwords, unpatched software, and phishing. Defences are patching, unique passwords, MFA, and endpoint protection. Disposing of or disconnecting infected devices without cleaning them can spread the problem."),
("what is ddos attack", "A DDOS (distributed denial of service) attack floods a service with traffic so legitimate users cannot connect. It does not usually steal data; it disrupts availability. Defences include capacity planning, rate limiting, CDN and upstream filtering, and keeping services updated. For small sites, hosting providers and CDNs often provide DDoS protection."),
("what is a trojan", "A TROJAN is malware disguised as legitimate software. Unlike a virus it does not replicate itself; it tricks you into running it. It often arrives as a free download, a cracked tool, or a fake update. Only download software from official sources, verify signatures or hashes when available, and keep endpoint protection on."),
("what is steganography", "STEGANOGRAPHY hides data inside other data, such as embedding a message in an image or audio file. It is used for legitimate watermarking and also to conceal malware or stolen data. Detection looks for statistical anomalies and mismatched metadata. It is different from encryption, which scrambles data rather than hiding its existence."),
("what is cryptography hashes", "Cryptography basics: a HASH turns data into a fixed-size fingerprint (SHA-256 is common) and is used to verify file integrity. A MAC or digital signature proves data was not altered and (for signatures) who created it. Passwords should be stored with a slow salted hash such as Argon2id, scrypt, or bcrypt, never as plain text or fast hashes like MD5 or SHA-1."),
("what is a digital signature", "A DIGITAL SIGNATURE uses a private key to create a signature that anyone with the public key can verify. It proves the signer created it and that the data has not changed since. It is the basis of code signing, certificate signing, and document signing. Protect your private key like a password, ideally in a hardware token."),
("what is symmetric vs asymmetric encryption", "SYMMETRIC encryption uses one shared secret key for both encrypting and decrypting (for example AES). ASYMMETRIC uses a key pair: a public key encrypts and a private key decrypts, or the reverse for signatures (RSA, ECC). Modern systems combine them: asymmetric crypto exchanges a session key, then symmetric crypto does the bulk work."),
("what is tls handshake", "THE TLS HANDSHAKE is how a browser and server agree on a protocol, verify the server certificate, and create shared encryption keys. After the handshake, traffic is encrypted and authenticated. Problems usually show as certificate errors, expired certificates, or mismatched names, which you should investigate rather than click through."),
("what is a certificate authority", "A CERTIFICATE AUTHORITY (CA) is an organization trusted to issue digital certificates that bind a name to a public key. Browsers trust a set of root CAs; a site certificate chains up to one of them. Short-lived, automated certificates such as those from Let's Encrypt have made HTTPS the default."),
("what is a digital certificate", "A DIGITAL CERTIFICATE is a signed statement that binds a name or key to an owner, used for HTTPS server identity, code signing, and email signing. It has an expiry date and a chain of trust. An expired or mismatched certificate is a warning to investigate, not something to bypass on systems you care about."),
]

# --- General knowledge brain (main persona) -------------------------------------
# Stable facts, everyday how-tos and small talk. Main persona only; the tutor
# never uses this (it keeps its clever cyber redirect). Keep answers TRUE and
# in-house: anything time-sensitive belongs to the live collectors below or to
# Gemini grounding in app.py, never to a frozen number here.
GENERAL_TOPICS = [
    # capitals (exact-match-first style titles; matcher needs title overlap)
    ("capital of france", "Paris is the capital of France. France is in western Europe, and Paris sits on the River Seine in the north of the country. The Eiffel Tower and the Louvre are its landmarks."),
    ("capital of the usa", "Washington, D.C. is the capital of the United States. It is a federal district, not part of any state, and is home to the White House and the Capitol."),
    ("capital of japan", "Tokyo is the capital of Japan. It is one of the largest metropolitan areas in the world and is known for places like Shibuya, Asakusa's Senso-ji temple and the Skytree."),
    ("capital of nigeria", "Abuja is the capital of Nigeria. It is a planned federal capital territory in the centre of the country, while Lagos remains the largest city and economic hub."),
    ("capital of brazil", "Brasilia is the capital of Brazil. Rio de Janeiro is the better-known former capital, but the seat of government moved to Brasilia in 1960."),
    ("capital of canada", "Ottawa is the capital of Canada. Toronto is the country's largest city, but Ottawa holds the federal government."),
    ("capital of china", "Beijing is the capital of China. It is home to the Forbidden City, Tiananmen Square and the Great Wall (which begins just outside the city)."),
    ("capital of india", "New Delhi is the capital of India. It sits within the National Capital Territory of Delhi, in the north of the country."),
    ("capital of egypt", "Cairo is the capital of Egypt. The pyramids of Giza sit on its outskirts, and the River Nile runs through the city."),
    ("capital of kenya", "Nairobi is the capital of Kenya. It is the only capital in the world with a national park inside its city limits."),
    ("capital of ghana", "Accra is the capital of Ghana. It is the country's largest city and its main port on the Gulf of Guinea."),
    ("capital of south africa", "South Africa has three capitals: Pretoria is the administrative capital, Cape Town the legislative, and Bloemfontein the judicial. The seat of government most people mean is Pretoria (Tshwane)."),
    ("capital of the united kingdom", "London is the capital of the United Kingdom. It sits on the River Thames in the south-east of England."),
    ("capital of spain", "Madrid is the capital of Spain. It sits in the middle of the Iberian Peninsula and hosts the Prado Museum."),
    # science
    ("who wrote hamlet", "William Shakespeare wrote Hamlet. It is one of his tragedies, written around 1599-1600, about Prince Hamlet of Denmark."),
    ("who painted the mona lisa", "Leonardo da Vinci painted the Mona Lisa. It is held by the Louvre in Paris and is probably the most famous painting in the world."),
    ("what is photosynthesis", "Photosynthesis is how green plants make food: they use sunlight, water and carbon dioxide to produce sugars for energy, releasing oxygen as a by-product. It is why nearly all life on Earth has oxygen to breathe."),
    ("how many continents are there", "There are seven continents: Africa, Antarctica, Asia, Europe, North America, Australia (Oceania) and South America. Some lists combine Europe and Asia as Eurasia, which is why you will also see counts of six."),
    ("what is the largest planet", "Jupiter is the largest planet in our solar system. It is a gas giant more than eleven times Earth's diameter and has more than 90 known moons."),
    ("what is the boiling point of water", "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at standard sea-level pressure. At higher altitude, where pressure is lower, it boils at a lower temperature."),
    ("how many days are in a leap year", "A leap year has 366 days. The extra day is added to February, making it 29 days, and it happens in years divisible by 4, with the century rules (divisible by 400 stays a leap year)."),
    ("what is the speed of light", "The speed of light in a vacuum is 299,792,458 metres per second, about 300,000 kilometres per second. Nothing with mass can reach it."),
    ("what does dna stand for", "DNA stands for deoxyribonucleic acid. It is the molecule that carries genetic instructions in living things, structured as a double helix of two strands."),
    ("what is the powerhouse of the cell", "The mitochondria are called the powerhouse of the cell because they produce most of the cell's ATP, its usable energy currency, through cellular respiration."),
    ("who invented the telephone", "Alexander Graham Bell received the key patent for the telephone in 1876, though several inventors worked on speaking devices before him. The rivalry over the invention is one of the famous priority disputes in technology."),
    ("what gas do plants absorb", "Plants absorb carbon dioxide (CO2) from the air for photosynthesis. They release oxygen, which is why forests are sometimes called the lungs of the planet."),
    ("what is the longest river in the world", "The Nile is generally considered the longest river in the world at about 6,650 kilometres. The Amazon carries more water, which is why some measurements argue for it."),
    ("who discovered penicillin", "Alexander Fleming discovered penicillin in 1928 when he noticed mould killing Staphylococcus bacteria on a plate. Howard Florey, Ernst Chain and their team turned it into a usable medicine a decade later."),
    ("what is the largest ocean on earth", "The Pacific Ocean is the largest ocean on Earth. It covers more area than all land on the planet put together."),
    ("how many legs does a spider have", "Spiders have eight legs. That is one of the features that makes them arachnids, not insects (insects have six)."),
    ("what is the freezing point of water in celsius", "Water freezes at 0 degrees Celsius at standard pressure, which is 32 degrees Fahrenheit. Salts and impurities lower the freezing point."),
    ("what is the chemical symbol for gold", "The chemical symbol for gold is Au, from the Latin word 'aurum'. Its atomic number is 79."),
    ("how many states are in nigeria", "Nigeria has 36 states plus the Federal Capital Territory of Abuja, making 37 administrative units in total."),
    ("what is the tallest mountain in africa", "Mount Kilimanjaro is the tallest mountain in Africa at 5,895 metres. It is a dormant volcano in Tanzania, famous for its snow-capped peak near the equator."),
    ("what is the square root of 144", "The square root of 144 is 12, because 12 times 12 equals 144."),
    ("how many minutes are in 3 hours", "There are 180 minutes in 3 hours: 60 minutes per hour multiplied by 3."),
    ("what is 15 percent of 200", "15 percent of 200 is 30. Work it out as 0.15 times 200."),
    ("how many sides does a hexagon have", "A hexagon has six sides. A regular hexagon has all six sides equal and all angles 120 degrees."),
    ("what year did man land on the moon", "Astronauts first landed on the Moon in 1969, on NASA's Apollo 11 mission. Neil Armstrong and Buzz Aldrin walked on the surface while Michael Collins stayed in orbit."),
    ("who wrote the nigerian national anthem", "The current Nigerian national anthem, 'Nigeria, We Hail Thee', has words by Lillian Jean Williams and music by Frances Bertha Emery, both of whom were British. Nigeria also adopted 'Arise, O Compatriots' as its anthem from 1978 to 2024, before returning to 'Nigeria, We Hail Thee'."),
    ("what language is spoken in brazil", "Portuguese is the official language of Brazil. Brazil is the world's largest Portuguese-speaking country, a legacy of Portuguese colonisation."),
    ("what is the main ingredient in guacamole", "Avocado is the main ingredient in guacamole, mashed with lime juice, onion, coriander (cilantro), chilli and salt."),
    ("what is the most spoken language in the world", "English is the most widely spoken language overall when you count second-language speakers, with over a billion speakers. Mandarin Chinese has the most native speakers. Spanish has the most speakers after English when counting native speakers only."),
    ("what is the currency of japan", "The currency of Japan is the yen (JPY). Coins and notes are denominated in yen, with one yen not divided into smaller circulating units."),
    ("who was the first president of nigeria", "Nnamdi Azikiwe became Nigeria's first president on 1 October 1963, when Nigeria became a republic. Before that, under the 1960 independence constitution, the head of state was the British monarch represented by a governor-general."),
    ("how tall is the eiffel tower", "The Eiffel Tower in Paris stands 330 metres tall including its antenna, about 300 metres without it. It was built in 1889 for the World's Fair."),
    ("who is the richest man in the world", "The identity of the world's richest person changes with markets, and it is usually someone like Elon Musk, Jeff Bezos or Larry Ellison depending on the week. Check the latest headlines for today's name rather than trusting any frozen list."),
    ("who is the president of nigeria", "Bola Ahmed Tinubu has been President of Nigeria since 29 May 2023. For anything more current than that, ask me for the latest news and I will pull it live."),
]

# Everyday how-to / advice.
GENERAL_HOWTO = [
    ("how do i bake a cake", "HOW TO BAKE A CAKE: you need flour, sugar, butter, eggs, baking powder, milk and vanilla. 1) Heat the oven to 180C (350F) and grease or line a tin. 2) Whisk 225g butter with 225g sugar until pale. 3) Add 4 eggs one at a time. 4) Fold in 225g flour mixed with 2 tsp baking powder, alternating with a splash of milk (about 4 tbsp). 5) Add 1 tsp vanilla. 6) Bake 25-30 minutes; test with a skewer, which should come out clean. Cool 10 minutes in the tin before turning out."),
    ("how do i boil yam", "HOW TO BOIL YAM: peel the yam and cut it into chunks (1-2 inches). Rinse them, then cover with water in a pot and add a pinch of salt. Bring to the boil, then turn down and simmer 15-20 minutes until a fork slides through easily. Drain and serve. Yam is done when it is soft but not falling apart, and it pairs well with egg sauce, stew or palm oil."),
    ("how to tie a tie", "HOW TO TIE A TIE (simple Windsor): 1) Drape the tie around your neck, wide end on the right about 30cm lower than the thin end. 2) Cross the wide end over the thin end. 3) Bring the wide end up through the neck loop. 4) Bring it down through the knot you just made. 5) Pull the wide end up through the loop you just created. 6) Slide it down into the knot and tighten. 7) Slide the knot up and pull the wide end down until the tip sits at your belt line."),
    ("how can i improve my memory", "IMPROVING MEMORY: 1) Sleep 7-9 hours, memory consolidates during deep sleep. 2) Space your revision: short sessions spread over days beat one long cram. 3) Test yourself instead of re-reading. 4) Teach what you learned to someone else. 5) Move your body, exercise grows the brain. 6) Chunk information into groups of about 4 items. 7) Reduce multitasking; attention is the doorway to memory."),
    ("how do i learn python", "LEARNING PYTHON (beginner path): 1) Install Python from python.org and get comfortable with variables, types and printing. 2) Learn lists, dicts and loops. 3) Write small functions and handle errors with try/except. 4) Play with the standard library: os, json, datetime, requests. 5) Build tiny projects: a number game, a file renamer, a weather checker. 6) Read one chapter of 'Automate the Boring Stuff with Python' (free online) and harden your habit with daily 20-minute practice."),
    ("how to make money online", "MAKING MONEY ONLINE (honest starter routes): 1) Freelance skills people already pay for: writing, design, video editing, spreadsheets, virtual assistance. 2) Tutoring or teaching a subject you know. 3) Selling digital products: templates, study guides, printables. 4) Content that solves a real problem, built slowly over months. 5) Your own service routed through CyberLord-style tools if you are into security work. Rule of thumb: charge for a skill, not for watching videos. Anything promising guaranteed passive income with no work is a scam."),
    ("how do i stay productive", "STAYING PRODUCTIVE: 1) Pick ONE most important task for the day and do it first. 2) Work in 25-minute sprints with 5-minute breaks (Pomodoro). 3) Put your phone in another room during sprints. 4) Write tomorrow's top task on paper tonight. 5) Shrink tasks until they feel stupidly small, then start. 6) Review weekly what actually moved the needle and drop the rest. Productivity is mostly saying no to the second-most-important thing."),
    ("how to write a good cv", "WRITING A GOOD CV: 1) One page if you are early-career. 2) Contact details, a two-line summary, experience, education, skills. 3) Start every bullet with an action verb and add numbers ('saved the team 5 hours a week'). 4) Match the keywords in the job post. 5) Tailor the top half to the job, not the whole CV. 6) Get someone to read it once for typos before sending."),
    ("how do i make jollof rice", "HOW TO MAKE JOLLOF RICE (Nigerian style): blend tomatoes, red pepper, onions and garlic; fry with palm oil and tomato paste until the paste sweetens and darkens. Add stock, thyme, curry powder, bay leaves and seasoning cubes. Add washed long-grain rice (about 1 cup per 1.5 cups liquid) and stir, cover and cook on low 35-45 minutes, stirring occasionally, until the rice is tender and the base carries that smoky 'party' flavour. Rest 10 minutes off the heat before serving."),
    ("how to save money each month", "SAVING MONEY EACH MONTH: 1) Find out what you actually spend for one month. 2) Pay yourself first: move a fixed amount to savings the day money lands. 3) List needs vs wants honestly. 4) Kill one recurring subscription this week. 5) Cook 3 extra meals a week instead of ordering. 6) Keep a 3-month emergency fund as the first goal. Small automatic transfers beat big intentions."),
    ("how do i start a business in nigeria", "STARTING A BUSINESS IN NIGERIA: 1) Pick a problem people already pay to solve. 2) Talk to 10 potential customers before spending anything. 3) Start with the smallest version you can sell (a service, not a shop). 4) Register with CAC when you have paying customers. 5) Keep business money in a separate account from day one. 6) Sort your NI and tax basics early. 7) Grow from profit, not from borrowed money, for as long as you can."),
    ("how to learn the piano", "LEARNING PIANO: 1) Get an 88-key digital piano or borrow one; play every day, even 10 minutes. 2) Learn the note names and C major scale first. 3) Practise 5-finger exercises slowly. 4) Use a good method book or app that makes you read notes, not just follow finger numbers. 5) Learn one simple song per week. 6) Play with both hands as soon as you can, and keep a practice log."),
    ("how do i improve my english", "IMPROVING ENGLISH: 1) Read 10 minutes daily, even phone news counts. 2) Speak out loud daily, narrate what you are doing. 3) Write one short paragraph a day. 4) Learn 5 new words a week and use them the same day. 5) Watch shows with English subtitles, then without. 6) Find one conversation partner and talk weekly. Consistency of 20 honest minutes beats weekend marathons."),
    ("how to cook fried rice", "HOW TO COOK FRIED RICE: use day-old cooked rice (fresh rice goes mushy). Heat oil in a very hot wok or pan, scramble 2 eggs and set aside. Add diced carrots, peas, onions and garlic, stir-fry 2-3 minutes. Add the rice, break clumps, and fry 4-5 minutes until grains are dry and golden at the edges. Season with soy sauce (2-3 tbsp) and a pinch of sugar. Fold the eggs back in. Serve immediately while hot."),
    ("how do i get a good night sleep", "SLEEPING BETTER: 1) Same wake time every day, including weekends. 2) No screens 30 minutes before bed, or at least dim them. 3) Cool, dark, quiet room. 4) No caffeine after mid-afternoon. 5) Get daylight in the morning. 6) If you cannot sleep in 20 minutes, get up and read something boring until drowsy. 7) Aim for 7-9 hours; an alarm decides your wake time, habits decide how fast you fall asleep."),
    ("how to take better photos with my phone", "BETTER PHONE PHOTOS: 1) Get closer; fill the frame with your subject. 2) Light is everything: face the light, avoid harsh midday sun. 3) Tap the screen to focus and tap-hold to lock exposure. 4) Clean the lens, fingerprints ruin everything. 5) Use the grid and put horizons on the lines. 6) Shoot in bursts for action. 7) Edit lightly: a little contrast and warmth goes far."),
    ("how do i start exercising", "STARTING TO EXERCISE: 1) Pick something you will actually do 3 times a week: walking, cycling, bodyweight circuits, swimming. 2) Start at 15-20 minutes; consistency beats intensity. 3) Add time before you add difficulty. 4) Schedule it like an appointment. 5) Track your sessions; streaks motivate. 6) Eat and sleep like it matters, because it does. Rest days are part of the plan, not a failure."),
    ("how to plan a birthday party", "PLANNING A BIRTHDAY PARTY: 1) Set the budget and guest list first; everything else follows. 2) Pick a date and venue, then send invitations at least 3 weeks ahead. 3) Plan the food and drink around the guest count (overshoot by about 25 percent). 4) Order the cake early. 5) Make one playlist and one plan for games or activities. 6) Assign two helpers for setup and cleanup. 7) Keep a small 'day of' checklist so you are a host, not staff."),
    ("how do i fix a flat tire", "CHANGING A FLAT TIRE: 1) Park on flat ground, handbrake on, hazards on. 2) Loosen the lug nuts half a turn while the wheel is on the ground. 3) Jack the car up at the marked jack point until the wheel hangs free. 4) Remove the nuts fully (keep them in a bowl, not the dirt). 5) Pull the wheel off. 6) Fit the spare, finger-tighten the nuts in a star pattern, lower the car, then tighten fully in the same star pattern. Check pressure soon after."),
    ("how to change a car tire", "CHANGING A CAR TIRE: same steps as a flat tire. Safety first: flat ground, handbrake on, chocks if you have them, and never put any part of your body under a jacked-up car. Loosen the nuts on the ground, jack at the marked point, remove the wheel, fit the spare or new tire, tighten in a star pattern, and recheck the torque after a few kilometres."),
    ("how do i learn to swim", "LEARNING TO SWIM: 1) Learn to float and breathe in shallow water first. 2) Practise blowing bubbles and holding your breath. 3) Learn the kick on your back, then the front. 4) Add the arm stroke (freestyle) once the kick is steady. 5) Keep sessions short and frequent, 20 minutes beats one long weekly one. 6) Swim where a lifeguard is present until you are confident."),
    ("how to make homemade pizza", "HOMEMADE PIZZA (simple no-yeast-flatbread version): 1) Mix 250g flour, 1 tsp baking powder, 1 tsp salt and 150ml warm water into a dough; knead 3 minutes. 2) Rest while the oven heats to its hottest (240C+). 3) Roll thin on a floured surface. 4) Spread tomato sauce, add mozzarella and toppings. 5) Bake on the hottest rack 8-10 minutes until the crust is golden and the cheese bubbles. For real yeast dough, give it an hour to rise and use a preheated baking stone or cast-iron pan."),
    ("how do i budget my salary", "BUDGETING A SALARY (50/30/20 starter): 1) Write down your take-home pay. 2) Give 50 percent to needs (rent, food, transport, bills). 3) 30 percent to wants (eating out, data, streaming). 4) 20 percent to savings and debt payoff. 5) Move savings on payday, before spending. 6) Review weekly for 2 minutes. If needs exceed 50 percent, cut wants to zero and attack the biggest need line first. Adjust the split to your city; the habit matters more than the exact numbers."),
    ("how to grow a small business", "GROWING A SMALL BUSINESS: 1) Keep existing customers happy before hunting new ones; referrals are the cheapest marketing. 2) Ask every customer one question: why did you buy from me? 3) Raise prices on your best seller, even slightly, and watch what happens. 4) Document what works so it can be repeated. 5) Track numbers weekly: sales, margin, repeat buyers. 6) Cut the product or service line nobody asks about. Growth is usually one thing done repeatedly, not ten new things."),
    ("how do i boil plantain", "HOW TO BOIL PLANTAIN: choose firm green plantain for boiling (ripe yellow ones go sweet and soft). Peel with a knife (green plantain is stubborn; score the skin lengthways and pry). Cut into chunks, rinse, and cover with salted water. Boil 15-20 minutes until tender but not mushy; a knife should slide in with slight resistance. Drain and serve with stew, egg sauce or peppersoup."),
    ("how do i start a youtube channel", "STARTING A YOUTUBE CHANNEL: 1) Pick one topic you can make 50 videos about. 2) Film with your phone; sound matters more than camera quality: film near the phone mic, kill the echo. 3) Make a clear promise in the first 15 seconds. 4) Post on a schedule you can keep for months. 5) Put the searchable words in the title, not clever jokes. 6) Read your analytics after 10 videos: what got clicked, what got watched. 7) The first 30 videos are practice, not failure."),
    ("how do i lose weight", "LOSING WEIGHT SUSTAINABLY: 1) Eat in a small calorie deficit, about 300-500 kcal below maintenance; crash diets bounce back. 2) Protein at every meal keeps muscle and hunger down. 3) Walk 8,000 steps a day; it burns more over a week than any workout. 4) Lift weights or do resistance training twice a week. 5) Sleep 7-9 hours; poor sleep spikes hunger hormones. 6) Track for 2 weeks before judging progress; the scale lies daily but not monthly."),
    ("how to learn a new language", "LEARNING A NEW LANGUAGE: 1) Learn the 100 most common words first. 2) Do 15 honest minutes daily instead of weekend crams. 3) Speak from week one, even badly; grammar comes later. 4) Listen to slow native content with transcripts. 5) Keep a notebook of phrases you actually use. 6) Change your phone language. 7) Find a conversation partner as soon as you can say ten sentences."),
]

# Small talk and identity bits beyond _SMALL_TALK.
GENERAL_CHAT = [
    ("hello there", "Hello there! Good to see you. What is on your mind today?"),
    ("thank you so much", "You are very welcome. Anything else I can help with?"),
    ("are you a robot", "Sort of, I am Oga, the AI voice of CyberLord, made by Nozomio Labs. I can chat, explain things, check the weather and headlines, and even find pictures. What do you need?"),
    ("who are you", "I am Oga, the main CyberLord AI, built by Nozomio Labs for cyberlord.name.ng. I chat on anything, walk you round the CyberLord site, and point your cyber questions to the Academy tutor. What is on your mind today?"),
    ("what is your name", "I am Oga, the main CyberLord AI. Call me Oga, that is the name. What can I do for you?"),
    ("tell me about yourself", "I am Oga, the main CyberLord AI, built by Nozomio Labs. Ask me anything: general questions, how-tos, the weather, today's headlines, a picture, or about the CyberLord site itself. Cybersecurity lessons belong to the Academy tutor, and I will point you there for those."),
    ("good night", "Good night, sleep well. I will be here whenever you need me."),
    ("see you", "See you later. Take care."),
    ("what's your favourite colour", "I do not have a favourite, colours are not really my thing. But I can tell you that blue is the most popular colour in the world. Anything you want to know?"),
    ("do you have a boyfriend", "Ha, no. I am an AI assistant, no boyfriend required. What can I help you with?"),
    ("are you human", "Nope, I am Oga, the AI voice of CyberLord, built by Nozomio Labs. Ask me anything."),
    ("what can i call you", "Call me Oga, that is the name. What would you like to know?"),
    ("how many languages do you speak", "I can handle English and some of the everyday bits of other languages, but English is my home ground. Try me on something."),
]


# Toyota deep-dive (main persona, general knowledge).
# Stable facts only; live prices, post-knowledge recalls and unverifiable
# model-year specs get an honest "I don't know" instead of a guess.
TOYOTA_TOPICS = [
    ("what is toyota", "TOYOTA: Toyota Motor Corporation is a Japanese multinational automaker headquartered in Toyota City, Aichi, Japan. It was founded in 1937 by Kiichiro Toyoda as Toyota Motor Corporation, though its roots go to Sakichi Toyoda's loom business and the Toyota Gosei company of 1926. Toyota is one of the largest automakers in the world by production and sales, known for reliability, hybrid leadership (it pioneered the mass-market Prius), and the Lexus luxury brand. Its Nigerian arm is Toyota Nigeria Ltd, and the brand is one of the most trusted car brands in Nigeria."),
    ("when was toyota founded", "Toyota was founded in 1937 as Toyota Motor Corporation by Kiichiro Toyoda in Koromo (now Toyota City), Japan. The family business began with Sakichi Toyoda's automatic loom company in 1926; Kiichiro's automobile division produced its first passenger car, the AA, in 1936, and the motor company was formally set up in 1937."),
    ("who founded toyota", "Kiichiro Toyoda founded Toyota Motor Corporation in 1937. His father, Sakichi Toyoda, founded the Toyoda loom works, whose patents funded the young automobile business. His son Eiji Toyoda later built the production system (the Toyota Production System) that made Toyota famous for quality."),
    ("toyota headquarters", "Toyota's global headquarters is in Toyota City, Aichi Prefecture, Japan. Its many regional subsidiaries include Toyota Nigeria Ltd, which handles sales and service for Toyota vehicles in Nigeria."),
    ("what does toyota mean", "The name Toyota comes from the family name Toyoda, changed to Toyota because the new spelling needs eight strokes in Japanese katakana, considered lucky, and because it sounds cleaner internationally. The Toyota logo's three ovals represent the customer, the product, and a heart of trust between them."),
    ("toyota history", "Toyota's history in brief: Sakichi Toyoda founded a loom business in 1926; his son Kiichiro Toyoda started automobiles in the 1930s and founded Toyota Motor Corporation in 1937. The Crown launched in 1955 as its first all-original design. The Corolla arrived in 1966 and became the world's best-selling car nameplate. Toyota pioneered mass-market hybrids with the Prius in 1997, and launched the TNGA platform from 2015. Lexus, its luxury brand, launched in the US in 1989."),
    ("what is toyota corolla", "The Toyota Corolla is a compact car, in production since 1966, one of the best-selling nameplates in automotive history with more than 50 million sold worldwide. It is famous for reliability, low running costs and strong resale value. Generations are identified by code names (E100, E110, E120 and so on). The Corolla is offered as a sedan, hatchback, wagon and, in its Cross form, a compact SUV; hybrid versions are sold in many markets including Nigeria."),
    ("when did corolla come out", "The Toyota Corolla launched in Japan in 1966 (the E10 generation, internally designated KE10). It was designed as an affordable, practical family car and quickly became a global export success. The name comes from the Latin word for a small crown, matching the Crown sedan above it."),
    ("best selling car of all time corolla", "Yes, the Toyota Corolla is widely described as the best-selling car nameplate in history, with more than 50 million units across all generations, badges and body styles since 1966. The claim counts the nameplate family (sedan, hatchback, wagon, Cross and others), which is why it tops the list ahead of single models like the Golf or F-Series."),
    ("toyota corolla generations", "Corolla generations are tracked by chassis codes: E10 (1966), E20, E30, E40, E50, E60, E70 (1979), E80 (1983), E90 (1987), E100 (1991), E110 (1995), E120/E130 (2000), E140/E150 (2006), E160 (2012), E170 (2013), E180 (2014), E210 (2019) and current E210-family variants. The E120 and E140 families are especially common as tokunbo (imported) cars in Nigeria."),
    ("toyota corolla engine", "Corolla engines across generations range from 1.3 to 2.0 litres. Common ones include the 1ZR-FE and 2ZR-FE (1.8L) in the E140/E150, the 1NZ-FE/2NZ-FE in smaller markets, and the 2ZR-FAE in the E170. Hybrid Corollas (E210) use a 1.8L 2ZR-FXE Atkinson-cycle engine with an electric motor. The exact engine depends on your year and market, so check the VIN or engine stamp for your exact car."),
    ("toyota camry", "The Toyota Camry is a midsize sedan, in production since 1982 (as the Celica Camry in Japan from 1982, standalone Camry from 1983). It is one of Toyota's global best sellers and the best-selling passenger car in the US for many years. Generations run from XV10 (1992) through XV20, XV30, XV40 (2006), XV50 (2011), XV70 (2018) and the current XV80 (2024). It is known for comfort, reliability and strong resale value, and is a staple of Nigerian roads, both officially sold and tokunbo."),
    ("when did camry launch", "The Toyota Camry began in 1982 as the Celica Camry in Japan and became a standalone nameplate in 1983. It was positioned between the Corolla and the Crown, and the name comes from the Japanese 'kanmuri', meaning crown. It has since had eight generations and is Toyota's flagship midsize sedan worldwide."),
    ("toyota camry engine", "Recent Camry engines: the XV70 (2018-2024) uses a 2.5L Dynamic Force 4-cylinder (A25A-FKS) or, in hybrid form, a 2.5L Atkinson engine with electric drive; the current XV80 (2024) is hybrid-only globally. Earlier generations used 2AZ-FE (2.4L), 2AR-FE (2.5L) and 3.5L V6 (2GR-FE) engines. The exact engine depends on your year and market, so read the engine stamp under the hood."),
    ("toyota hilux", "The Toyota Hilux is a midsize pickup truck, in production since 1968, built on the rugged IMV platform. It is famous worldwide for durability, simple mechanics and off-road ability, and is a sales leader in Africa, Southeast Asia, Australia and Latin America. Generations include the 4th (1988-1997), 5th (1997-2005), 6th (2005-2015, 'Vigo') and 7th (2015-present, 'Revo'/'Rocco'). In Nigeria the Hilux is widely used by companies, NGOs, security fleets and individuals for work and tough terrain."),
    ("when did hilux start", "The Toyota Hilux launched in 1968 as the RN10, replacing the Stout and Briska. It was the first Toyota pickup with a cabin body style and independent front suspension, and evolved into one of the world's most durable workhorses. The name comes from 'high' and 'luxury', reflecting a utility truck with car-like comfort."),
    ("toyota hilux generations", "Hilux generations (roughly): 1st 1968-1978 (RN10), 2nd 1978-1988 (RN40/RN50), 3rd 1988-1997 (RN85), 4th 1997-2005 (RN105), 5th 2005-2015 (Vigo, AN10/AN20), 6th 2015-present (Revo/Rocco, AN120/AN130). The Vigo and Revo generations are the ones you see most in Nigeria. Trim names like SR5, Invincible and Rocco vary by market. Exact specs depend on year and destination market."),
    ("toyota hilux engine", "The current (2015 onward) Hilux uses a 2.4L diesel (2GD-FTB, single turbo) or 2.8L diesel (1GD-FTV, turbo/intercooled) in most markets, and a 2.7L petrol in some. The Vigo generation mainly used a 2.5L diesel (2KD-FTV) with a 3.0L diesel (1KD-FTV) on higher trims, plus petrol options. Power and torque figures vary by tune and market; check the engine stamp and VIN plate."),
    ("toyota hilux towing capacity", "Toyota quotes the 2015 onward Hilux with a braked towing capacity of around 3,500 kg in many markets (single-cab and double-cab diesel trims); unbraked towing is lower, and payload is around 800-1000 kg depending on cab and trim. Earlier Vigo models towed up to about 3,000 kg braked. Limits vary by market and trim, so check the VIN plate and owner's manual for your exact truck."),
    ("toyota land cruiser", "The Toyota Land Cruiser is a large SUV and pickup lineup, in production since 1951, famous for extreme durability, off-road capability and long service life in harsh conditions. The series include the 40, 60, 70, 80, 100, 200 and current 300 series. The Land Cruiser is a status and workhorse vehicle in Nigeria, widely used by government, companies and families. There is also the Land Cruiser Prado, a slightly smaller sibling, and the separate Land Cruiser 70 series for heavy-duty work."),
    ("when did land cruiser come out", "The Toyota Land Cruiser line began in 1951 as the Toyota BJ, a four-wheel-drive Jeep-style vehicle built for military and police use. The 20 series followed in 1955, the 40 series (FJ40) in 1960, and the big SUV line grew through the 60, 80, 100, 200 and 300 series. 'Land Cruiser' became the official name in 1954."),
    ("toyota land cruiser 300 series", "The Land Cruiser 300 series launched in 2021 as the successor to the 200 series. It is built on the TNGA-F platform, uses twin-turbo V6 petrol (3.5L) or diesel (3.3L) engines in most markets (no V8), and has a more modern interior and safety kit. The 300 series is the full-size flagship Land Cruiser sold in Nigeria and globally. Exact specs depend on market and trim; check the VIN plate."),
    ("toyota land cruiser prado", "The Land Cruiser Prado is Toyota's slightly smaller, more comfortable 4x4 SUV, sold alongside the full-size Land Cruiser. Generations: 90 series (1996), 120 series (2002), 150 series (2009) and the current 250 series (2023, also called the new Prado). The Prado uses body-on-frame construction, a 2.4L or 2.8L diesel or a hybrid petrol in some markets, and is a very common family and executive SUV in Nigeria."),
    ("is land cruiser same as prado", "No. The Land Cruiser 300 is the full-size flagship (bigger, more expensive, more powerful), while the Land Cruiser Prado (current 250 series) is the smaller, slightly more compact sibling. Both are body-on-frame 4x4s, both are very capable, and both are common in Nigeria. The Prado is the one most buyers cross-shop against the Fortuner; the 300 series sits a class above."),
    ("toyota rav4", "The RAV4 is a compact crossover SUV, in production since 1994, credited with popularising the crossover segment. Generations: XA10 (1994), XA20 (2000), XA30 (2005), XA40 (2012), XA50 (2018) and the current XA60 (2024). The RAV4 is known for practicality, AWD availability, hybrid and plug-in hybrid options, and strong reliability. In Nigeria it is a popular family SUV, especially the XA40 and XA50 generations, sold new and as tokunbo."),
    ("when did rav4 come out", "The Toyota RAV4 launched in Japan in 1994 (XA10) as a small 3-door and 5-door crossover. Its name means 'Recreational Active Vehicle with 4-wheel drive', though many sold today are front-wheel drive. It helped define the modern crossover category, smaller than a traditional SUV but with SUV looks and AWD options. The current generation is the XA60 (2024 onward)."),
    ("toyota rav4 hybrid", "The RAV4 Hybrid pairs a 2.5L Atkinson-cycle petrol engine with front and rear electric motors (e-AWD standard on hybrid in many markets). Combined output is around 219 hp (FWD) to 222 hp (AWD), with fuel economy roughly 40 mpg combined (about 5.9 L/100 km) in US ratings. The plug-in hybrid (Prime/XSE PHEV) adds a larger battery and about 40 miles (64 km) of electric range. Figures vary by market; hybrids have no conventional starter or alternator, so battery and inverter health matter at high mileage."),
    ("toyota yaris", "The Toyota Yaris is a subcompact hatchback (and sedan in some markets), in production since 1999, designed for affordable urban driving. Generations include the XP10 (1999), XP90 (2005), XP130 (2011), XP150 (2013, sedan-focused) and the current XP210 (2019). The Yaris is known for low running costs, simple mechanicals and city-friendly size, and is a common small car in Nigeria, often imported as tokunbo."),
    ("toyota yaris cross", "The Yaris Cross is the small crossover SUV version of the Yaris, launched in 2020. It sits on the GA-B platform, with front-wheel drive standard and optional hybrid (1.5L Atkinson petrol plus electric motor) in many markets, and optional AWD. It is positioned between the Yaris hatchback and the RAV4. In Nigeria it is sold as a compact family crossover; exact engine and trim depend on market."),
    ("toyota supra", "The Toyota Supra is a sports coupe. The original MkI-IV Supras ran from 1978 to 2002 (the MkIV with the 2JZ-GTE turbo engine is the most famous), then the name returned in 2019 (A90/A91, the 'MkV'), co-developed with BMW (built on the BMW Z4 platform, using BMW engines, badged and tuned by Toyota). The current Supra offers a 2.0L turbo or 3.0L turbo inline-six, in manual or automatic. It is a halo sports car, not the practical family Toyota, and is rare in Nigeria."),
    ("toyota supra mk4 2jz", "The MkIV Supra (1993-2002, A80) is the most celebrated Supra, powered by the 2JZ-GTE 3.0L twin-turbo inline-six, famous for its strength and tuning potential. Stock output was around 276 hp in Japan (gentlemen's agreement) and about 320 hp in the US. The 2JZ engine's reputation comes from its solid block, iron crank and over-engineering. The MkIV is a collector car now; clean examples command high prices and fakes exist, so provenance checks matter."),
    ("toyota prius", "The Toyota Prius is the world's most famous hybrid car, launched in Japan in 1997 as the first mass-produced hybrid. It pairs a petrol engine (Atkinson-cycle, 1.5L or 1.8L depending on generation) with electric motors and a battery, switching seamlessly between petrol, electric and combined drive. The Prius is famous for fuel economy (often 50-57 mpg US combined depending on year) and low running costs. Generations: NHW10 (1997), NHW11 (2000), NHW20 (2003), ZVW30 (2009), ZVW50 (2015), and the current ZVW60 (2022)."),
    ("when did prius come out", "The Toyota Prius launched in Japan in December 1997 (NHW10), the world's first mass-produced hybrid car. It went global in 2000 (NHW11) and became a symbol of fuel-efficient motoring. The name 'Prius' is Latin for 'prior to' or 'before', suggesting a car ahead of its time. Toyota has since applied hybrid technology across its range."),
    ("how does prius hybrid work", "The Prius hybrid system (Toyota Hybrid Synergy Drive) works like this: at low speed and light load, only the electric motor drives the car and the petrol engine is off; under harder load, the petrol engine runs and shares driving with the motor; during braking, energy is recaptured into the battery (regenerative braking); and the battery is recharged by the engine and braking, never by plugging in. The system uses a planetary gearset so there is no conventional gearbox, and a Prius has no starter motor or alternator. On the highway at steady speed, the petrol engine does most of the work."),
    ("toyota hybrid system", "Toyota's hybrid system combines a petrol engine (usually Atkinson-cycle for efficiency) with one or two electric motors, an inverter, and a battery pack. The electronic control unit blends engine and motor power seamlessly, so the driver just drives. Toyota hybrids have no conventional starter or alternator; the motor starts the engine. Fuel economy is typically 40-57 mpg US combined depending on model (Prius highest, RAV4 Hybrid and Highlander lower). Hybrid batteries typically last 8-10 years or 150,000-200,000 km with care. Toyota hybrids are known for reliability, but hybrid-specific diagnostics need a qualified technician."),
    ("toyota tnga", "TNGA (Toyota New Global Architecture) is Toyota's modular vehicle platform introduced from 2015. It splits into TNGA-C (compact: Corolla, C-HR, Yaris Cross), TNGA-B (small: Yaris), TNGA-K (midsize: Camry, RAV4, Highlander, Sienna), TNGA-F (body-on-frame: Land Cruiser 300, Hilux, Tundra, Sequoia, 4Runner, Tacoma), TNGA-L (rear-wheel-drive: Lexus and rear-drive cars) and e-TNGA (electric: bZ4X). TNGA lowers the centre of gravity, stiffens the body and improves handling and efficiency across the range."),
    ("what is tnga platform toyota", "TNGA is Toyota's global modular platform (Toyota New Global Architecture), launched from 2015. Cars share engines, gearboxes, seats and electronics while riding on different-sized platforms (TNGA-C compact, TNGA-K midsize, TNGA-F truck/SUV, e-TNGA electric). The Corolla/C-HR/Yaris Cross use TNGA-C, Camry/RAV4/Highlander use TNGA-K, and Land Cruiser/Hilux use TNGA-F."),
    ("toyota lexus", "Lexus is Toyota's luxury brand, launched in the US in 1989. It builds luxury cars on Toyota platforms and technology, with a reputation for reliability that matches Toyota's. Models include the ES (sedan, based on the Camry), RX (midsize SUV, the best seller), NX, GX, TX, LX (based on the Land Cruiser), UX, IS, LC and the electric RZ. Lexus is sold officially in Nigeria by Toyota Nigeria."),
    ("toyota fortuner", "The Toyota Fortuner is a midsize body-on-frame SUV built on the Hilux platform, in production since 2005. Generations: AN50/AN60 (2005), AN150 (2015) and the current AN160 (2024). It is a rugged 7-seater SUV, common in Nigeria, Southeast Asia, Africa and South America. The diesel (2.4L 2GD or 2.8L 1GD) is the popular engine."),
    ("toyota hilux common problems", "Common Hilux issues owners report: 1) The 2KD-FTV diesel (pre-2015) can develop injector wear and EGR clogging, causing smoke and rough running; keep up fuel-filter changes and use clean diesel. 2) The 1GD/2GD diesels (2015+) are generally robust but can suffer turbo and DPF issues if short trips are the norm. 3) Front suspension and ball joints wear on rough roads; check bushes and steering at service. 4) Rust on the chassis in coastal or salty areas. Always confirm with a qualified mechanic for your exact year, and check the VIN history before buying used; never skip a pre-purchase inspection."),
    ("toyota corolla common problems", "Common Corolla issues owners report: 1) CVT fluid changes are often skipped; fresh CVT fluid every 60,000-100,000 km extends CVT life. 2) 2009-2013 1.8L (2ZR-FE) engines had a well-known oil-consumption issue on some cars; check oil level weekly and service on time. 3) 2003-2008 models had Toyota's airbag recall for Takata inflators; verify recall completion by VIN. 4) Battery and alternator wear can cause no-start complaints on older cars. Always verify by VIN and a pre-purchase inspection rather than trusting a list."),
    ("toyota corolla cvt problems", "The Corolla CVT (K313, in 2014-2019 E170 models) is generally reliable compared to many CVTs, but the main complaints are whining noise on acceleration, delayed engagement when cold, and shudder at low speed, often traced to low or degraded CVT fluid. The fix is a fluid and filter change with the correct Toyota CVT fluid, done by a specialist. CVT fluid changes every 60,000-100,000 km are cheap insurance. If a CVT has failed, replacement is expensive, so test-drive carefully and check service history before buying."),
    ("toyota reliable car", "Toyota earned its reliability reputation through conservative engineering, proven engines and gearboxes, and decades of quality control. The Corolla, Camry, Hilux and Land Cruiser regularly top reliability rankings. Toyota hybrids (Prius, Camry Hybrid, RAV4 Hybrid) also score very highly because the hybrid system has few moving parts. Reliability still depends on maintenance, fuel quality and how the car is driven; a Toyota is not a car you can neglect."),
    ("toyota maintenance schedule", "Toyota's general maintenance rhythm (confirm in your owner's manual): engine oil and filter every 5,000-10,000 km or 6 months (sooner in dusty Nigerian conditions); air filter every 20,000-40,000 km; engine coolant every 4 years or 80,000 km; brake fluid every 2 years; CVT fluid every 60,000-100,000 km; spark plugs every 80,000-100,000 km; and a full inspection at every service. Keep records; they protect resale value."),
    ("how often change toyota engine oil", "Toyota generally recommends engine oil changes every 5,000-10,000 km or every 6 months, whichever comes first, but Nigeria's dust, heat and traffic jams mean the shorter end (5,000 km) is safer. Always use oil of the correct viscosity (0W-20 or 5W-30 for most modern Toyotas) and change the filter with every change."),
    ("toyota nigeria", "Toyota Nigeria Ltd is the official distributor for Toyota and Lexus vehicles in Nigeria, with head offices in Lagos and dealers across the country. It sells new Corolla, Camry, Hilux, Land Cruiser, Prado, Fortuner, RAV4, Yaris and Lexus models, with warranty and after-sales support. Alongside official sales, many Toyotas enter Nigeria as tokunbo (used imports). Toyota is one of the most popular car brands in Nigeria because of reliability, resale value, parts availability and fuel economy."),
    ("toyota cars in nigeria", "Toyota is one of Nigeria's best-selling car brands. The most common models on Nigerian roads are the Corolla, Camry, Hilux, Land Cruiser and Prado, RAV4, Yaris, Fortuner and Lexus models. Many are sold new by Toyota Nigeria Ltd, and many more arrive as tokunbo (used imports) from the US, Canada, Europe and the UAE. Toyotas hold value well in Nigeria and parts are widely available; that is why they dominate resale markets from Lagos to Kano. Model years and trims vary a lot on used imports, so VIN checks matter."),
    ("toyota tokunbo", "Tokunbo means a used imported car, usually from the US, Canada, Europe or the UAE. Tokunbo Toyotas make up a huge share of cars on Nigerian roads because they are cheaper than new and often better equipped. Before buying a tokunbo Toyota, check: the VIN for accident and mileage history, panel gaps and paint for accident signs, the engine and gearbox for leaks and shifting, and the dashboard warning lights on a cold start. Always do a pre-purchase inspection by an independent mechanic; never trust the seller's word alone."),
    ("how to check toyota vin", "A Toyota VIN (Vehicle Identification Number) is 17 characters on a plate at the base of the windshield (driver side) and on the door jamb. The first character tells the country of manufacture (J = Japan, 1/2/4/5 = USA/Canada/Mexico, for example), the 4th-8th characters give the model and engine, and the 10th character is the model year. You can run the VIN through Toyota's official recall page and through reputable history services for accidents and mileage. For tokunbo cars, also cross-check the mileage and accident signs physically."),
    ("toyota recall check", "You can check for open recalls on a Toyota by entering the 17-character VIN on Toyota's official recall page (toyota.com/recall for the US, or your local Toyota site). Recalls are free at authorised dealers. Notable past Toyota recalls include Takata airbags (many models, 2000s-2010s). Always verify your exact VIN rather than assuming your car is or is not affected."),
    ("does toyota make electric cars", "Yes. Toyota sells the bZ4X (on the e-TNGA platform) as its first dedicated battery-electric SUV, and the bZ3 sedan in China and some markets. Toyota's main electric strategy so far has been hybrids (Prius, Corolla, Camry, RAV4, Highlander, Sienna, Lexus RX/ES), which it calls a bridge to full electric. Toyota's global range remains hybrid-led today. For live model availability in Nigeria, check Toyota Nigeria or toyota.com."),
    ("toyota vs honda", "Toyota vs Honda, the honest breakdown: Toyota wins on long-term reliability reputation, resale value, parts availability and hybrid leadership; Honda wins on driving feel, cabin packaging and engine character in some segments. In Nigeria, Toyota holds value better and parts are easier to find, which is why Toyotas dominate the resale market. Honda (Accord, Civic, CR-V) is a strong second choice and often cheaper to buy used. For long-term cost of ownership in Nigeria, Toyota usually comes out ahead."),
    ("toyota vs lexus reliability", "Lexus is Toyota's luxury brand and its reliability is essentially Toyota reliability with luxury trim. Lexus models built on Toyota platforms (ES vs Camry, RX vs Highlander, LX vs Land Cruiser) share engines and gearboxes with their Toyota siblings. In independent rankings, Lexus often scores at or near the very top, slightly ahead of Toyota, mainly because Lexus buyers tend to maintain more carefully."),
    ("toyota full hybrid vs mild hybrid", "Mild hybrids (common on some European models) use a small motor to assist the engine and recover braking energy, but cannot drive on electricity alone. Toyota's full hybrids (Prius, Corolla Hybrid, Camry Hybrid, RAV4 Hybrid) can drive on electric power alone at low speed, switch off the petrol engine in traffic, and use a larger battery and more powerful motors. That is why Toyota hybrids deliver 40-57 mpg. Almost every Toyota hybrid sold today is a full hybrid."),
    ("toyota cvt", "Toyota's CVT (Continuously Variable Transmission) is fitted to Corolla, Yaris, C-HR and other models. It has no fixed gears, so it holds the engine in the efficient rev range, which is why fuel economy is good. Toyota's CVT is generally regarded as reliable when maintained; the key maintenance item is CVT fluid changes every 60,000-100,000 km with the correct fluid, done by a specialist. Symptoms of CVT trouble include whining, shuddering and delayed engagement."),
    ("toyota warranty", "Toyota's new-vehicle warranty varies by market. In the US it is 3 years/36,000 miles basic and 5 years/60,000 miles powertrain, with hybrid components covered for 8 years/100,000 miles. In Nigeria, Toyota Nigeria Ltd offers its own warranty terms on new cars sold by its dealers; always read the exact warranty booklet for your car, since used and tokunbo cars generally have no remaining factory warranty."),
    ("toyota price in nigeria", "I don't know current Toyota prices in Nigeria to the naira, and they change with the exchange rate, import duties and dealer offers, so I won't quote a number I can't verify. The reliable way is Toyota Nigeria's website or a dealer for new cars, and reputable car marketplaces for second-hand and tokunbo prices. Always confirm the total price including duties and registration before paying."),
    ("toyota corolla price nigeria", "I don't know current Corolla prices in Nigeria, and they move with the naira, import duties and dealer offers, so I won't guess a figure. New Corollas (including the Corolla Altis and Corolla Cross) are sold by Toyota Nigeria Ltd; second-hand and tokunbo prices vary sharply by year, mileage and accident history. For a live quote, check Toyota Nigeria or a reputable Nigerian car marketplace, and always cross-check the VIN before buying."),
    ("toyota hilux price nigeria", "I don't know current Hilux prices in Nigeria, and they swing with the exchange rate and import duties, so I won't quote a number I can't verify. New Hilux models (single cab, double cab, SR5, Invincible, Rocco trims) are sold by Toyota Nigeria Ltd; tokunbo prices depend heavily on year, engine (2KD, 2GD or 1GD), mileage and condition. Get a live quote from Toyota Nigeria or a reputable dealer, and verify the VIN before paying."),
    ("best toyota car to buy in nigeria", "The best Toyota to buy in Nigeria depends on your budget and use, but the usual shortlist is: Corolla (best all-rounder, low running costs, holds value), Camry (more comfort, strong resale), Hilux (for work, tough terrain and carrying loads), Prado or Land Cruiser (for family and status, rugged off-road), RAV4 (compact family SUV) and Yaris (cheap city car). For most people the Corolla or Camry is the safest buy. Always check the VIN, do a pre-purchase inspection, and keep service records."),
    ("toyota engine 2zz", "The 2ZZ-GE is a 1.8L naturally aspirated four-cylinder (1796 cc) with Toyota's VVTL-i variable valve timing and lift, producing about 140 hp in standard tune and up to 190 hp in the Celica GT-S, Lotus Elise and Corolla RunX/RSi. It was famous for its high 8,400 rpm redline. It is fitted to the 7th-generation Celica, Corolla RunX/RSi and Lotus Elise. It is a reliable engine when maintained, but like any high-revving engine it needs clean oil and proper warm-up."),
]

def _toyota_lookup(low):
    # Longest matching title wins, so "toyota hilux price nigeria" hits the
    # price entry, not the general Hilux entry.
    best = None
    for title, body in TOYOTA_TOPICS:
        if title in low and (best is None or len(title) > len(best[0])):
            best = (title, body)
    if best:
        return best[1]
    # Alias fallback: "tell me about corolla", "what about the camry", etc.
    _aliases = [
        ("corolla", "what is toyota corolla"),
        ("camry", "toyota camry"),
        ("hilux", "toyota hilux"),
        ("land cruiser", "toyota land cruiser"),
        ("prado", "toyota land cruiser prado"),
        ("rav4", "toyota rav4"),
        ("yaris", "toyota yaris"),
        ("supra", "toyota supra"),
        ("prius", "toyota prius"),
        ("lexus", "toyota lexus"),
        ("fortuner", "toyota fortuner"),
        ("tnga", "toyota tnga"),
        ("toyota", "what is toyota"),
    ]
    for key, title in _aliases:
        if key in low:
            for t, body in TOYOTA_TOPICS:
                if t == title:
                    return body
    return None

# --- Live collectors (keyless, no paid APIs) ------------------------------------

# --- Live collectors (keyless, no paid APIs) ------------------------------------
# Weather: Open-Meteo (free, no key, no signup). Coordinates for Nigerian and
# common world cities; anything else goes through the Open-Meteo geocoding API.
# News: Google News RSS search feed (keyless) parsed with xml.etree.
# Images: Wikimedia/Wikipedia REST+API (keyless) with real thumbnail URLs.
# Every collector degrades to an honest "couldn't reach it" line, never a guess.

_LIVE_UA = {"User-Agent": "CyberLord-Assistant/1.0 (https://cyberlord.name.ng)"}

_CITY_COORDS = {
    "lagos": ("Lagos, Nigeria", 6.5244, 3.3792, "Africa/Lagos"),
    "abuja": ("Abuja, Nigeria", 9.0579, 7.4898, "Africa/Lagos"),
    "port harcourt": ("Port Harcourt, Nigeria", 4.8156, 7.0498, "Africa/Lagos"),
    "kano": ("Kano, Nigeria", 12.0022, 8.5919, "Africa/Lagos"),
    "ibadan": ("Ibadan, Nigeria", 7.3775, 3.9470, "Africa/Lagos"),
    "calabar": ("Calabar, Nigeria", 4.9573, 8.3220, "Africa/Lagos"),
    "jos": ("Jos, Nigeria", 9.9257, 8.8921, "Africa/Lagos"),
    "maiduguri": ("Maiduguri, Nigeria", 11.8304, 13.1506, "Africa/Lagos"),
    "enugu": ("Enugu, Nigeria", 6.5244, 7.5107, "Africa/Lagos"),
    "benin city": ("Benin City, Nigeria", 6.3350, 5.6089, "Africa/Lagos"),
    "nigeria": ("Lagos, Nigeria", 6.5244, 3.3792, "Africa/Lagos"),
    "london": ("London, UK", 51.5072, -0.1276, "Europe/London"),
    "new york": ("New York City, USA", 40.7128, -74.0060, "America/New_York"),
    "nyc": ("New York City, USA", 40.7128, -74.0060, "America/New_York"),
    "los angeles": ("Los Angeles, USA", 34.0522, -118.2437, "America/Los_Angeles"),
    "accra": ("Accra, Ghana", 5.6037, -0.1870, "Africa/Accra"),
    "nairobi": ("Nairobi, Kenya", -1.2921, 36.8219, "Africa/Nairobi"),
    "johannesburg": ("Johannesburg, South Africa", -26.2041, 28.0473, "Africa/Johannesburg"),
    "cairo": ("Cairo, Egypt", 30.0444, 31.2357, "Africa/Cairo"),
    "dubai": ("Dubai, UAE", 25.2048, 55.2708, "Asia/Dubai"),
    "paris": ("Paris, France", 48.8566, 2.3522, "Europe/Paris"),
    "toronto": ("Toronto, Canada", 43.6532, -79.3832, "America/Toronto"),
}

_WX_TEXT = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light rain showers",
    81: "rain showers", 82: "violent rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}

def _wx_text(code):
    return _WX_TEXT.get(code, "changeable weather")

_CITY_PATTERNS = [
    re.compile(r"\bin\s+([a-z' -]{2,30}?)(?:\s+today|\s+now|\s+tomorrow|\s+please|\s*\?|\s*$)", re.I),
    re.compile(r"\bweather\s+(?:in|for)\s+([a-z' -]{2,30}?)(?:\s+today|\s+now|\s+tomorrow|\s+please|\s*\?|\s*$)", re.I),
    re.compile(r"\bhow\s+(?:hot|cold)\s+is\s+it\s+in\s+([a-z' -]{2,30}?)(?:\s+today|\s+now|\s*\?|\s*$)", re.I),
    re.compile(r"\b(?:rain(?:ing)?|sunny|temperature)\s+(?:in|for)\s+([a-z' -]{2,30}?)(?:\s+today|\s+now|\s*\?|\s*$)", re.I),
]

def _extract_city(low):
    for pat in _CITY_PATTERNS:
        m = pat.search(low)
        if m:
            city = m.group(1).strip(" .,?!")
            if city:
                return city
    return None

def _geocode(city):
    """Return (label, lat, lon, timezone) for a city name, or None."""
    # Direct hit on the curated table first (fast, no network).
    for key, val in _CITY_COORDS.items():
        if key in city:
            return val
    try:
        r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "en", "format": "json"},
                         timeout=8, headers=_LIVE_UA)
        r.raise_for_status()
        res = (r.json().get("results") or [None])[0]
        if not res:
            return None
        zone = res.get("timezone") or "UTC"
        label = ", ".join(x for x in (res.get("name", city), res.get("admin1"), res.get("country")) if x)
        return (label, float(res["latitude"]), float(res["longitude"]), zone)
    except Exception:
        return None

def _live_weather(query):
    low = (query or "").lower()
    city = _extract_city(low) or "lagos"
    found = _geocode(city)
    if not found:
        return ("I could not find a place called '" + city + "' in my weather lookup just now. "
                "Try a city name like Lagos, Abuja, London or New York.")
    label, lat, lon, zone = found
    tomorrow = "tomorrow" in low
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": lat, "longitude": lon,
                                 "current_weather": "true",
                                 "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode",
                                 "timezone": zone, "forecast_days": 3},
                         timeout=10, headers=_LIVE_UA)
        r.raise_for_status()
        j = r.json()
        cur = j.get("current_weather") or {}
        daily = j.get("daily") or {}
        times = daily.get("time") or []
        maxs = daily.get("temperature_2m_max") or []
        mins = daily.get("temperature_2m_min") or []
        probs = daily.get("precipitation_probability_max") or []
        codes = daily.get("weathercode") or []
        idx = 0
        if tomorrow and len(times) > 1:
            idx = 1
        tlabel = times[idx] if len(times) > idx else "today"
        when = "tomorrow" if idx else "today"
        bits = []
        if idx == 0 and cur.get("temperature") is not None:
            bits.append("Right now it is about %s degrees C with %s and wind around %s km/h."
                        % (round(cur["temperature"], 1), _wx_text(cur.get("weathercode", 0)),
                           round(cur.get("windspeed", 0))))
        if len(maxs) > idx:
            bits.append("%s the high is about %s C and the low about %s C."
                        % ("Tomorrow" if idx else "Today", round(maxs[idx], 1),
                           round(mins[idx], 1) if len(mins) > idx else "?"))
            if len(probs) > idx and probs[idx] is not None:
                bits.append("Chance of rain: about %s percent." % probs[idx])
            if len(codes) > idx:
                bits.append("Expected conditions: %s." % _wx_text(codes[idx]))
        if not bits:
            return "I could not read a fresh forecast for %s just now. Try again in a minute." % label
        return "Weather in %s (%s, %s): %s" % (label, tlabel, zone, " ".join(bits))
    except Exception:
        return ("I could not reach the weather service just now, so I will not guess "
                "what the weather in %s is doing. Try again in a minute, or check a weather app." % label)

_NEWS_TRIGGERS = ("news", "headline", "headlines", "trending", "breaking",
                  "happening", "latest in", "in the news", "punch", "punch news")
_NICHE_STOP = {"nigeria", "lagos", "today", "latest", "the", "news", "in", "world",
               "english", "top", "any", "whats", "what", "is", "whats", "on"}

def _news_topic(low):
    """Pull a search topic out of a news question; default to Nigeria."""
    t = low
    t = re.sub(r"(whats|what is|what's|what|give me|tell me|show me|latest|top|any|the|today|tonight|right now|please|breaking|trending|happening|in|on|did|does|do)\b", " ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = [w for w in t.split() if w and w not in _NICHE_STOP and len(w) > 2]
    if not words:
        return "Nigeria"
    joined = " ".join(words)
    if "football" in words or "soccer" in words:
        return "Nigeria football"
    if "sport" in words or "sports" in words:
        return "sports Nigeria"
    return joined.title() if len(joined) <= 40 else "Nigeria"

def _live_news(query, limit=7):
    low = (query or "").lower()
    topic = _news_topic(low) if any(w in low for w in ("football", "sport", "tech", "nigeria", "lagos", "world")) else "Nigeria"
    try:
        import xml.etree.ElementTree as ET
        url = "https://news.google.com/rss/search?q=" + requests.utils.quote(topic) + "&hl=en-NG&gl=NG&ceid=NG:en"
        r = requests.get(url, timeout=10, headers=_LIVE_UA)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        if not items:
            return ("I checked the news feed just now and it came back empty for '%s'. "
                    "Ask me again in a bit, or try 'latest news in Nigeria'." % topic)
        lines = ["Latest headlines on %s:" % topic]
        for it in items[:limit]:
            title = (it.findtext("title") or "").strip()
            # Google News appends " - Publisher" to the title; keep it, it is useful source info.
            link = (it.findtext("link") or "").strip()
            date = (it.findtext("pubDate") or "").strip()
            if title:
                lines.append("- %s%s" % (title, (" (via " + link + ")") if link else ""))
            if date:
                lines[-1] += " [%s]" % date[:16]
        return "\n".join(lines)
    except Exception:
        return ("I could not reach the news feed just now, so I cannot give you fresh headlines "
                "without guessing. Try again in a minute.")

_IMAGE_TRIGGERS = ("show me a picture", "show me pictures", "show me an image", "show me images",
                   "show me a photo", "show me photos", "pictures of", "picture of", "images of",
                   "image of", "photos of", "photo of", "find me pictures", "find pictures",
                   "find me images", "find images", "i want pictures", "i want a picture",
                   "i want images", "pictures please", "images please", "photo please")

def _image_subject(low):
    t = low
    for trig in _IMAGE_TRIGGERS:
        if trig in t:
            t = t.replace(trig, " ")
    t = re.sub(r"(please|show me|find me|give me|i want|a picture of|pictures of|images of|an image of|photo of|photos of|of the)\b", " ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = [w for w in t.split() if w and w not in ("show", "me", "pictures", "picture", "puctures", "images", "image", "photos", "photo", "please", "find", "want", "i", "of", "the", "a") and len(w) > 1]
    return " ".join(words) if words else ""

def _live_images(query, limit=4):
    low = (query or "").lower()
    subject = _image_subject(low)
    if not subject:
        return ("Tell me what you want pictures of, like 'show me pictures of the Eiffel Tower' "
                "or 'pictures of Lagos please'.")
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php",
                         params={"action": "query", "format": "json", "generator": "search",
                                 "gsrsearch": subject, "gsrlimit": 6,
                                 "prop": "pageimages|info", "piprop": "thumbnail",
                                 "pithumbsize": 320, "inprop": "url"},
                         timeout=10, headers=_LIVE_UA)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        picks = []
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            thumb = (p.get("thumbnail") or {}).get("source")
            if thumb and "thumb.wikimedia.org" in thumb:
                # Strip Wikipedia attribution query junk, keep the image URL.
                thumb = thumb.split("?")[0]
                picks.append((p.get("title", subject), thumb, p.get("fullurl", "")))
            if len(picks) >= limit:
                break
        if not picks:
            return ("I searched Wikimedia Commons and could not find a free picture for '%s' just now. "
                    "Try a different subject." % subject)
        lines = ["Here are some pictures of %s:" % subject]
        for title, img, page in picks:
            lines.append("- %s: %s%s" % (title, img, (" (more: " + page + ")") if page else ""))
        return "\n".join(lines)
    except Exception:
        return ("I could not reach the free image search just now, so I will not invent picture links. "
                "Try again in a minute.")

def fetch_images(query, limit=4):
    """Structured images: [{url, thumb, title}]. Main persona only."""
    try:
        from urllib.parse import quote_plus
        import re as _re
        t = _re.sub(r"\s+", " ", (query or "").lower().strip())
        words = [w for w in t.split() if w and w not in ("show","me","pictures","picture","puctures","images","image","photos","photo","please","find","want","i","of","the","a") and len(w) > 1]
        subject = " ".join(words) or "beautiful photo"
        r = None
        for _attempt in range(3):
            r = requests.get("https://en.wikipedia.org/w/api.php", params={"action":"query","format":"json","generator":"search","gsrsearch":subject,"gsrlimit":6,"prop":"pageimages|info","piprop":"thumbnail","pithumbsize":320,"inprop":"url"}, timeout=8, headers={"User-Agent":"CyberLord-Assistant/1.0 (cyberlord.name.ng)"})
            if r.status_code == 200:
                break
            if r.status_code in (429, 500, 502, 503, 504) and _attempt < 2:
                import time as _time; _time.sleep(1.5 * (_attempt + 1)); continue
            break
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        out = []
        for pg in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            thumb = (pg.get("thumbnail") or {}).get("source") or ""
            if not thumb or "thumb.wikimedia.org" not in thumb:
                continue
            thumb = thumb.split("?")[0]
            out.append({"url": pg.get("fullurl", thumb), "thumb": thumb, "title": pg.get("title", subject)})
            if len(out) >= limit:
                break
        return out[:limit]
    except Exception:
        return []

def fetch_live_fact(query):
    """Structured weather/news for prompts: (kind, text) or (None, None)."""
    low = (query or "").lower()
    if _wants_weather(low):
        return ("weather", _live_weather(query))
    if _wants_news(low):
        return ("news", _live_news(query))
    return (None, None)

def _wants_images(low):
    return any(t in low for t in _IMAGE_TRIGGERS)

def _wants_weather(low):
    return any(w in low for w in ("weather", "wether", "wheather", "forecast",
                                  "will it rain", "is it raining", "rained today",
                                  "temperature in", "how hot is it", "how cold is it",
                                  "is it sunny", "is it cloudy", "chance of rain",
                                  "is it going to rain", "raining in", "sunny in",
                                  "rain in", "hot in", "cold in"))

def _wants_news(low):
    if any(x in low for x in ("news", "newz", "headline", "headlines", "trending",
                              "breaking news", "in the news", "what happened today",
                              "what is happening", "happening in", "latest in nigeria",
                              "top stories", "latest stories")):
        return True
    if "what's happening" in low and ("today" in low or "latest" in low):
        return True
    return False


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



_GREETINGS = ["Hey there!", "Hello!", "Hi!", "Hey, welcome back!", "Hello, good to see you!"]
_VARIANT_OPENERS = ["Sure thing, here's a clear rundown:", "Got it, let's break this down:", "Happy to help. Here's the practical version:", "Good question. Here's how it works:", "No problem, let's go through this step by step:", "Absolutely, here's the gist:"]
_FOLLOWUPS = {
 "phishing": "Want a quick checklist for spotting a phishing email, or help with what to do if you already clicked?",
 "nmap": "Want the beginner Nmap commands for your own lab, or help reading a scan result you already have?",
 "owasp": "Would you like the 2021 Top 10 list in more detail, or examples of how each one shows up in code?",
 "cve": "Have a specific CVE ID you'd like me to look up in the live NVD database?",
 "career": "Want a step-by-step learning plan with free resources, or cert advice for a specific role?",
 "server": "Is this a Linux or Windows server? I can tailor the hardening steps to your system.",
 "password": "Would you like help choosing a password manager, or setting up MFA on an account?",
 "linux": "Are you on Ubuntu/Debian or another distro? I can give commands for your system.",
}
_AMBIGUOUS = [
 ("windows server", "Is that a Windows Server question, or are you asking about hardening a Windows server? If you tell me the version and what the server runs, I'll give tailored steps."),
 ("how do i hack", "I can only help with authorized testing and learning. Are you trying to practice in your own lab, understand a concept defensively, or secure a system you own? Tell me which, and I'll point you to a legal path."),
]
_UNCERTAINTY = ("Honest answer: I don't know that one from my built-in knowledge, and I don't want to guess. Here is what I can do: rephrase it, ask about a specific tool or CVE, or check a trusted source like NIST NVD or OWASP. What topic are you trying to cover?")
_MAIN_DONT_KNOW = "Honestly, I don't know that one."

def _pick(seq, seed_text):
    idx = sum(ord(c) for c in seed_text) % max(1, len(seq))
    return seq[idx]

def _followup_for(low, title):
    for k, v in _FOLLOWUPS.items():
        if k in low or k in title:
            return v
    return "Want me to go deeper on any part, or give you a practical example with commands?"

_STOP = {"how","do","does","what","is","are","the","to","of","in","on","for","my","me","it","this","that","and","or","can","you","tell","about","explain","teach","please"}
_ALIAS_EXTRA = {"website":"web","site":"web","secure":"security","securing":"security","protect":"security","domain":"dns web","wifi":"wireless","virus":"malware"}
_TYPO_FIXES = {"phising": "phishing", "phishng": "phishing", "malwere": "malware", "maleware": "malware", "ransomwere": "ransomware", "ransomeware": "ransomware", "cyber security": "cybersecurity", "cyber sec": "cybersecurity", "namp": "nmap", "vurnerability": "vulnerability", "wether": "weather", "wheather": "weather", "newz": "news", "puctures": "pictures", "costt": "cost", "yuo": "you", "corrola": "corolla", "corrola ": "corolla ", "toytoa": "toyota"}
def _tokens(s):
    s = (s or "").lower()
    s = re.sub(r"\bti\b", "time", s)
    for wrong, right in _TYPO_FIXES.items():
        s = s.replace(wrong, right)
    toks = set(re.findall(r"[a-z0-9+#.-]{2,}", s)) - _STOP
    extra=set()
    for t in list(toks):
        if t in _ALIAS_EXTRA:
            extra.update(_ALIAS_EXTRA[t].split())
    return toks | extra


def _topic_matches(query):
    q = _tokens(query)
    ranked = []
    for title, body in TOPICS:
        keys = _tokens(title)
        score = len(q & keys) * 2
        # Related technical vocabulary can identify a topic even if the title differs.
        body_keys = _tokens(body)
        score += min(4, len(q & body_keys) // 5)
        # Guard against body-hash noise: require light title overlap unless
        # the query is a short tool/topic name that the body heavily matches.
        if keys and not (q & keys):
            if not (len(q) <= 2 and len(q & body_keys) >= 2):
                continue
        if score:
            ranked.append((score, title, body))
    ranked.sort(key=lambda x: (-x[0], x[1]))
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


_SMALL_TALK = {
    "hi": "Hey there! What's up? I can chat about pretty much anything, or tell you about the CyberLord website if you want.",
    "hello": "Hello! How's your day going? Ask me anything, or ask me about CyberLord if you're curious.",
    "hey": "Hey! What's on your mind today?",
    "good morning": "Good morning! How can I help you today? We can talk about anything, or I can walk you through CyberLord.",
    "good evening": "Good evening! Hope you're having a good day. What can I do for you?",
    "how are you": "Doing great, thanks for asking! How about you, what's on your mind today?",
    "what's up": "Not much, just here and ready to chat. What do you need?",
    "thanks": "You're welcome! Anything else on your mind?",
    "thank you": "You're welcome! Anything else I can help with?",
    "bye": "See you later! Take care.",
    "goodbye": "See you later! Take care.",
    "help": "Sure, I can help with CyberLord stuff, cybersecurity basics, or just chat. What are you trying to do?",
    "what can you do": "I can talk through CyberLord and its plans and tools, point you to the Academy tutor for cybersecurity lessons, and explain a lot of everyday topics right here. What do you need?",
    "who made you": "I am Oga, the main CyberLord AI, built by Nozomio Labs. I am the voice of the CyberLord dashboard, here to chat, guide, and keep the swagger up. What can I help you with today?",
    "who created you": "I am Oga, the main CyberLord AI, built by Nozomio Labs. I am the voice of the CyberLord dashboard, here to chat, guide, and keep the swagger up. What can I help you with today?",
    "who are you": "I am Oga, the main CyberLord AI, built by the Nozomio Labs team for cyberlord.name.ng. I chat on anything, walk you round the CyberLord site, and point your cyber questions to the Academy tutor. What is on your mind today?",
    "what is your name": "I am Oga, the main CyberLord AI. Call me Oga, that is the name. What can I do for you?",
    "how old are you": "I don't really have an age, I am an AI assistant. What can I help you with?",
    "tell me a joke": "Why did the scarecrow win an award? He was outstanding in his field. Want another one, or shall we get back to something useful?",
    "what is the capital of france": "Paris is the capital of France. Want to know more about it, or something else?",
    "ok": "Got it. What would you like to do next?",
    "okay": "Got it. What would you like to do next?",
    "yes": "Great, go ahead and tell me what you need.",
    "no": "No problem. Let me know if you want to chat about anything else.",
    "test": "All good on my end, I am here and listening. What do you need?",
    "help me write an email": "Happy to help. Tell me who it is for, what it should say, and the tone you want, and I will draft it for you.",
}

_CYBERLORD_SITE_INFO = (
    "CyberLord is a domain security toolkit at cyberlord.name.ng. "
    "It offers domain scans, a deep scan, the CyberLord Academy, an AI tutor, "
    "an interaction board, a security centre, and advanced intelligence. "
    "Plans are Free (NGN 0), Pro (NGN 6,300 for 30 days) and Pro Plus (NGN 12,600 for 30 days). "
    "Pro unlocks more tools and academy courses, Pro Plus unlocks the advanced ones. "
    "You can ask me how any part of the site works."
)

_CYBERLORD_SITE_KEYS = (
    "what is this site", "what is the site", "what is this website", "what is the website",
    "cyberlord website", "cyberlord site", "what is cyberlord", "what does cyberlord do",
    "about cyberlord", "tell me about cyberlord", "cyberlord features", "cyberlord plans",
    "cyberlord pricing", "cyberlord price", "how much is cyberlord", "cyberlord free",
    "cyberlord pro", "deep scan", "interaction board", "security centre", "advanced intelligence",
    "cyberlord academy", "cyberlord tutor",
)
_PLAN_KEYS = ("pro plus", "pro-plus", "how much is pro", "how much is pro plus", "how much is pro-plus", "cyberlord plan", "cyberlord plans", "subscription", "payment", "paystack", "bank transfer", "usdt", "how much does pro cost", "how much does cyberlord cost", "pro price", "pro cost", "price of pro", "cost of pro", "free plan", "how do i pay", "how to pay")
_LIVE_CVE_KEYS = ("latest exploited", "known exploited", "cisa kev", "recent kev", "latest cve feed", "cve feed", "latest vulnerabilities", "latest cve")
_ILLEGAL_KEYS = ("how do i hack", "hack into", "break into", "crack password")

try:
    from zoneinfo import ZoneInfo
    _LAGOS_TZ = ZoneInfo("Africa/Lagos")
except Exception:
    _LAGOS_TZ = timezone(timedelta(hours=1), "Africa/Lagos")

def lagos_now():
    return datetime.now(_LAGOS_TZ)

def current_datetime_line(now=None):
    now = now or lagos_now()
    return "Today is " + now.strftime("%A, %B %d, %Y") + ", " + now.strftime("%-I:%M %p").lstrip("0") + " (Lagos time)"

_TIME_DATE_RE = re.compile(r"(what['\s]+(?:time|day|date)|whats['\s]+(?:the['\s]+)?(?:time|day|date)|current['\s]+(?:time|date|day)|time['\s]+is['\s]+it|date['\s]+is['\s]+it|day['\s]+is['\s]+it|what['\s]+is['\s]+(?:the['\s]+)?current)", re.I)

def answer_current_time(q=None):
    return current_datetime_line()

def _looks_like_time_question(q):
    q = (q or "").lower()
    if _TIME_DATE_RE.search(q):
        return True
    if "time" in q and any(w in q for w in ("what", "tell", "current", "now", "exact", "clock")):
        return True
    if any(w in q for w in ("what day is it", "what date is today", "date today", "day is it today", "today's date", "todays date")):
        return True
    return False

def _time_answer():
    now = lagos_now()
    stamp = current_datetime_line(now)
    if "time" in now.strftime("%A").lower():
        pass
    # full sentence, carries the required format verbatim
    return stamp + ". It is " + now.strftime("%-I:%M %p").lstrip("0") + " in Lagos, Nigeria on " + now.strftime("%A, %B %d, %Y") + "."

_GENERAL_OPENER = "Happy to chat about that."
_MAIN_TUTOR_REDIRECT = "That is one for the tutor, head to the Academy tutor and they will walk you through it. The Academy covers Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, and Career Path & Certifications, so pick the course that matches your question and the tutor will help step by step."
_CYBER_MAIN_KEYS = (
    "nmap", "wireshark", "burp", "metasploit", "sqlmap", "gobuster", "nikto", "searchsploit", "john the ripper", "hashcat",
    "cybersecurity", "penetration test", "pen test", "ethical hacker", "ethical hacking", "phishing", "malware", "ransomware",
    "vulnerability", "exploit", "cve", "cvss", "owasp", "xss", "sql injection", "zero day", "rootkit", "botnet", "ddos",
    "social engineering", "2fa", "mfa", "two factor", "firewall", "cryptography", "encryption", "tls", "https", "dns",
    "tcp", "udp", "subnet", "port scan", "kali", "linux", "ssh", "password manager", "strong password",
    "bug bounty", "bugbounty", "incident response", "forensics", "threat intelligence", "mitre", "zero trust",
    "api security", "cloud security", "container", "kubernetes",    "wifi security", "wireless", "android", "mobile security",
    "secure my", "secure my network", "security of my", "how to secure", "how do i secure", "securing my",
    "git", "github secrets", "code injection", "how do i hack", "hack into", "break into", "course",
    "csrf", "ssrf", "sqli", "jwt", "oauth", "siem", "edr", "threat hunting", "buffer overflow", "ddof", "denial of service",
    "active directory", "kerberos", "ntlm", "osint", "reconnaissance", "subdomain",
    "nvd", "cve lookup", "vulnerability scan", "nessus", "shodan", "waf", "siem", "soc",
)
_TUTOR_OFFTOPIC_OPENERS = ["Interesting question, but this one is outside my cybersecurity scope. ", "I love curiousity, but let us keep this one on cybersecurity. ", "That is a bit outside the lesson we are on. ", "Good question, but I am best at cybersecurity topics. "]
_GENERAL_DONT_KNOW = "Honestly, I don't know that one for sure, and I don't want to guess. If you give me a bit more detail I can try to help, or you could check a trusted source. What else can we talk about?"

_CONVERSATIONAL_STARTERS = [
    "Good question. ", "Sure, let's walk through it. ", "Easy one. ",
    "Here's the short version. ", "Let's break it down. ", "Happy to explain. ",
]

def _focus_phrase(q):
    low = q.lower()
    for phrase in ("how do i ", "how to ", "how can i ", "explain ", "what is ", "what does ", "what are ", "tell me about ", "teach me "):
        if phrase in low:
            return low.split(phrase, 1)[1][:60]
    words = low.split()
    return " ".join(words[:5])[:60] if words else ""



def _general_lookup(low, q):
    """Main-persona general brain: exact-ish phrase match against GENERAL_* titles."""
    for title, body in GENERAL_TOPICS:
        if title in low:
            return body
    for title, body in GENERAL_HOWTO:
        if title in low:
            return body
    for title, body in GENERAL_CHAT:
        if title == low or title in low:
            return body
    return None

def _normalize_typos(low):
    s = re.sub(r"\bti\b", "time", low)
    for wrong, right in _TYPO_FIXES.items():
        s = s.replace(wrong, right)
    return s

def answer(query, history=None, persona="main", lesson=None):
    """Built-in KB answer, shaped by persona.
    persona="tutor": academy-only, off-topic -> clever redirect (never a flat
    refusal), current-lesson material first. persona="main" (default): broad
    answers, honestly says when it does not know instead of guessing.
    lesson: optional dict with title/desc/content for the current lesson.
    """
    persona = persona if persona in ("tutor", "main") else "main"
    q = (query or "").strip()
    low = q.lower().strip(" .!?")
    if not q:
        if persona == "tutor":
            return "Ask me anything about cybersecurity or your CyberLord tools and I'll walk you through it."
        return "Hey, I am Oga! Chat with me about anything, or ask me about the CyberLord website and I'll walk you through it."
    _TUTOR_GREETINGS = {"hi", "hello", "hey", "good morning", "good evening", "how are you", "what's up",
                        "thanks", "thank you", "bye", "goodbye", "ok", "okay", "yes", "no", "test", "help"}
    if low in _SMALL_TALK and (persona == "main" or low in _TUTOR_GREETINGS):
        return _SMALL_TALK[low]
    low = _normalize_typos(low)
    _TUTOR_GREETINGS = {"hi", "hello", "hey", "good morning", "good evening", "how are you", "what's up",
                        "thanks", "thank you", "bye", "goodbye", "ok", "okay", "yes", "no", "test", "help"}
    if low in _SMALL_TALK and (persona == "main" or low in _TUTOR_GREETINGS):
        return _SMALL_TALK[low]
    if persona == "main" and _looks_like_time_question(low):
        return _time_answer()
    if persona == "main" and _wants_images(low):
        return _live_images(q)
    if persona == "main" and _wants_weather(low):
        return _live_weather(q)
    if persona == "main" and _wants_news(low):
        return _live_news(q)
    if persona == "main":
        _t = _toyota_lookup(low)
        if _t:
            return _t
        _g = _general_lookup(low, q)
        if _g:
            return _g
    if persona == "main" and any(k in low for k in _CYBERLORD_SITE_KEYS):
        return _CYBERLORD_SITE_INFO
    if persona == "main" and any(k in low for k in _PLAN_KEYS):
        return ("CYBERLORD ACCOUNT & PLANS\nPro: 6,300 NGN or 4.50 USDT for 30 days. Pro Plus: 12,600 NGN or 9.00 USDT for 30 days. USDT networks supported by the current dashboard are TRC20 and BEP20; Paystack is temporarily disabled.\nA receipt, screenshot or bank reference alone does not activate a subscription. Payment must be independently verified by the server-side payment process. I cannot approve payments or change accounts. Never share passwords, OTPs, private keys or seed phrases in chat. For account-specific help contact michaelelvistito@gmail.com.")
    # Live CISA feed BEFORE the cyber redirect, or "latest exploited" hits the
    # tutor redirect on "exploit".
    if any(x in low for x in _LIVE_CVE_KEYS):
        return _live_kev(q)
    if persona == "main" and any(k in low for k in _CYBER_MAIN_KEYS):
        return _MAIN_TUTOR_REDIRECT
    live = _live_cve(q)
    if live:
        return live
    if any(x in low for x in _PLAN_KEYS):
        return ("CYBERLORD ACCOUNT & PLANS\nPro: 6,300 NGN or 4.50 USDT for 30 days. Pro Plus: 12,600 NGN or 9.00 USDT for 30 days. USDT networks supported by the current dashboard are TRC20 and BEP20; Paystack is temporarily disabled.\nA receipt, screenshot or bank reference alone does not activate a subscription. Payment must be independently verified by the server-side payment process. I cannot approve payments or change accounts. Never share passwords, OTPs, private keys or seed phrases in chat. For account-specific help contact michaelelvistito@gmail.com.")
    if any(x in low for x in _ILLEGAL_KEYS):
        return "I can only help with authorized testing and learning. Are you trying to practice in your own lab, understand a concept defensively, or secure a system you own? Tell me which, and I'll point you to a legal path."
    # Tutor: current lesson's material answers first, before the general KB.
    if persona == "tutor" and lesson:
        try:
            _q_texts = []
            for _i, _qq in enumerate(lesson.get("questions", []) or [], 1):
                if isinstance(_qq, dict):
                    _qs = str(_qq.get("question", "")).strip()
                    if _qs:
                        _q_texts.append(_qs)
            _ex = str(lesson.get("exercise", "") or "").strip()
            lesson_text = " ".join([str(lesson.get("title", "")), str(lesson.get("desc", "")), _ex] + list(lesson.get("content", []) or []) + _q_texts)
        except Exception:
            lesson_text = ""
        # Generic prompts like "explain this lesson" pull the lesson summary.
        if low in ("explain this lesson", "explain this", "explain the lesson", "what is this lesson about", "summarize this lesson", "tell me about this lesson", "what did we cover", "recap this lesson"):
            first = str(lesson.get("desc", "")).strip() or lesson_text[:420]
            points = "\n".join(str(p).strip() for p in (lesson.get("content", []) or []) if str(p).strip())
            summary = str(lesson.get("title", "")).strip() + ": " + first
            if points:
                summary += "\n\nKey ideas:\n" + points
            return (summary + "\n\nWant me to drill into any one of those, or give a quick example using the same idea?")
        # Quiz-question asks: discuss and explain; reveal the answer and
        # explanation only when the student asks to check or has attempted it.
        _qlow = low
        _ask_check = any(w in _qlow for w in ("check", "answer", "correct", "right answer", "reveal", "attempted", "tried", "my answer", "is it right"))
        if any(w in _qlow for w in ("question", "quiz", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10")) and lesson.get("questions"):
            import re as _re
            _num = _re.search(r"q(\d+)", _qlow) or _re.search(r"(\d+)(st|nd|rd|th)?\s*question", _qlow)
            _idx = int(_num.group(1)) - 1 if _num else 0
            _qs = lesson.get("questions", []) or []
            if 0 <= _idx < len(_qs) and isinstance(_qs[_idx], dict):
                _qq = _qs[_idx]
                _qtext = str(_qq.get("question", "")).strip()
                _chosen = str(_qq.get("choices", []) or [])[:300]
                _ans = _qq.get("answer", 0)
                try:
                    _ans = int(_ans)
                except Exception:
                    _ans = 0
                _letters = "ABCDEFGHIJ"
                _letter = _letters[_ans] if 0 <= _ans < len(_letters) else str(_ans + 1)
                _expl = str(_qq.get("explain", "") or _qq.get("explanation", "") or "").strip()
                if _ask_check:
                    return ("For question %d: %s\n\nThe correct answer is %s. %s" % (_idx + 1, _qtext, _letter, _expl))
                return ("Let's look at question %d: %s\n\nOptions: %s\n\nTry picking one first and tell me your answer, then I'll check it with you and explain the reasoning." % (_idx + 1, _qtext, _chosen))
        if lesson_text and _tokens(q) & _tokens(lesson_text):
            first = str(lesson.get("desc", "")).strip() or lesson_text[:420]
            return ("Let's stay with this lesson, " + str(lesson.get("title", "")).strip() + ". " + first +
                    "\n\nWant the next step on this, or a quick example using the same idea?")
    # Tutor: academy topics only. Off-topic (no KB topic hit, or an obvious
    # non-security subject) gets a clever redirect, never a generic answer.
    if persona == "tutor":
        _OFF_TOPIC = ("weather", "rain", "temperature", "sunny", "forecast", "football", "soccer",
                      "basketball", "tennis", "cricket", "movie", "film", "music", "song",
                      "sport", "game score", "recipe", "cook", "celebrity", "star sign",
                      "horoscope", "stock price", "lottery", "joke", "meme", "pet", "dog",
                      "cat", "baby", "wedding", "religion", "politic", "election", "currency",
                      "bitcoin price", "ethereum price", "fashion", "holiday", "travel destination")
        _tutor_off_topic = any(x in low for x in _OFF_TOPIC)
        if _tutor_off_topic:
            title = str((lesson or {}).get("title", "")).strip() if lesson else ""
            return _tutor_redirect(q, lesson_title=title)
        _t_matches = _topic_matches(q)
        if not _t_matches:
            title = str((lesson or {}).get("title", "")).strip() if lesson else ""
            return _tutor_redirect(q, lesson_title=title)
        # If the question tokens land mostly in the winning topic's title,
        # return that topic (academy topics second priority).
    # Main persona: topic-matched security questions belong to the tutor.
    if persona == "main" and any(k in low for k in _CYBER_MAIN_KEYS):
        return _MAIN_TUTOR_REDIRECT
    matches = _topic_matches(q)
    if matches:
        score, title, body = matches[0]
        starter = _pick(_CONVERSATIONAL_STARTERS, q)
        first_para = body.split("\n\n")[0].strip()[:420]
        rest = body[len(first_para):].strip(" \n")
        out = [starter + first_para]
        if rest:
            out.append(rest)
        out.append("\nWant me to go deeper on " + title + " or show a practical example next?")
        return "\n\n".join(out)
    if persona == "tutor":
        # Off-academy question: clever redirect, never a flat refusal.
        title = str((lesson or {}).get("title", "")).strip() if lesson else ""
        return _tutor_redirect(q, lesson_title=title)
    # Main persona: friendly general assistant. Chat naturally on ANY topic,
    # talk about the CyberLord website when asked, stay honest when unsure.
    # Never redirect general greetings or everyday questions to cybersecurity.
    if persona == "main":
        focus = _focus_phrase(q)
        if focus:
            return (_GENERAL_DONT_KNOW + " (about " + focus + ")")
        return _GENERAL_DONT_KNOW


def _tutor_redirect(question, lesson_title="", lesson_topic=""):
    topic = (lesson_topic or lesson_title or "cybersecurity").strip()
    angle = {
        "weather": "look at the sky the way a defender looks at logs, patterns and pressure changes",
        "news": "treat headlines like threat intel: verify the source before you trust the signal",
        "sport": "think of match strategy the way a defender thinks about positioning and timing",
        "music": "think of rhythm and patterns, exactly how we spot anomalies hiding in logs",
        "movie": "think of the plot twist the way an attacker hides a step, our job is to spot the gap",
        "food": "think of a recipe the way we think of a checklist: right inputs, right order, no shortcuts",
    }
    low = (question or "").lower()
    hook = next((v for k, v in angle.items() if k in low), None)
    base = ("Nice question, I like the curiosity. In this lesson's world that one turns into "
            + (hook or "something we can actually use here") + ".")
    if topic and topic != "cybersecurity":
        base += (" But let's stay on " + topic + " for now: we were just looking at it, "
                 "and the fastest way to lock it in is to keep going for one more question.")
    else:
        base += " But let's stay on the lesson for now, one more question and it will click."
    return base

