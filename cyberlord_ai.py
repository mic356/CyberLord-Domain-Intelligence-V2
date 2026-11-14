"""Free CyberLord knowledge assistant with curated cybersecurity guidance and public vulnerability lookups.
No paid LLM or API key is required. External lookups use public NVD/CISA feeds when reachable.
"""
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

SOURCES = [
("NIST National Vulnerability Database", "https://nvd.nist.gov/"),
("CISA Known Exploited Vulnerabilities Catalog", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"),
("MITRE ATT&CK", "https://attack.mitre.org/"),
("OWASP", "https://owasp.org/"),
("CIS Controls", "https://www.cisecurity.org/controls"),
("NIST Cybersecurity Framework", "https://www.nist.gov/cyberframework"),
("FIRST CVSS", "https://www.first.org/cvss/"),
("PortSwigger Web Security Academy", "https://portswigger.net/web-security"),

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
_ALIAS_EXTRA = {"website":"web security http","site":"web security http","secure":"security","securing":"security","protect":"security","domain":"dns web","wifi":"wireless","virus":"malware"}
def _tokens(s):
    toks = set(re.findall(r"[a-z0-9+#.-]{2,}", (s or "").lower())) - _STOP
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
    "cyberlord website", "cyberlord site", "what is cyberlord", "what does cyberlord do",
    "about cyberlord", "tell me about cyberlord", "cyberlord features", "cyberlord plans",
    "cyberlord pricing", "cyberlord price", "how much is cyberlord", "cyberlord free",
    "cyberlord pro", "deep scan", "interaction board", "security centre", "advanced intelligence",
    "cyberlord academy", "cyberlord tutor",
)

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
    return bool(_TIME_DATE_RE.search(q or ""))

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
    "api security", "cloud security", "container", "kubernetes", "wifi security", "wireless", "android", "mobile security",
    "git", "github secrets", "code injection", "how do i hack", "hack into", "break into", "course",
)
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
        return "Hey! Chat with me about anything, or ask me about the CyberLord website and I'll walk you through it."
    if low in _SMALL_TALK:
        return _SMALL_TALK[low]
    if persona == "main" and _looks_like_time_question(low):
        return _time_answer()
    if persona == "main" and any(k in low for k in _CYBERLORD_SITE_KEYS):
        return _CYBERLORD_SITE_INFO
    if persona == "main" and any(k in low for k in ("pro plus", "how much is pro", "how much is pro plus", "cyberlord plan", "subscription", "payment", "paystack", "bank transfer", "usdt")):
        return ("CYBERLORD ACCOUNT & PLANS\nPro: 6,300 NGN or 4.50 USDT for 30 days. Pro Plus: 12,600 NGN or 9.00 USDT for 30 days. USDT networks supported by the current dashboard are TRC20 and BEP20; Paystack is temporarily disabled.\nA receipt, screenshot or bank reference alone does not activate a subscription. Payment must be independently verified by the server-side payment process. I cannot approve payments or change accounts. Never share passwords, OTPs, private keys or seed phrases in chat. For account-specific help contact michaelelvistito@gmail.com.")
    if persona == "main" and any(k in low for k in _CYBER_MAIN_KEYS):
        return _MAIN_TUTOR_REDIRECT
    live = _live_cve(q)
    if live:
        return live
    if any(x in low for x in ("latest exploited", "known exploited", "cisa kev", "recent kev", "latest cve feed")):
        return _live_kev(q)
    if any(x in low for x in ("cyberlord plan", "subscription", "pro plus", "payment", "paystack", "bank transfer", "usdt")):
        return ("CYBERLORD ACCOUNT & PLANS\nPro: 6,300 NGN or 4.50 USDT for 30 days. Pro Plus: 12,600 NGN or 9.00 USDT for 30 days. USDT networks supported by the current dashboard are TRC20 and BEP20; Paystack is temporarily disabled.\nA receipt, screenshot or bank reference alone does not activate a subscription. Payment must be independently verified by the server-side payment process. I cannot approve payments or change accounts. Never share passwords, OTPs, private keys or seed phrases in chat. For account-specific help contact michaelelvistito@gmail.com.")
    if any(x in low for x in ("how do i hack", "hack into", "break into", "crack password")):
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

