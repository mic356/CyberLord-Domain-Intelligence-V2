"""
CyberLord Academy: course platform data.

Structure: 6 courses, each a list of lesson slugs.
Every lesson has:
  slug, level, title, time, desc, image (static/academy/), objectives, exercise, content, questions.

To add a question edit the lesson by "slug" below; restart the app.
Gating: course[plan] -> 0 FREE, 1 PRO, 2 PRO PLUS.
"""

LESSON_QUESTIONS_SEP = "---questions---"


ACADEMY_LESSONS = [{'slug': 'networking-essentials',
  'level': 'FOUNDATION',
  'title': 'Networking essentials',
  'time': '12 min',
  'desc': 'Understand IP addresses, ports, TCP, UDP and DNS.',
  'content': ['An IP address identifies a device or network interface. A port identifies a service or '
              'application endpoint on that device.',
              'TCP is connection-oriented and provides ordered, reliable delivery. UDP is connectionless and '
              'has lower overhead, but does not guarantee delivery.',
              'DNS translates domain names into records such as A/AAAA addresses and MX mail servers. A port '
              'being open means a service is listening; it does not automatically mean the service is '
              'vulnerable.'],
  'questions': [{'question': 'What does a port number help identify?',
                 'choices': ['A service or application endpoint',
                             "A device's physical location",
                             "The owner's password"],
                 'answer': 0,
                 'explain': 'A port helps direct network traffic to the correct service on a device.'},
                {'question': 'Scenario: a voice call over UDP drops a packet and the audio glitches for a '
                             'moment, but nothing stalls. A file download over TCP pauses and retransmits '
                             'instead. Which statement is the best explanation?',
                 'choices': ['UDP retransmits silently like TCP but is faster',
                             'UDP trades reliability for lower overhead and no retransmission stalls, which '
                             'suits real-time media',
                             'TCP guarantees delivery but cannot be used for real-time audio at all',
                             'The difference is encryption, not reliability'],
                 'answer': 1,
                 'explain': 'UDP is connectionless and does not retransmit; a lost packet is simply missed, '
                            'which suits live media. TCP retransmits lost data, which suits files.'},
                {'question': 'Log snippet from a resolver:\n'
                             'query: name=backup.example.com type=A\n'
                             'answer: 203.0.113.17\n'
                             'query: name=mail.example.com type=MX\n'
                             'answer: 10 mail.example.com\n'
                             'What do these two answers tell you?',
                 'choices': ['backup.example.com resolves to an IPv4 address; mail.example.com is handled by '
                             'a mail server',
                             'Both names have no mail server configured',
                             'The second query proves mail is encrypted',
                             'DNS cannot return both address and mail records'],
                 'answer': 0,
                 'explain': 'An A record gives the IPv4 address for a host; an MX record names the mail '
                            'exchanger responsible for the domain.'},
                {'question': "An asset owner says: 'Port 22 is open, so the server is compromised.' What is "
                             'the correct professional response?',
                 'choices': ['Agree: an open port means compromise',
                             'Explain that an open port only means a service is listening; compromise needs '
                             'evidence of unauthorised access or misuse',
                             'Close the port immediately without investigation',
                             'Block the port at the perimeter and skip documentation'],
                 'answer': 1,
                 'explain': 'Open is not the same as compromised. A listening service is an exposure to '
                            'assess, not proof of breach.'}],
  'image': 'networking-essentials.svg',
  'objectives': ['Explain IP, port, TCP, UDP and DNS in one sentence each',
                 'Interpret A and MX DNS answers',
                 'Correct the myth that an open port means compromise'],
  'exercise': 'In your lab, run `ss -tlnp` (or `netstat -tlnp`) and list the listening services. Read one '
              'DNS A answer and one MX answer with dig. Write two sentences: what is listening, and where '
              'mail for the domain goes.'},
 {'slug': 'kali-linux-basics',
  'level': 'LINUX & TOOLS',
  'title': 'Getting comfortable with Kali Linux',
  'time': '15 min',
  'desc': 'Learn terminal navigation, files and safe lab habits.',
  'content': ['The terminal lets you run commands and inspect system information. Start with pwd to show '
              'your current directory, ls to list files and cd to change directory.',
              'Use whoami to see the current account and ip addr to inspect network interfaces. Read command '
              'help before running unfamiliar tools.',
              'Keep practice inside your own virtual lab or systems where you have explicit permission. '
              'Avoid running commands copied from unknown sources with administrator privileges.'],
  'questions': [{'question': 'Which command shows your current directory?',
                 'choices': ['pwd', 'whoami', 'ip addr'],
                 'answer': 0,
                 'explain': 'pwd prints the current working directory.'},
                {'question': 'You find a blog post telling you to run `sudo curl -s '
                             "http://random-site.example/x.sh | bash` to 'set up your lab'. What is the "
                             'correct first step?',
                 'choices': ['Run it as root quickly',
                             'Do not run it; inspect the script first and install tools from trusted package '
                             'sources in your own VM',
                             'Run it but only as a normal user',
                             'Run it inside the production network'],
                 'answer': 1,
                 'explain': 'Piping an untrusted script into a shell as root is a classic supply-chain trap. '
                            'Read it first, use trusted sources, and keep it in an isolated lab.'},
                {'question': 'Scenario: you are in /home/kali/evidence and want to move one directory up to '
                             '/home/kali without losing your place. Which command and reasoning is right?',
                 'choices': ['cd .. then pwd to confirm; .. means the parent directory',
                             'cd / to return home',
                             'pwd .. lists the parent',
                             'cd ~ .. goes up two levels'],
                 'answer': 0,
                 'explain': '.. refers to the parent directory. cd .. moves up one level; pwd confirms where '
                            'you are.'},
                {'question': 'A command output shows a service is listening on 0.0.0.0:8080. What should you '
                             'conclude about its exposure?',
                 'choices': ['It only listens on localhost',
                             'It listens on all interfaces, so anyone who can reach the host can connect; '
                             'confirm scope and intent before relying on it',
                             'It is encrypted',
                             'It cannot be reached externally'],
                 'answer': 1,
                 'explain': '0.0.0.0 means the service binds to all available network interfaces. Whether it '
                            'is externally reachable also depends on firewall and routing.'}],
  'image': 'kali-linux-basics.svg',
  'objectives': ['Navigate with pwd, ls, cd and whoami',
                 'Inspect network interfaces with ip addr',
                 'Apply safe lab habits before running unfamiliar tools'],
  'exercise': 'In a VM, practise pwd, ls -la, cd .. and whoami, then check ip addr and note your interfaces. '
              'Find one online guide that suggests piping a script into bash and list three reasons you '
              'would not run it.'},
 {'slug': 'nmap-fundamentals',
  'level': 'RECONNAISSANCE',
  'title': 'Nmap fundamentals',
  'time': '18 min',
  'desc': 'Learn port states, service detection and scan interpretation.',
  'content': ['Nmap is used for network discovery and security auditing. Only scan systems you own or have '
              'permission to assess.',
              'A basic lab command is nmap 127.0.0.1. The -sV option asks Nmap to identify service versions. '
              'Use -p 80,443 to specify ports or -p- to scan all TCP ports.',
              'Open means a service accepted the connection attempt. Closed means the host responded but no '
              'service is listening. Filtered means a firewall or network control prevents Nmap from '
              'determining the state.'],
  'questions': [{'question': 'What does Nmap -sV attempt to identify?',
                 'choices': ['Service versions', 'Wi-Fi passwords', 'User account passwords'],
                 'answer': 0,
                 'explain': '-sV enables service/version detection.'},
                {'question': 'Scan output for a host you own:\n'
                             'PORT     STATE  SERVICE\n'
                             '22/tcp   open   ssh\n'
                             '3306/tcp filtered mysql\n'
                             'What is the correct interpretation?',
                 'choices': ['SSH is reachable; MySQL is blocked or dropped by a firewall, so Nmap cannot '
                             'tell if it is listening',
                             'MySQL is open and unprotected',
                             'SSH is closed',
                             'Filtered means the host is offline'],
                 'answer': 0,
                 'explain': 'Open means the service connected. Filtered means no response was received '
                            '(likely firewall drop), so the state is unknown, not open.'},
                {'question': 'Which scan choice is the least disruptive while still useful for an authorised '
                             'internal lab inventory?',
                 'choices': ['A full -p- scan with aggressive timing on production hosts',
                             'A targeted -sV scan of known ports on lab hosts you own, during an agreed '
                             'window',
                             'An OS-detection scan of the public internet',
                             'Scanning with spoofed sources to hide your activity'],
                 'answer': 1,
                 'explain': 'Narrow scope, known ports, and an agreed window keep the scan useful and '
                            'low-impact. Broad, aggressive scans risk disruption and leave scope unclear.'},
                {'question': "Nmap reports 'OpenSSH 8.2p1 Ubuntu' on port 22. A junior report writes: "
                             "'OpenSSH 8.2p1 is vulnerable to CVE-XXXX-YYYY.' What is wrong with that "
                             'sentence as written?',
                 'choices': ['Nothing: a banner alone proves exploitability',
                             'A version banner is a hint, not proof of the exact build, patch level, or '
                             'configuration; verify against vendor advisories before claiming a CVE',
                             'Nmap cannot detect service versions at all',
                             'Only the operating system matters'],
                 'answer': 1,
                 'explain': 'Banners can be spoofed and distributions backport patches. Match product, exact '
                            'version, and configuration to a vendor advisory before naming a CVE.'}],
  'image': 'nmap-fundamentals.svg',
  'objectives': ['Interpret open, closed and filtered port states',
                 'Use -sV and port selection deliberately',
                 'Avoid naming a CVE from a banner alone'],
  'exercise': "In your lab, run `nmap -sV -p 22,80,443 127.0.0.1` and write each port's state. Add a "
              'firewall rule that drops one port, re-scan, and note what changed from closed to filtered.'},
 {'slug': 'http-tls-headers',
  'level': 'WEB SECURITY',
  'title': 'HTTP, TLS and security headers',
  'time': '16 min',
  'desc': 'Understand requests, responses, HTTPS and browser security headers.',
  'content': ['An HTTP request contains a method, path, headers and sometimes a body. The server responds '
              'with a status code, headers and optional content.',
              'Common status codes include 200 (success), 301/302 (redirect), 400 (bad request), 401 '
              '(authentication required), 403 (forbidden) and 404 (not found).',
              'TLS protects data in transit and helps authenticate the server. Headers such as '
              'Strict-Transport-Security, Content-Security-Policy and X-Content-Type-Options add '
              'browser-side protections.'],
  'questions': [{'question': 'What does HTTP status 403 generally mean?',
                 'choices': ['Forbidden', 'Successful response', 'Page permanently moved'],
                 'answer': 0,
                 'explain': '403 means the server understood the request but refuses access.'},
                {'question': 'Response headers from a site:\n'
                             'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload\n'
                             "Content-Security-Policy: default-src 'self'; script-src 'self'\n"
                             'What is the correct review conclusion?',
                 'choices': ['Both headers are absent and should be added',
                             'HSTS is strong (includes preload and includeSubDomains); CSP restricts scripts '
                             'to the same origin, so review inline/external scripts against it',
                             'CSP means the site is only served over HTTP',
                             'HSTS preload alone protects against SQL injection'],
                 'answer': 1,
                 'explain': 'HSTS with includeSubDomains and preload is the strong form. A CSP of '
                            "default-src 'self' with script-src 'self' blocks inline and third-party "
                            'scripts.'},
                {'question': 'Config review: a server is believed to be forcing HTTPS, but '
                             'http://site.example redirects fine. Which check confirms the TLS upgrade is '
                             'actually enforced for everyone?',
                 'choices': ['Check that the certificate exists',
                             'Request the http:// URL and confirm a redirect to https://, and check the HSTS '
                             'header on the HTTPS response',
                             'Check the DNS A record',
                             'Ping the server'],
                 'answer': 1,
                 'explain': 'Enforcement needs a redirect from HTTP to HTTPS plus an HSTS header so browsers '
                            'keep using HTTPS. A certificate alone does not force HTTPS.'},
                {'question': 'A login page returns 401 for an unauthenticated request and 200 after valid '
                             "login. An auditor writes '401 means the page is forbidden.' What is the "
                             'mistake?',
                 'choices': ['There is no mistake',
                             '401 means authentication is required; 403 means authenticated/identified but '
                             'forbidden. The distinction affects whether retrying with credentials helps',
                             '401 always means the server is down',
                             '401 and 403 are identical'],
                 'answer': 1,
                 'explain': '401 = authentication required. 403 = access refused even though the request was '
                            'understood. Mixing them up misdirects remediation.'}],
  'image': 'http-tls-headers.svg',
  'objectives': ['Read an HTTP request and response',
                 'Explain status codes 200, 301, 401, 403, 404',
                 'Verify HSTS and CSP on a real site'],
  'exercise': 'Run `curl -sI https://cyberlord.name.ng` and note the status, Strict-Transport-Security and '
              'Content-Security-Policy headers. Curl the http version and confirm it redirects to https. '
              'Write one line per finding.'},
 {'slug': 'cve-triage',
  'level': 'VULNERABILITY',
  'title': 'CVE and vulnerability triage',
  'time': '14 min',
  'desc': 'Validate versions, severity, exposure and remediation.',
  'content': ['A CVE is a public identifier for a disclosed cybersecurity vulnerability. A CVE record is a '
              'starting point for research, not proof that a particular system is affected.',
              'Check the exact product, version, configuration and vendor advisory. Compare the affected '
              'version range with reliable evidence from the target environment.',
              'Severity scores help prioritise work, but real risk also depends on exposure, exploitability, '
              'business impact and available mitigations. Document uncertainty instead of overstating a '
              'finding.'],
  'questions': [{'question': 'Does a CVE number alone prove a system is vulnerable?',
                 'choices': ['No; verify product, version and configuration',
                             'Yes, always',
                             'Only if the port is open'],
                 'answer': 0,
                 'explain': 'A CVE must be matched to the actual product and affected '
                            'version/configuration.'},
                {'question': 'Triage scenario: a CVE affects ExampleCMS 4.2.0 to 4.2.3. Your lab VM runs '
                             'ExampleCMS 4.2.1 but has no public route and is only used for offline '
                             'training. How do you prioritise it?',
                 'choices': ['Critical immediately, publish an alert',
                             'Lower than an internet-facing 4.2.3, because version match matters but '
                             'exposure and business impact lower the practical risk; still patch in the next '
                             'maintenance window',
                             'Ignore it forever',
                             'Delete the VM'],
                 'answer': 1,
                 'explain': 'Version match is necessary but not sufficient. Exposure, exploitability and '
                            'impact shape priority; the VM is affected but low risk, so patch normally '
                            'rather than as an emergency.'},
                {'question': "A vendor advisory says a fix is 'backported' into a package that still reports "
                             'the old version number. What does that mean for triage?',
                 'choices': ['The version number proves the system is still vulnerable',
                             'The vendor applied the fix without changing the public version, so '
                             'version-only checks will give false positives; verify the package build or '
                             'vendor statement',
                             'Backports are never real fixes',
                             'The CVE should be deleted'],
                 'answer': 1,
                 'explain': 'Distributions often backport security fixes while keeping the upstream version '
                            'number. Confirm the build or vendor advisory instead of relying on the version '
                            'string alone.'},
                {'question': 'Incident-response decision point: a public exploit for a CVE appears, and the '
                             'same CVE affects a payment service that cannot be patched for 48 hours. What '
                             'is the sound first move?',
                 'choices': ['Wait quietly for the patch window',
                             'Apply compensating controls now (restrict access, add WAF rules, tighten '
                             'monitoring) and document the temporary risk while tracking the patch',
                             'Shut down the whole company network',
                             'Claim the service is not vulnerable because it is unpatched'],
                 'answer': 1,
                 'explain': 'When patching must wait, reduce exposure and detection gaps immediately and '
                            'record the residual risk. That is better than silent waiting.'}],
  'image': 'cve-triage.svg',
  'objectives': ['Match a CVE to product, version and configuration',
                 'Prioritise by exposure and impact, not score alone',
                 'Apply compensating controls when patching must wait'],
  'exercise': 'Pick one CVE from your lab inventory. Run it through the four gates: product, version, '
              'exposure, impact. Decide: patch now, compensating controls, or schedule. Write your '
              'one-sentence rationale and the evidence behind it.'},
 {'slug': 'security-reporting',
  'level': 'REPORTING',
  'title': 'Writing a professional security report',
  'time': '10 min',
  'desc': 'Turn evidence into clear impact and practical recommendations.',
  'content': ['A useful report explains what was tested, when it was tested, the scope and the limitations. '
              'Readers should understand exactly what was and was not assessed.',
              'For each finding, include a concise title, severity rationale, affected asset, reproducible '
              'evidence, impact and a practical remediation recommendation.',
              'Do not include secrets or unnecessary personal data. Separate confirmed observations from '
              'assumptions, and retest after remediation when authorised.'],
  'questions': [{'question': 'What should a finding include?',
                 'choices': ['Evidence, impact and remediation',
                             'Only a scary title',
                             'Unverified assumptions'],
                 'answer': 0,
                 'explain': 'A finding should be supported by evidence and explain its impact and '
                            'remediation.'},
                {'question': 'You observe a staging server (dev.example.com) with debug mode on, during a '
                             'scan limited to production.example.com. How should it be reported?',
                 'choices': ['As a confirmed critical production breach',
                             'Not at all; out of scope means invisible',
                             'As an out-of-scope observation: note it, state it was not tested in this '
                             'engagement, and recommend a separate authorised assessment',
                             'Guessed as a finding with no evidence'],
                 'answer': 2,
                 'explain': 'Out-of-scope observations are worth flagging, but they must not be presented as '
                            'tested findings. Label the scope limit and recommend follow-up.'},
                {'question': 'Two findings: (A) a low-severity missing header on a marketing site, (B) an '
                             'internet-facing service with a known exploited vulnerability. The client asks '
                             'which to fix first. What is the correct ordering?',
                 'choices': ['A first, because headers are easy',
                             'B first, because exposure plus known exploitation outweighs a hardening '
                             'header; explain the ordering in the report',
                             'Both are equal',
                             'Neither needs fixing'],
                 'answer': 1,
                 'explain': 'Priority follows exposure, exploitability and impact, not ease of fix. State '
                            'the reasoning so the client follows the right order.'},
                {'question': 'A log snippet shows a failed login, then a successful login from a new '
                             "country, then a password-reset request. The draft report concludes 'account "
                             "compromised.' What does the evidence actually support?",
                 'choices': ['Confirmed compromise',
                             'Suspicious sequence that warrants investigation and user outreach, but not yet '
                             'a confirmed compromise; list the missing evidence',
                             'Nothing suspicious at all',
                             'A confirmed attack with no further checks needed'],
                 'answer': 1,
                 'explain': 'A suspicious sequence is a lead, not a conclusion. Confirmed compromise needs '
                            'corroborating evidence such as session, device, or content checks.'}],
  'image': 'security-reporting.svg',
  'objectives': ['Structure a finding: title, asset, evidence, impact, fix',
                 'Separate observations from assumptions',
                 'Flag out-of-scope items without overstating them'],
  'exercise': 'Take one lab observation (a listening service or a missing header) and write a full finding: '
              'title, asset, reproducible evidence, impact, remediation, retest step. Ask a friend what they '
              'would do next.'},
 {'slug': 'owasp-top10',
  'level': 'WEB SECURITY',
  'title': 'OWASP Top 10: the hits list',
  'time': '14 min',
  'desc': 'The ten vulnerability categories behind most real web breaches.',
  'image': 'owasp-top10.svg',
  'objectives': ['List the OWASP Top 10 categories from memory',
                 'Explain each category with one real-world example',
                 'Prioritise fixes by risk, not by order in the list'],
  'exercise': 'Pick one category. Write down one public breach caused by it and one design decision that '
              'would have prevented it. Keep both sentences in your notes.',
  'content': ['The OWASP Top 10 collects the web application risks seen most often in real incidents. Broken '
              'access control, injection flaws and insecure design sit at the top because they are common, '
              'not because they are exotic.',
              'Every category maps to a failure mode: trusting the user, trusting the input, trusting the '
              'network, or skipping the logging that would have caught the abuse.',
              'Fixing in list order is a mistake. A broken access control bug on your login page outranks a '
              'cryptographic flaw in a cosmetic feature. Prioritise by exposure and impact.'],
  'questions': [{'question': 'Which of these is an OWASP Top 10 category?',
                 'choices': ['Broken Access Control', 'Perfect Encryption', 'Faster HTML'],
                 'answer': 0,
                 'explain': 'Broken Access Control is a Top 10 category: users can act beyond their '
                            'permissions.'},
                {'question': "A login page lets any visitor view another customer's invoices by changing a "
                             'number in the URL. Which OWASP category does this belong to, and what is the '
                             'fix?',
                 'choices': ['Cryptographic failure; rotate keys',
                             'Broken access control; check authorisation on the server for every request',
                             'Security misconfiguration; change the font',
                             'Logging failure; add more logs'],
                 'answer': 1,
                 'explain': 'Server-side authorisation on every request is the fix for broken access '
                            'control. The client must never be trusted to enforce permissions.'},
                {'question': 'A CTO asks: “We fixed category 1 this week, so the Top 10 is done.” What is '
                             'the correct professional response?',
                 'choices': ['Agree and close the ticket',
                             'Explain the Top 10 is a risk list to prioritise continuously, not a checklist '
                             'that ends with one fix',
                             'Suggest deleting categories 2 to 10',
                             'Recommend hiding the list'],
                 'answer': 1,
                 'explain': 'The Top 10 is a prioritisation aid, not a pass/fail checklist. Risk review is '
                            'ongoing.'}]},
 {'slug': 'xss-explained',
  'level': 'WEB SECURITY',
  'title': 'Cross-site scripting (XSS)',
  'time': '16 min',
  'desc': "How attacker script runs in your users' browsers, and how to stop it.",
  'image': 'xss-explained.svg',
  'objectives': ['Explain stored, reflected and DOM-based XSS',
                 'Describe how a session cookie is stolen',
                 'Apply output encoding and CSP as defences'],
  'exercise': 'In your lab page, add a text field that echoes input back unescaped. Demonstrate the '
              'reflection with a harmless alert. Then escape the output and add a Content-Security-Policy '
              'header. Confirm the attack fails. Never test XSS on a site you do not own.',
  'content': ["XSS means the attacker injects script that runs in another user's browser, with that user's "
              'session. Stored XSS ships inside saved content like a comment. Reflected XSS rides inside a '
              'link or form parameter. DOM-based XSS lives entirely in client-side code.',
              "The damage is whatever the victim's browser can do: read cookies, keystroke passwords, or "
              'perform actions as the victim.',
              'The primary defence is output encoding: treat every untrusted string as data, never as code. '
              'Content-Security-Policy is the second layer: it tells the browser which scripts may run at '
              'all.'],
  'questions': [{'question': "A comment saved by an attacker runs script in every visitor's browser. What "
                             'type of XSS is this?',
                 'choices': ['DOM-based only', 'Stored XSS', 'Reflected XSS'],
                 'answer': 1,
                 'explain': 'Stored XSS persists on the server inside saved content, so it fires for every '
                            'later visitor.'},
                {'question': 'A link like site.example/search?q=<script>alert(1)</script> executes in the '
                             "victim's browser. What is the best primary fix?",
                 'choices': ['Block the word script in the URL',
                             'Encode the search term on output so it is rendered as text, not code',
                             'Remove the search feature',
                             'Hide the link'],
                 'answer': 1,
                 'explain': 'Output encoding neutralises the term. Blocking words is brittle: new payloads '
                            'bypass it.'},
                {'question': 'Scenario: a site sets session cookies without HttpOnly, and an XSS bug is '
                             'found. An auditor writes “XSS impact is limited to a popup.” What is wrong?',
                 'choices': ['Nothing, popups are the only risk',
                             'A script can read and steal a non-HttpOnly session cookie, giving the attacker '
                             "the victim's session",
                             'HttpOnly prevents all XSS',
                             'Cookies cannot be read by scripts'],
                 'answer': 1,
                 'explain': 'Without HttpOnly, a script can exfiltrate the session cookie and the attacker '
                            'becomes the victim.'}]},
 {'slug': 'sqli-deep-dive',
  'level': 'WEB SECURITY',
  'title': 'SQL injection deep dive',
  'time': '18 min',
  'desc': 'How input bends a query, three extraction tricks, and the one real fix.',
  'image': 'sqli-deep-dive.svg',
  'objectives': ['Explain how input alters SQL logic',
                 'Describe union-based, error-based and blind extraction',
                 'Apply parameterised queries as the correct fix'],
  'exercise': 'In your lab app, build one query two ways: string-concatenated, then parameterised. Run the '
              "same payload (e.g. ' OR 1=1 --) against both. Record which one returns data and explain why "
              'in three sentences.',
  'content': ['SQL injection happens when user input is pasted into a query string. The database cannot tell '
              "the difference between the programmer's code and the attacker's text, so the input becomes "
              'part of the logic.',
              'Attackers extract data three ways: union-based selects stitch extra columns into the result, '
              'error-based attacks read data from database error messages, and blind attacks infer data one '
              'yes-or-no answer at a time.',
              'The only correct fix is parameterised queries: the input is sent separately from the SQL, so '
              "it can never change the statement's structure. Input filtering is decoration by comparison."],
  'questions': [{'question': "Input: admin' -- in a login field changes who gets in. Why?",
                 'choices': ['The password was wrong',
                             'The -- comments out the password check, so the query logic changes',
                             'The database is too fast'],
                 'answer': 1,
                 'explain': 'The trailing comment disables the password comparison in the query.'},
                {'question': 'A product page passes its id straight into a query. Which fix actually stops '
                             'SQL injection?',
                 'choices': ['Block the word SELECT',
                             'Blacklist quotes',
                             'Use a parameterised query',
                             'Move the page to HTTPS'],
                 'answer': 2,
                 'explain': 'Parameterised queries separate data from code. Blacklists miss encodings and '
                            'edge cases.'},
                {'question': 'Attack log excerpt:\\nGET '
                             '/product?id=1%20UNION%20SELECT%20user,pass%20FROM%20users\\nWhat is happening '
                             'and what is the first response?',
                 'choices': ['A customer shopping; no response needed',
                             'A union-based extraction attempt; block the source, review query construction, '
                             'and fix the code with parameterised queries',
                             'A slow network; retry',
                             'A backup job; ignore'],
                 'answer': 1,
                 'explain': 'The UNION SELECT shape is a classic data-extraction probe. Treat the log as '
                            'evidence, fix the query, and check what was returned.'}]},
 {'slug': 'auth-flaws',
  'level': 'WEB SECURITY',
  'title': 'Authentication flaws',
  'time': '15 min',
  'desc': 'Weak passwords, session leaks, and recovery flows that give up the keys.',
  'image': 'auth-flaws.svg',
  'objectives': ['Name the five classic authentication failure modes',
                 'Explain why MFA changes the maths',
                 'Review a login flow for throttling and recovery safety'],
  'exercise': 'Write down your own login flow step by step: request, check, session, token, recovery. Mark '
              'each step pass or fail against throttling, expiry, HttpOnly/Secure flags, and reset-token '
              'randomness. Note one fix per fail.',
  'content': ['Most account takeovers do not break strong cryptography. They reuse a leaked password, guess '
              'an unthrottled login form, steal a session cookie, or abuse a password-reset flow with a '
              'predictable token.',
              'Throttling slows guessing. MFA means a stolen password alone is not enough. Short session '
              'lifetimes and secure cookie flags limit the value of a stolen token.',
              'Password recovery deserves the same rigour as login: random, expiring, single-use tokens, and '
              'no messages that reveal whether an account exists.'],
  'questions': [{'question': 'Which combination makes account takeover hardest?',
                 'choices': ['Long passwords only',
                             'MFA plus throttled login plus expiring sessions',
                             'A hidden login page'],
                 'answer': 1,
                 'explain': 'Layers beat single controls: MFA, rate limits and short sessions together raise '
                            'the cost for attackers.'},
                {'question': 'A reset link uses /reset?token=4821 (a four-digit number) and never expires. '
                             'What is the flaw?',
                 'choices': ['The URL is too short',
                             'Predictable, non-expiring reset tokens let anyone guess an account takeover '
                             'path',
                             'Numbers cannot be tokens'],
                 'answer': 1,
                 'explain': 'Reset tokens must be random, high-entropy, single-use and short-lived.'},
                {'question': "Incident note: “Attacker logged in with the victim's password, which they "
                             'bought in a breach dump. MFA was off.” What is the sound remediation order?',
                 'choices': ['Change the password only',
                             'Force a password reset, enable MFA, revoke sessions, and notify the user; then '
                             'review other accounts with the same password',
                             'Wait for the next breach',
                             'Delete the account silently'],
                 'answer': 1,
                 'explain': 'Credential stuffing with a reused password needs the full reset: password, MFA, '
                            'session revocation and user notification.'}]},
 {'slug': 'secure-code-review',
  'level': 'WEB SECURITY',
  'title': 'Secure code review method',
  'time': '15 min',
  'desc': 'A repeatable way to read a login endpoint like an auditor.',
  'image': 'secure-code-review.svg',
  'objectives': ['Review an endpoint in input, logic, output order',
                 'Hunt for missing authorisation checks',
                 'Write observations without overstating them'],
  'exercise': 'Take the login handler from your lab app (or any open-source one you may read). Produce a '
              'one-page review: inputs, query shape, permission checks, error messages, logging. Mark each '
              'line pass, fail, or unknown.',
  'content': ['A secure code review follows the data. Start where untrusted input enters, walk it through '
              'validation and logic, and finish at the output and the logs. Most flaws live at the hand-offs '
              'between those stages.',
              'Permission checks are the most commonly skipped step: the code authenticates, then forgets to '
              'authorise. Look for the check that should happen on every request and does not.',
              'Write findings as observations with evidence, not verdicts. Unknown is an honest answer; it '
              'also tells you exactly what to test next.'],
  'questions': [{'question': 'Where do you begin reading an endpoint for a security review?',
                 'choices': ['The footer',
                             'Where untrusted input enters, then follow it to output and logs',
                             'The README'],
                 'answer': 1,
                 'explain': 'Follow the data. Input, logic, output and logging are the stages where flaws '
                            'hide.'},
                {'question': 'Code snippet:\\nuser = users.get(id)\\nreturn user.invoice\\nThe user is never '
                             'checked against the logged-in account. What is the flaw?',
                 'choices': ['Slow code',
                             'Missing authorisation: any logged-in user can view any invoice by guessing ids',
                             'Database too small'],
                 'answer': 1,
                 'explain': 'Authentication is not authorisation. Every request needs a permission check for '
                            'the specific object.'},
                {'question': 'You cannot tell from the code whether passwords are hashed. How do you record '
                             'it?',
                 'choices': ['Guess it is fine',
                             'Record as “unknown, needs dynamic test: inspect the credential store and '
                             'registration code”',
                             'Skip the finding'],
                 'answer': 1,
                 'explain': 'Unknown is a valid state. State the evidence you lack and the exact test that '
                            'would settle it.'}]},
 {'slug': 'tcp-handshake',
  'level': 'NETWORK SECURITY',
  'title': 'The TCP handshake, explained',
  'time': '12 min',
  'desc': 'SYN, SYN-ACK, ACK: the three packets before any data moves.',
  'image': 'tcp-handshake.svg',
  'objectives': ['Walk through the three-way handshake',
                 'Explain sequence numbers in one sentence each',
                 'Spot a half-open connection in a capture'],
  'exercise': 'Capture a connection in Wireshark (your own lab): filter tcp.flags.syn == 1. You should see '
              'SYN then SYN-ACK. Note the sequence numbers and write one sentence per packet.',
  'content': ['TCP is connection-oriented: before data flows, the two sides agree to talk. The client sends '
              'SYN, the server answers SYN-ACK, and the client confirms with ACK.',
              'Sequence numbers label each byte so the receiver can reorder and spot gaps. Acknowledgements '
              'tell the sender what arrived. Together they make delivery reliable and ordered.',
              'A SYN with no ACK and no data is a half-open connection: normal at first, suspicious in '
              'volume. That is the shape of a SYN flood.'],
  'questions': [{'question': 'What are the three handshake packets, in order?',
                 'choices': ['ACK, SYN, FIN', 'SYN, SYN-ACK, ACK', 'SYN, FIN, RST'],
                 'answer': 1,
                 'explain': 'Client SYN, server SYN-ACK, client ACK. Then data flows.'},
                {'question': 'Capture excerpt: 400 SYN packets arrive in a minute, none complete the '
                             'handshake. What is the likely cause?',
                 'choices': ['A healthy handshake',
                             "A SYN flood: half-open connections exhaust the server's backlog",
                             'DNS failure'],
                 'answer': 1,
                 'explain': 'SYNs with no completing ACKs fill the connection backlog and crowd out real '
                            'clients.'},
                {'question': 'Why do sequence numbers matter?',
                 'choices': ['They encrypt the data',
                             'They let the receiver reorder bytes and detect gaps or replayed segments',
                             'They replace IP addresses'],
                 'answer': 1,
                 'explain': 'Sequence numbers label every byte so TCP can deliver data in order and spot '
                            'what is missing.'}]},
 {'slug': 'firewalls-vpn',
  'level': 'NETWORK SECURITY',
  'title': 'Firewalls and VPNs',
  'time': '14 min',
  'desc': 'Filtering versus encrypting, and where each sits in the path.',
  'image': 'firewalls-vpn.svg',
  'objectives': ['Distinguish firewall filtering from VPN encryption',
                 'Read a simple firewall rule set',
                 'Explain what a VPN does and does not protect'],
  'exercise': 'Write three firewall rules for a small office: allow HTTPS out, drop unsolicited inbound, '
              'allow admin SSH from one IP only. Then write one sentence each: what the firewall stops, what '
              'the VPN adds, what neither stops.',
  'content': ['A firewall filters traffic by rule: source, destination, port, protocol, state. It decides '
              'allow, deny, or log. It cannot see inside encrypted traffic and it cannot fix a vulnerable '
              'service it allows through.',
              'A VPN encrypts traffic inside a tunnel between two points and authenticates the endpoints. On '
              'public Wi-Fi, that hides your traffic from the network around you.',
              'Neither replaces the other. A firewall still guards the network edge, a VPN still needs '
              'endpoint security, and both need patching. A VPN hides traffic from the path, not from the '
              'destination.'],
  'questions': [{'question': 'A firewall rule says allow tcp/443 out, drop inbound unsolicited. What is it '
                             'doing?',
                 'choices': ['Encrypting traffic',
                             'Filtering traffic by rule: which connections may flow',
                             'Scanning for viruses'],
                 'answer': 1,
                 'explain': 'Firewalls filter by header and state. Encryption is a VPN or TLS job.'},
                {'question': 'A user on café Wi-Fi says “the VPN makes my banking safe from the café.” What '
                             'is right and what is missing?',
                 'choices': ['Fully right, nothing missing',
                             'The VPN protects traffic from the local network, but an unpatched laptop or '
                             'fake banking site is still a risk',
                             'VPNs block all viruses'],
                 'answer': 1,
                 'explain': 'The tunnel protects the path. Endpoint security and phishing awareness still '
                            'matter.'},
                {'question': 'Rule order: allow all, then deny port 22. A review says SSH is still '
                             'reachable. Why?',
                 'choices': ['Firewalls are broken',
                             'The first matching rule wins: “allow all” matched first, so the deny never '
                             'runs',
                             'Port 22 cannot be blocked'],
                 'answer': 1,
                 'explain': 'Firewall rules are evaluated top-down; first match wins. Specific denies must '
                            'sit before broad allows.'}]},
 {'slug': 'packet-analysis',
  'level': 'NETWORK SECURITY',
  'title': 'Packet analysis basics',
  'time': '16 min',
  'desc': 'Read a capture: who talked, when, and what they said.',
  'image': 'packet-analysis.svg',
  'objectives': ['Read frame, header and payload layers',
                 'Use display filters to isolate conversations',
                 'Spot exfiltration patterns in a capture'],
  'exercise': 'Record a short capture of your own traffic (e.g. loading a web page). Use a filter for one '
              'host and count the protocols. Write one observation about timing and one about size. Delete '
              'captures with real credentials afterwards.',
  'content': ['A packet capture is a recording of network frames: time, direction, addresses, ports, '
              'protocol, and payload. Wireshark turns those bytes into a readable conversation.',
              'Start with the overview: which hosts, which protocols, how much traffic each way. Then filter '
              'down to one conversation and read it packet by packet.',
              'Exfiltration in a capture shows as an unusual destination, large outbound volume, or odd '
              'protocols. Size plus destination plus timing is usually the tell.'],
  'questions': [{'question': 'What does a packet capture mainly record?',
                 'choices': ['Passwords only',
                             'Frames with time, direction, addresses, ports and payload',
                             "The owner's identity"],
                 'answer': 1,
                 'explain': 'A capture is the network conversation itself: headers and payload, in order.'},
                {'question': "In Wireshark, which filter shows one host's HTTP only?",
                 'choices': ['ip.addr == 10.0.0.5 && http', 'color == red', 'size > 1000'],
                 'answer': 0,
                 'explain': 'Combine the address filter with the protocol filter to isolate the '
                            'conversation.'},
                {'question': 'Capture note: a workstation sends 900 MB to one unfamiliar IP at 3am over DNS. '
                             'What is the right first step?',
                 'choices': ['Ignore it, night traffic is normal',
                             'Treat as suspected exfiltration: preserve the capture, check the host, and '
                             'escalate to incident response',
                             'Block the DNS port for everyone'],
                 'answer': 1,
                 'explain': 'Large, odd, off-hours transfers to an unknown destination are an incident until '
                            'proven otherwise. Preserve evidence first.'}]},
 {'slug': 'dns-security',
  'level': 'NETWORK SECURITY',
  'title': 'DNS security records',
  'time': '14 min',
  'desc': 'A, MX, TXT, CAA, and how attackers abuse them.',
  'image': 'dns-security.svg',
  'objectives': ['Read A, AAAA, MX, TXT and CAA records',
                 'Explain DNS hijacking in one paragraph',
                 "Check a domain's mail records like an auditor"],
  'exercise': 'Run `dig` lookups for A, MX and TXT for a domain you may test (your own or a public one). For '
              'each record write one sentence: what it proves and what an attacker would try to change.',
  'content': ['DNS maps names to infrastructure: A and AAAA to addresses, MX to mail servers, TXT to text '
              'used by SPF and DKIM, CAA to which certificate authorities may issue TLS certificates.',
              'Attackers abuse DNS by hijacking a registrar account, poisoning caches, or registering '
              'lookalike domains. Each route gives them the same prize: control of where names point.',
              'Defence is layered: strong registrar MFA, DNSSEC validation where available, a restrictive '
              'CAA record, and monitoring for record changes.'],
  'questions': [{'question': 'What does a CAA record control?',
                 'choices': ['Email signing',
                             'Which certificate authorities may issue TLS certificates for the domain',
                             'Wi-Fi passwords'],
                 'answer': 1,
                 'explain': 'CAA restricts who may issue certificates, so an attacker cannot simply get a '
                            'valid cert for a lookalike.'},
                {'question': "A domain's MX record is changed overnight to an unfamiliar mail server. No one "
                             'with the registrar login recalls it. What is the concern?',
                 'choices': ['A new backup server',
                             'Possible DNS or registrar hijack: mail now flows through an '
                             'attacker-controlled server',
                             'A printer update'],
                 'answer': 1,
                 'explain': 'Unauthorised MX changes intercept or copy mail. That is a hijack until proven '
                            'otherwise.'},
                {'question': 'Which check pairs best with CAA to stop lookalike-domain phishing?',
                 'choices': ['A longer domain name',
                             'DMARC on the real domain plus user awareness, since CAA does not stop '
                             'lookalikes',
                             'Hiding the WHOIS record'],
                 'answer': 1,
                 'explain': "CAA does not stop lookalike domains. DMARC protects your domain's mail, and "
                            'training catches the rest.'}]},
 {'slug': 'spf-dkim-dmarc-deep',
  'level': 'EMAIL & PHISHING',
  'title': 'SPF, DKIM and DMARC deep dive',
  'time': '18 min',
  'desc': 'Three checks, one verdict: how receivers decide your mail is real.',
  'image': 'spf-dkim-dmarc.svg',
  'objectives': ['Explain SPF, DKIM and DMARC each in one sentence',
                 'Read a DMARC policy: none, quarantine, reject',
                 'Explain why alignment matters'],
  'exercise': 'Check your own domain (or a public one) with dig for TXT (SPF), the DKIM selector, and the '
              '_dmarc TXT record. Write one line per record: what it says, and what would break if it were '
              'missing.',
  'content': ['SPF checks whether the sending IP is authorised for the domain. DKIM checks that the message '
              "carries a valid cryptographic signature made with the domain's private key. DMARC tells the "
              'receiver what to do when those checks fail, and where to send reports.',
              'Alignment is the catch: SPF must pass for the domain in the From header, and DKIM must be '
              'signed for that same domain. A perfect signature from the wrong domain still fails DMARC.',
              'Start at p=none to gather reports, move to quarantine, then reject once the legitimate '
              'senders are all authenticated. Jumping straight to reject usually breaks real mail.'],
  'questions': [{'question': 'What does each check prove? SPF / DKIM / DMARC?',
                 'choices': ['All three encrypt email',
                             'SPF authorises the sending IP, DKIM verifies the signature, DMARC is the '
                             'policy for failures',
                             'They are three names for one record'],
                 'answer': 1,
                 'explain': "Authorisation, signature, policy. Together they form the receiver's verdict."},
                {'question': 'A message passes SPF for evil.com but the From header says yourbank.com. DMARC '
                             'result?',
                 'choices': ['Pass, SPF passed',
                             'Fail: SPF passed for the wrong domain, so alignment fails',
                             'Pass if the subject looks real'],
                 'answer': 1,
                 'explain': 'DMARC requires alignment with the From domain. SPF for another domain does not '
                            'count.'},
                {'question': 'A report shows p=none and your legitimate newsletter is failing DKIM because '
                             'of a broken selector. What is the right move?',
                 'choices': ['Move to p=reject immediately',
                             'Fix the DKIM selector, confirm alignment passes, then step the policy up',
                             'Delete DMARC'],
                 'answer': 1,
                 'explain': 'Fix authentication first, then tighten policy. Rejecting while legitimate mail '
                            'fails breaks real customers.'}]},
 {'slug': 'phishing-anatomy',
  'level': 'EMAIL & PHISHING',
  'title': 'Anatomy of a phishing email',
  'time': '13 min',
  'desc': 'Hook, spoof, trap, payload: read a phish like an analyst.',
  'image': 'phishing-anatomy.svg',
  'objectives': ['Break a phish into hook, spoof and trap',
                 'Check sender, link and page independently',
                 'Explain why MFA codes get harvested'],
  'exercise': 'Take one real de-identified phishing email from your inbox or a public sample. Annotate four '
              'things: the hook, the sender trick, the link destination, the page it leads to. Write the one '
              'check that would have stopped each.',
  'content': ['Every phish has the same skeleton: a hook that creates urgency or temptation, a spoofed '
              'appearance of trust, a trap that harvests credentials, and a payload that cashes them in.',
              'The sender display name is free text. The real address is in the headers. Hover the link and '
              'read the actual destination, not the words on the button. The landing page copies a login '
              'form but the credentials go to the attacker.',
              "MFA does not save a user who types the code into the attacker's page: the code is relayed in "
              'real time. Verification must happen before anything is typed.'],
  'questions': [{'question': 'A message from “Your Bank” arrives from bank-support@nothebank.example. What '
                             'is the tell?',
                 'choices': ['The greeting',
                             'The actual sender domain does not match the bank; display names are free text',
                             'The logo'],
                 'answer': 1,
                 'explain': 'Always read the address, not the display name. Nothebank is not the bank.'},
                {'question': 'Why does real-time MFA code harvesting work?',
                 'choices': ['MFA codes are long',
                             "The victim types the live code into the attacker's page, which relays it "
                             'before it expires',
                             'Banks share codes'],
                 'answer': 1,
                 'explain': 'The attacker relays the fresh code within its validity window. The human is the '
                            'bypass.'},
                {'question': 'You kept the phish email. What should you do with it?',
                 'choices': ['Click the link to check',
                             "Forward it to the real organisation's abuse address and report it; then delete "
                             'your copy',
                             'Forward it to everyone'],
                 'answer': 1,
                 'explain': "Report to the impersonated org's abuse channel (or your provider), then delete. "
                            'Never click through from the training copy.'}]},
 {'slug': 'social-engineering',
  'level': 'EMAIL & PHISHING',
  'title': 'Social engineering plays',
  'time': '14 min',
  'desc': 'Pretexting, urgency, baiting, vishing: the human attack surface.',
  'image': 'social-engineering.svg',
  'objectives': ['Name the four classic plays',
                 'Explain why urgency defeats verification',
                 'Design one process control per play'],
  'exercise': 'Write a one-paragraph pretext an attacker might use on a fictional helpdesk. Then write the '
              'verification step that stops it. Repeat for urgency and baiting. This is defence training, '
              'not a script to use.',
  'content': ['Social engineering is manipulation, not hacking: pretexting builds a false story, urgency and '
              'authority suppress verification, baiting offers a tempting prize, and vishing or smishing '
              'moves the same script to voice and text.',
              'Urgency is the master key. Every play tries to make the target act before they verify. The '
              'defence is a pause: a separate channel, a call-back number, a colleague check.',
              'Process beats awareness alone. A rule like “payments never on first contact, always verified '
              'on a known number” stops more fraud than a poster ever will.'],
  'questions': [{'question': 'A caller claims to be IT, asks for your password “to fix your account”. Which '
                             'play is this?',
                 'choices': ['Vishing with pretexting', 'SQL injection', 'DNS poisoning'],
                 'answer': 0,
                 'explain': 'A voice call plus a false role is pretexting by phone. Real IT never asks for '
                            'your password.'},
                {'question': 'Finance staff get a message: “CEO here, wire $5k now, confidential.” What '
                             'control stops this?',
                 'choices': ['A spam filter',
                             'A process rule: payments verified on a known channel, never on first contact',
                             'Faster passwords'],
                 'answer': 1,
                 'explain': 'Business email compromise wins on urgency. A verification rule breaks the '
                            'script.'},
                {'question': 'Why is urgency the master key of social engineering?',
                 'choices': ['It makes messages shorter',
                             'It makes the target act before they verify, which is exactly what the attacker '
                             'needs',
                             'It encrypts the message'],
                 'answer': 1,
                 'explain': 'Verification is the defence. Urgency exists to skip it.'}]},
 {'slug': 'forensics-process',
  'level': 'FORENSICS & IR',
  'title': 'Forensics and IR lifecycle',
  'time': '15 min',
  'desc': 'Prepare, detect, contain, recover, learn: the order that matters.',
  'image': 'forensics-process.svg',
  'objectives': ['Recite the five IR phases in order',
                 'Explain why containment comes before recovery',
                 'Describe what a lessons-learned report contains'],
  'exercise': 'Write a one-page incident response plan for a small organisation: owners, first three '
              'actions, who to call, where evidence goes. Keep it readable by a non-technical manager.',
  'content': ['Incident response is a lifecycle: prepare before anything happens, detect and analyse, '
              'contain the spread, eradicate and recover, then learn and fix the process. The order is the '
              'discipline.',
              'Containment before recovery matters because rebuilding on a still-compromised system just '
              'hands the attacker the new system. Eradication removes the cause; recovery restores service.',
              'The lessons-learned report closes the loop: timeline, decisions, gaps, and process fixes. An '
              'incident that changes nothing will repeat.'],
  'questions': [{'question': 'What is the correct IR order?',
                 'choices': ['Recover, contain, detect',
                             'Prepare, detect and analyse, contain, eradicate and recover, learn',
                             'Detect, recover, prepare'],
                 'answer': 1,
                 'explain': 'Preparation first, lessons last, containment before recovery.'},
                {'question': 'Why contain before recovering?',
                 'choices': ['Faster billing',
                             'Rebuilding on a compromised system hands the attacker the restored system; '
                             'eradication must come first',
                             'Logs look nicer'],
                 'answer': 1,
                 'explain': 'Contain and eradicate the cause, then recover. Otherwise the incident restarts '
                            'from the new build.'},
                {'question': 'The post-incident report is mainly for:',
                 'choices': ['Blame', 'Process fixes so the same incident cannot repeat', 'Marketing'],
                 'answer': 1,
                 'explain': 'Lessons learned exist to change the process, not to assign blame.'}]},
 {'slug': 'evidence-handling',
  'level': 'FORENSICS & IR',
  'title': 'Evidence handling',
  'time': '13 min',
  'desc': 'Capture, hash, custody, copies: evidence that survives scrutiny.',
  'image': 'evidence-handling.svg',
  'objectives': ['Hash files with SHA-256 and verify a hash',
                 'Explain chain of custody in one sentence',
                 'State the copies-only rule'],
  'exercise': 'Create a text file, hash it with sha256sum, copy it, hash the copy, and confirm they match. '
              'Then change one byte in the copy and re-hash. Write down what the mismatch proves.',
  'content': ['Forensics stands or falls on integrity. Capture evidence first: disk images, logs, '
              'screenshots, memory. Hash everything with SHA-256 so any later change is detectable.',
              'Chain of custody is the record of who held the evidence, when, and why. It is the story that '
              'makes the hash meaningful in court or in an HR process.',
              'Work on copies, never the original. Analysis tools change timestamps and metadata; the '
              'original must remain provably untouched.'],
  'questions': [{'question': 'What does hashing achieve?',
                 'choices': ['Encryption', 'Provable integrity: any change changes the hash', 'Compression'],
                 'answer': 1,
                 'explain': 'A hash is a fingerprint. If the original changes after hashing, the '
                            'fingerprints will not match.'},
                {'question': 'An analyst runs tools directly on the only copy of a seized drive. What is '
                             'wrong?',
                 'choices': ['Nothing',
                             'Analysis changes the original; investigators must work on a hashed copy and '
                             'preserve the original',
                             'Tools are too old'],
                 'answer': 1,
                 'explain': 'The original is evidence. Tools alter it, so they run on copies only.'},
                {'question': 'What is chain of custody?',
                 'choices': ['A password list',
                             'The documented record of who held the evidence, when, and why',
                             'A backup schedule'],
                 'answer': 1,
                 'explain': 'Custody is the story of possession. Without it, integrity alone will not '
                            'convince a court.'}]},
 {'slug': 'ir-playbook',
  'level': 'FORENSICS & IR',
  'title': 'Your first 24 hours of an incident',
  'time': '16 min',
  'desc': 'Triage, contain, scope, communicate: a clock for the first day.',
  'image': 'ir-playbook.svg',
  'objectives': ['Assign an incident owner in hour zero',
                 'Sequence contain, scope and comms across 24 hours',
                 'Write a one-paragraph status update'],
  'exercise': 'Simulate an incident: a colleague reports ransomware on one laptop. Write four timestamped '
              'notes, one per phase (triage, contain, scope, comms), each two sentences. Hand them to a '
              'friend: could they act on them?',
  'content': ['The first hour decides the incident: confirm it is real, name an owner, and start a written '
              'timeline. Hour one contains: isolate the host, block indicators, revoke sessions. Scope '
              'follows: who else, what data, how it started.',
              'Communication is an incident task, not an afterthought. Customers, management and regulators '
              'each need what you know, what you do not know, and when the next update lands.',
              'A written timeline beats memory under pressure. Every decision, in order, with a time. It '
              'becomes the post-incident report and, if needed, the evidence.'],
  'questions': [{'question': 'In the first hour, the most important job is:',
                 'choices': ['Rebuilding the server',
                             'Confirming the incident is real, naming an owner, and starting a written '
                             'timeline',
                             'Emailing the press'],
                 'answer': 1,
                 'explain': 'Ownership plus a timeline. Everything else hangs off those two.'},
                {'question': 'A compromised laptop is still on the network, spreading. The team wants to '
                             '“watch it for a week”. What is the sound call?',
                 'choices': ['Watch silently',
                             'Contain now (isolate, block, revoke) and investigate from preserved evidence; '
                             'watching live spread trades learning for damage',
                             'Reboot it'],
                 'answer': 1,
                 'explain': 'Containment first. Evidence survives on copies; the live spread does not need '
                            'to continue to be studied.'},
                {'question': 'What belongs in the first customer update?',
                 'choices': ['Blame and guesses',
                             'What you know, what you do not know, and when the next update arrives',
                             "The attacker's email"],
                 'answer': 1,
                 'explain': 'Honest status plus a next-update time. Guesses become liabilities.'}]},
 {'slug': 'secplus-roadmap',
  'level': 'CAREER',
  'title': 'Security+ road map',
  'time': '13 min',
  'desc': 'Domains, performance questions, and how to study for CompTIA Security+.',
  'image': 'secplus-roadmap.svg',
  'objectives': ['List the Security+ domains and their weight',
                 'Plan a 6-week study schedule',
                 'Explain performance-based questions'],
  'exercise': 'Pick one domain. Write five study topics, one hands-on lab per topic, and the book chapter '
              'that covers it. That is your study week.',
  'content': ['CompTIA Security+ covers concepts, architecture, operations, monitoring and governance. It is '
              'vendor-neutral, entry-level, and the most common first security cert employers ask for.',
              'Performance-based questions give you a scenario or a console and ask you to act. They punish '
              'cramming and reward lab time: build the thing once and the question is familiar.',
              'Study each domain in three passes: read, lab, self-test. Book the exam only when practice '
              'scores are consistent, not when you feel brave.'],
  'questions': [{'question': 'What kind of questions make Security+ different from memory tests?',
                 'choices': ['Long essays',
                             'Performance-based questions: act in a scenario or console, not just recall',
                             'No practicals'],
                 'answer': 1,
                 'explain': 'Performance questions simulate real tasks. Lab practice is the preparation.'},
                {'question': 'A candidate studies one topic overnight and books the exam next week. What is '
                             'the better plan?',
                 'choices': ['Book and hope',
                             'Three passes per domain (read, lab, self-test) and book only on consistent '
                             'practice scores',
                             'Skip the labs'],
                 'answer': 1,
                 'explain': 'Consistent practice evidence beats cramming and nerves.'},
                {'question': 'Why do employers ask for Security+?',
                 'choices': ['It is easy',
                             'It is vendor-neutral baseline proof of core concepts across security '
                             'operations',
                             'It replaces experience'],
                 'answer': 1,
                 'explain': 'It standardises vocabulary and core knowledge. Experience still does the '
                            'rest.'}]},
 {'slug': 'ceh-vs-blue-team',
  'level': 'CAREER',
  'title': 'Red team, blue team, purple team',
  'time': '12 min',
  'desc': 'Attack skills like CEH, defence careers, and how they connect.',
  'image': 'ceh-vs-blue-team.svg',
  'objectives': ['Define red, blue and purple teams',
                 'Explain what CEH teaches and what it does not',
                 'Choose a first junior role realistically'],
  'exercise': 'Job hunt exercise: search three junior roles in your market (SOC analyst, IT support, junior '
              'pentester). For each, list the skills named and mark which come from Security+ study versus '
              'lab work.',
  'content': ['Red teams think like attackers and test defences. Blue teams defend, detect and respond. '
              'Purple teams run joint exercises and close the gaps the red team finds, in real time.',
              'CEH teaches attack methodology: reconnaissance, exploitation, reporting. It is a strong '
              'second cert, but most junior roles hire for blue team skills: monitoring, triage, log '
              'analysis.',
              'A common path is IT support, then SOC analyst, then a specialism. Pick the first role by the '
              "skills listed, not by the title's glamour."],
  'questions': [{'question': 'What does a blue team do?',
                 'choices': ['Only attack', 'Defend, detect and respond to incidents', 'Issue certificates'],
                 'answer': 1,
                 'explain': 'Blue team is defence: monitoring, detection, response.'},
                {'question': 'CEH is best described as:',
                 'choices': ['A law degree',
                             'Attack methodology training: recon, exploitation, reporting. A strong second '
                             'cert after baseline',
                             'A blue team monitoring cert'],
                 'answer': 1,
                 'explain': 'CEH teaches how attackers operate. Pair it with blue team foundations.'},
                {'question': 'A candidate wants a junior pentest role with no labs, no certs, no reports. '
                             'What is the honest advice?',
                 'choices': ['Apply anyway',
                             'Build proof first: a lab, a small report, a challenge write-up; junior pentest '
                             'roles are scarce without evidence',
                             'Learn to bluff'],
                 'answer': 1,
                 'explain': 'Pentest hiring runs on proof. Labs and written findings are the entry '
                            'ticket.'}]},
 {'slug': 'cv-and-interview',
  'level': 'CAREER',
  'title': 'CV and interview for security roles',
  'time': '13 min',
  'desc': 'Evidence over adjectives: the junior CV that gets replies.',
  'image': 'cv-and-interview.svg',
  'objectives': ['Structure a one-page CV around evidence',
                 'Match keywords to the job description',
                 'Walk through one project in an interview'],
  'exercise': 'Rewrite your own CV (or draft one) as a single page: three evidence bullets (lab, project, '
              'cert), tools used, and one line per skill the job asked for. Ask a friend to find the proof '
              'in ten seconds.',
  'content': ['Hiring managers scan for proof, not adjectives. “Lab-tested X, found Y, reported Z” beats '
              '“passionate about cybersecurity”. Every bullet should point at something you built, ran, or '
              'wrote.',
              "One page, tailored: mirror the job description's keywords and drop the rest. A tailored page "
              'that proves three skills beats a generic page that claims ten.',
              'In the interview, rehearse one project in full: goal, setup, what broke, what you found, what '
              'you fixed. Depth on one project signals readiness better than a tour of ten.'],
  'questions': [{'question': 'What should a junior security CV lead with?',
                 'choices': ['Adjectives like “passionate”',
                             'Evidence: labs, projects, certs and tools used',
                             'Hobby lists'],
                 'answer': 1,
                 'explain': 'Proof gets callbacks. Adjectives get skimmed.'},
                {'question': 'A job asks for “log analysis (Wazuh)” and your CV says “knowledge of tools”. '
                             'Fix it.',
                 'choices': ['Leave it, it covers everything',
                             'Name the tool and the task: “Built Wazuh rules in my lab; triaged 12 alerts, '
                             'tuned 2 false positives”',
                             'Add more adjectives'],
                 'answer': 1,
                 'explain': "Mirror the job's keywords with evidence attached. Specific beats generic."},
                {'question': 'Interviewers ask you to walk through one project. The strongest answer covers:',
                 'choices': ['Tools you have heard of',
                             'Goal, setup, what broke, what you found, what you fixed, in detail',
                             "The company's history"],
                 'answer': 1,
                 'explain': 'Depth on one project proves you can do the work, not just name the tools.'}]},
 {'slug': 'lab-building',
  'level': 'CAREER',
  'title': 'Build a home security lab',
  'time': '15 min',
  'desc': 'A VM, a target, snapshots, and a network you control.',
  'image': 'lab-building.svg',
  'objectives': ['Provision an isolated virtual lab',
                 'Snapshot before breaking anything',
                 'Plan two weeks of lab exercises'],
  'exercise': 'Set up a virtualiser with one Kali VM and one target VM on a host-only network. Snapshot '
              'both. In week one: one networking exercise, one log exercise. Week two: one web challenge, '
              'one report. Write the plan down.',
  'content': ['A home lab is the only place to learn offensive skills safely and legally: your machines, '
              'your network, your rules. A virtualiser gives you isolated VMs you can break and roll back in '
              'seconds.',
              'Use a host-only or lab-only network so practice traffic cannot leak onto the internet or your '
              'home devices. Snapshot before every experiment; a broken VM is a lesson, not a loss.',
              'Good labs are boring on purpose: update the VM, document the setup, keep one exercise per '
              'session, and write a short report after each. The notes are the product.'],
  'questions': [{'question': 'Why isolate the lab network?',
                 'choices': ['Faster internet',
                             'So practice traffic and experiments cannot reach the internet or your home '
                             'devices',
                             'Cheaper electricity'],
                 'answer': 1,
                 'explain': 'Host-only or lab LAN keeps experiments contained. That is the legal and safety '
                            'boundary.'},
                {'question': 'What is a VM snapshot for?',
                 'choices': ['Backup to the cloud',
                             'Reverting to a known-good state in seconds after an experiment breaks things',
                             'Faster CPU'],
                 'answer': 1,
                 'explain': 'Snapshot before you break. Rolling back keeps learning fast.'},
                {'question': 'Where does the write-up go?',
                 'choices': ['Nowhere',
                             'A dated lab journal: setup, exercise, findings, fixes. It becomes your '
                             'portfolio evidence',
                             'A video game'],
                 'answer': 1,
                 'explain': 'Notes are the product of a lab. They also become the evidence employers ask '
                            'for.'}]},
 {'slug': 'web-access-control',
  'level': 'WEB SECURITY',
  'title': 'Access control and IDOR',
  'time': '14 min',
  'desc': 'Broken access control and insecure direct object references.',
  'image': 'web-access-control.svg',
  'objectives': ['Distinguish authentication from authorisation',
                 'Explain IDOR with a real example',
                 'Apply deny-by-default thinking'],
  'exercise': 'In your lab app, find one object id that comes from the user (invoice, profile, file). Check '
              'whether the code verifies the logged-in user owns it. Write the test you ran and the result.',
  'content': ['Authorisation answers a different question from authentication. Login asks who you are; '
              'access control asks what you may touch. Broken access control is what happens when the second '
              'question is never asked on the server.',
              'An insecure direct object reference (IDOR) is the common shape: an invoice id, a document id, '
              "or a user id in the URL that the server trusts. Change the number, see someone else's data. "
              'The fix is an ownership check on every request, not a secret number.',
              'Deny by default: if the code cannot prove the user may see this object, refuse. Role checks '
              'belong on the server; hiding a button in the browser is decoration.'],
  'questions': [{'question': "A URL shows /invoice/1042 and changing it to 1043 shows another customer's "
                             'invoice. What is this?',
                 'choices': ['Server misconfiguration',
                             'IDOR / broken access control: the server trusts the object id without an '
                             'ownership check',
                             'A slow database'],
                 'answer': 1,
                 'explain': 'The server must verify the logged-in user owns invoice 1043. The number was '
                            'never a secret.'},
                {'question': 'A button is hidden in the browser for non-admin users, but the API endpoint '
                             'still responds to their requests. What is the flaw?',
                 'choices': ['The button is the wrong colour',
                             'Authorisation enforced only in the browser, not the server',
                             'A CSS bug'],
                 'answer': 1,
                 'explain': 'Hiding UI is not authorisation. The endpoint must check permissions itself.'},
                {'question': 'A new feature lets users export their own reports as CSV. The page checks '
                             'ownership. What should you ask?',
                 'choices': ['Is the export endpoint checking ownership too, and logging the export?',
                             'Is the CSV coloured?',
                             'Which font is used?'],
                 'answer': 0,
                 'explain': 'New endpoints are new attack surface. Every one needs the same authorisation '
                            'and logging as the page it feeds.'}]},
 {'slug': 'crypto-misconfig',
  'level': 'WEB SECURITY',
  'title': 'Cryptographic failures and misconfiguration',
  'time': '14 min',
  'desc': 'Weak crypto, default creds, verbose errors, debug modes.',
  'image': 'crypto-misconfig.svg',
  'objectives': ['Spot weak cryptography in a design',
                 'List common misconfigurations by memory',
                 'Explain why verbose errors leak information'],
  'exercise': 'Review a lab site you own: check for default credentials, debug mode, verbose error pages, '
              'and TLS settings. Write one line per issue: what you observed, the risk, the fix.',
  'content': ['Cryptographic failures are usually boring: home-grown ciphers, short keys, passwords stored '
              'reversibly, random numbers that are not random. The discipline is boring too: use proven '
              'libraries, long keys, and never invent crypto.',
              'Misconfiguration is the other half: default credentials, debug mode in production, sample '
              'pages left live, and verbose error messages that show stack traces, SQL, or file paths. Each '
              'one hands the attacker a map.',
              'Hardening is a checklist, not a vibe. Change defaults, turn debug off, strip sensitive detail '
              'from errors, and keep only the services and pages the site actually needs.'],
  'questions': [{'question': 'Passwords are stored with a fast reversible cipher so support can recover '
                             'them. What is wrong?',
                 'choices': ['It is not reversible',
                             'Recoverable passwords mean anyone who reads the store can reverse them; use a '
                             'slow one-way hash with a salt',
                             'Support dislikes it'],
                 'answer': 1,
                 'explain': 'One-way hashing makes the store useless to an attacker. Recoverable storage '
                            'defeats the purpose.'},
                {'question': 'A production error page prints the full SQL error, including the table name. '
                             'An auditor flags it. Why?',
                 'choices': ['SQL errors are ugly',
                             'Verbose errors leak schema details that make recon and injection easier',
                             'Errors are required by law'],
                 'answer': 1,
                 'explain': 'Error detail is recon material. Users get a generic message; details go to '
                            'server logs.'},
                {'question': 'A staging server with debug mode on is reachable from the internet. Best '
                             'response?',
                 'choices': ['Turn debug off or restrict access now, then investigate what was exposed',
                             'Ignore staging, it is not production',
                             'Rename the server'],
                 'answer': 0,
                 'explain': 'Debug and staging exposure are launch-blocking. Reachable staging is part of '
                            'the attack surface.'}]},
 {'slug': 'csrf-ssrf',
  'level': 'WEB SECURITY',
  'title': 'CSRF and SSRF',
  'time': '15 min',
  'desc': 'Forged requests and server-side request forgery.',
  'image': 'csrf-ssrf.svg',
  'objectives': ['Explain CSRF in one paragraph',
                 'Explain SSRF and why the server is the target',
                 'Apply SameSite and allowlist defences'],
  'exercise': 'In your lab app, trigger a state-changing action in the browser, then repeat it with a plain '
              'form from another origin. Note what SameSite or a CSRF token does to the result.',
  'content': ["Cross-site request forgery rides the victim's session: a malicious page makes the browser "
              'send a forged request to your app, and the browser helpfully attaches the cookies. The server '
              'sees a valid session and obeys.',
              'Server-side request forgery is the mirror image: the application itself fetches a URL the '
              'attacker supplies, and the attacker uses the server as a proxy into internal services, cloud '
              'metadata endpoints, or localhost admin panels.',
              'Defences are specific to each: SameSite cookies and anti-CSRF tokens for CSRF; for SSRF, an '
              'allowlist of hosts, no redirects to private addresses, and blocking of cloud metadata '
              'endpoints.'],
  'questions': [{'question': "A victim's browser sends a forged POST that transfers money because cookies "
                             'were attached. What attack is this?',
                 'choices': ['XSS', 'CSRF', 'SQL injection'],
                 'answer': 1,
                 'explain': 'The browser attaches the session automatically. SameSite cookies and anti-CSRF '
                            'tokens are the defences.'},
                {'question': 'The app fetches a user-supplied image URL, and the attacker supplies the cloud '
                             'metadata address 169.254.169.254. What is the flaw and fix?',
                 'choices': ['Slow image loading',
                             'SSRF: allowlist destinations and block metadata and private addresses',
                             'Missing CSS'],
                 'answer': 1,
                 'explain': 'The server must not fetch arbitrary attacker URLs. Allowlist hosts and block '
                            'link-local and private ranges.'},
                {'question': 'Which attack needs no user to click anything?',
                 'choices': ['CSRF', 'SSRF, the server makes the request on its own', 'Stored XSS'],
                 'answer': 1,
                 'explain': 'SSRF is driven server-side. No victim click is required, which is what makes it '
                            'dangerous.'}]},
 {'slug': 'secure-design',
  'level': 'WEB SECURITY',
  'title': 'Insecure design and logging failures',
  'time': '13 min',
  'desc': 'Threat modelling, safe defaults, and logging that actually helps.',
  'image': 'secure-design.svg',
  'objectives': ['Name insecure design patterns',
                 'Explain what security logging must capture',
                 'Write three logging fields for a login event'],
  'exercise': 'Take one lab feature and write three abuse cases it allows. Then list five log fields you '
              'would capture for each. Note which are missing today.',
  'content': ['Insecure design is the flaw that is not a bug: the feature works as coded, and as coded it '
              'invites abuse. Refund flows callers can double-call, rate limits that only exist in the UI, '
              'and trust in client-side totals are design flaws, not typos.',
              'Logging failures complete the pair. If a login endpoint does not log failed attempts, user, '
              'and source, nobody notices credential stuffing. If sensitive data is logged in plaintext, the '
              'logs become the breach.',
              'Good logging is event-based: who, what, when, where, outcome. Protect the logs, alert on '
              'patterns, and never log passwords or tokens.'],
  'questions': [{'question': 'A refund endpoint works correctly but can be called twice and both refunds '
                             'succeed. What kind of flaw is this?',
                 'choices': ['A typo',
                             'Insecure design: the feature has no abuse case in mind',
                             'A CSS issue'],
                 'answer': 1,
                 'explain': 'The code does what it says. The design never considered being called twice.'},
                {'question': 'A login endpoint logs only successful logins. An account is emptied by '
                             'credential stuffing. What is missing?',
                 'choices': ['Faster login',
                             'Security logging: failed attempts, account, and source',
                             'A bigger database'],
                 'answer': 1,
                 'explain': 'Without failed-attempt logging there is no detection and no investigation '
                            'trail.'},
                {'question': 'Logs contain full passwords for debugging. What is the correct action?',
                 'choices': ['Keep them, debugging matters',
                             'Stop immediately, purge or restrict the logs, and treat them as exposed '
                             'secrets',
                             'Encrypt the passwords in the logs'],
                 'answer': 1,
                 'explain': 'Passwords in logs are exposed secrets. Stop logging them and assess the '
                            'damage.'}]},
 {'slug': 'wifi-vpn-advanced',
  'level': 'NETWORK SECURITY',
  'title': 'Wireless and VPN security',
  'time': '14 min',
  'desc': 'WPA, enterprise auth, VPN types, and the mistakes that matter.',
  'image': 'wifi-vpn-advanced.svg',
  'objectives': ['Compare WPA2 and WPA3 protection',
                 'Explain site-to-site versus remote-access VPN',
                 'Spot weak pre-shared keys and split tunnelling'],
  'exercise': 'Check the Wi-Fi settings on a network you own: mode, cipher, admin password, WPS state. Write '
              'the three changes you would make first and why.',
  'content': ['Wireless security lives or dies on the handshake and the password. WPA2 with a short '
              'passphrase falls to offline cracking; WPA3 and long passphrases raise the cost enormously. '
              'Enterprise authentication moves the check to a server.',
              'Remote-access VPNs connect one user to the network; site-to-site VPNs join whole networks. '
              'Split tunnelling sends only some traffic through the tunnel, which is convenient and quietly '
              'risky.',
              'A VPN protects the path, not the endpoints. Weak pre-shared keys, unpatched clients, and '
              'split tunnels are where VPN security actually fails.'],
  'questions': [{'question': 'A home router uses WPA2-PSK with passphrase password123. What is the risk?',
                 'choices': ['None',
                             "Offline dictionary cracking: the handshake can be attacked at the attacker's "
                             'own speed, and short passphrases fall fast',
                             'WPA2 is always broken'],
                 'answer': 1,
                 'explain': 'WPA2 strength depends on passphrase length. Short passphrases are crackable '
                            'offline.'},
                {'question': "A laptop's VPN is split-tunnelled, so banking traffic goes direct. What is the "
                             'trade-off?',
                 'choices': ['No trade-off',
                             'Convenience and speed, bought by sending some traffic outside the tunnel',
                             'The VPN is off'],
                 'answer': 1,
                 'explain': 'Split tunnelling means some traffic skips the tunnel. That is a deliberate, '
                            'documented risk or a hole.'},
                {'question': 'A site-to-site VPN protects offices A and B. Traffic from A to the bank still '
                             "appears in plaintext on the bank's side. Why?",
                 'choices': ['The tunnel is broken',
                             'VPNs protect the path between endpoints, not destinations beyond them; TLS '
                             'handles the rest',
                             'Offices are too far apart'],
                 'answer': 1,
                 'explain': 'Encryption ends at the tunnel endpoint. End-to-end protections are separate '
                            'layers.'}]},
 {'slug': 'soc-logs',
  'level': 'NETWORK SECURITY',
  'title': 'SOC, logs and detection basics',
  'time': '16 min',
  'desc': 'How a security operations centre reads logs and builds detections.',
  'image': 'soc-logs.svg',
  'objectives': ['Explain what a SOC analyst does all day',
                 'Write one detection rule in plain language',
                 'Explain false positives and tuning'],
  'exercise': "Write one detection rule in plain English for your lab, e.g. 'more than 10 failed logins from "
              "one IP in 5 minutes'. Then list two legitimate things that would trigger it.",
  'content': ['A security operations centre watches telemetry: authentication logs, network flows, endpoint '
              'alerts, and cloud events. The job is triage: decide what is noise, what is worth a look, and '
              'what is an incident, in that order, quickly.',
              'Detections are written as rules over events: condition, threshold, window, action. A good '
              'rule names the attack pattern in plain language before it names a tool.',
              'False positives are the tax on detection. Every rule needs tuning: baselining normal '
              'behaviour, allowlisting known jobs, and retiring rules that only cry wolf.'],
  'questions': [{'question': 'A rule fires 4,000 times a day and nobody reads it. What is the right move?',
                 'choices': ['Delete all rules',
                             'Tune or retire it: an unread rule protects nothing and trains the team to '
                             'ignore alerts',
                             'Add more alerts'],
                 'answer': 1,
                 'explain': 'Alert fatigue is a detection failure. Tune the rule or remove it.'},
                {'question': "A detection says '10 failed logins from one IP in 5 minutes'. A legitimate "
                             'user mistype triggers it twice a week. What is the proper response?',
                 'choices': ['Disable the rule',
                             'Tune it: check the source, allowlist the known case, and keep the rule for '
                             'real attacks',
                             'Ignore all failed logins'],
                 'answer': 1,
                 'explain': 'Tuning keeps the rule and removes the noise. Disabling it removes the '
                            'protection.'},
                {'question': 'What does a SOC analyst spend most of the day doing?',
                 'choices': ['Attacking other companies',
                             'Triaging telemetry: separating noise from incidents, in minutes, with evidence',
                             'Writing marketing copy'],
                 'answer': 1,
                 'explain': 'Triage is the core skill: fast, evidence-based decisions under uncertainty.'}]},
 {'slug': 'what-is-cybersecurity',
  'level': 'START HERE',
  'title': 'What is cybersecurity?',
  'time': '8 min',
  'desc': 'The CIA triad in plain words, and why it matters to you.',
  'image': 'what-is-cybersecurity.svg',
  'objectives': ['Explain confidentiality, integrity and availability in one sentence each',
                 'Give one example of each from daily life',
                 'Say why all three matter together'],
  'exercise': 'Pick one account you use every day. Write one line for each promise: how it stays '
              'confidential, how it stays unchanged, how it stays available. Notice which promise is '
              'weakest.',
  'content': ['Cybersecurity is protecting information and systems from people who would steal, change, or '
              'break them. That is the whole subject. Everything else is technique.',
              'The field breaks into three promises, called the CIA triad. Confidentiality: only the right '
              'people can read it. Integrity: it is the same as when it was sent. Availability: it works '
              'when you need it.',
              'A leaked password breaks confidentiality. A changed bank balance breaks integrity. A hospital '
              'system offline breaks availability. Every lesson in this academy protects one of these '
              'three.'],
  'questions': [{'question': 'Which of these is confidentiality?',
                 'choices': ['The file exists when you need it',
                             'Only the right people can read it',
                             'The file is unchanged'],
                 'answer': 1,
                 'explain': 'Confidentiality is about who can read. Availability is about access, integrity '
                            'about change.'},
                {'question': 'Someone edits your school report after you submitted it. Which promise broke?',
                 'choices': ['Confidentiality',
                             'Integrity: the content changed without authority',
                             'Availability'],
                 'answer': 1,
                 'explain': 'Integrity means the thing is what it was supposed to be. Edited content breaks '
                            'it.'},
                {'question': "A shop's tills are down for a day and nobody can pay. Which promise broke?",
                 'choices': ['Confidentiality', 'Integrity', 'Availability'],
                 'answer': 2,
                 'explain': 'Availability is about the system working when needed.'}]},
 {'slug': 'why-hackers-attack',
  'level': 'START HERE',
  'title': 'Why hackers attack, and what they want',
  'time': '9 min',
  'desc': 'Money, data, access and fame: the real motives behind attacks.',
  'image': 'why-hackers-attack.svg',
  'objectives': ['Name the four main attacker motives',
                 'Explain why money is the most common one',
                 'Describe one attack you have heard of and its motive'],
  'exercise': 'Find one news headline about a hack you remember. Write three sentences: what happened, what '
              'the attacker wanted, and which of the four motives it matches.',
  'content': ['Real attackers are mostly in it for money. Ransomware locks a business and sells the key '
              'back. Fraud sells stolen accounts and cards. Same motive, different shops.',
              'Data is the second motive. Passwords, identity details and company secrets are sold in packs '
              'on criminal marketplaces, because one stolen record can be used a hundred times.',
              'Access is the third: a small company is attacked to reach the big company that trusts it. The '
              'fourth is fame: some attackers want to be known for the breach. That one is the rarest and '
              'the loudest.'],
  'questions': [{'question': 'A business pays $50,000 to get its files back after ransomware. What was the '
                             'motive?',
                 'choices': ['Fame', 'Money: the files were the hostage', 'Curiosity'],
                 'answer': 1,
                 'explain': 'Ransomware is a business model. The files are worthless to the attacker except '
                            'as leverage.'},
                {'question': "An attacker steals staff passwords, then uses them to attack the staff's big "
                             'client. What motive is this?',
                 'choices': ['Money only',
                             'Access and footholds: the small company is the door to the big one',
                             'A mistake'],
                 'answer': 1,
                 'explain': 'Supply-chain and trust attacks use a smaller target as a stepping stone.'},
                {'question': 'Which motive do the headlines talk about most, but happens least?',
                 'choices': ['Money', 'Fame and notoriety', 'Data selling'],
                 'answer': 1,
                 'explain': 'Famous solo attackers get the news. Organised money crimes get the volume.'}]},
 {'slug': 'how-the-internet-works',
  'level': 'START HERE',
  'title': 'How the internet works, in plain words',
  'time': '10 min',
  'desc': 'Names, packets and locks: the whole journey in four steps.',
  'image': 'how-the-internet-works.svg',
  'objectives': ['Explain what DNS does in one sentence',
                 'Describe a packet and a router',
                 'Say what TLS adds to a connection'],
  'exercise': 'Open a site you use daily. Note its name, then ask: what address did your browser find, which '
              'packets carried the page, and did a lock show in the address bar? Write the journey in four '
              'sentences.',
  'content': ['When you type a name like example.com, your browser first asks a directory called DNS: what '
              'address does this name point to? Names are for people, addresses are for machines.',
              'Your request then travels as packets, small labelled chunks, passed from router to router '
              'across the internet like postcards through sorting offices. They may take different roads and '
              'arrive in a different order.',
              'TLS is the lock. It scrambles the contents so nobody on the road can read them, and it proves '
              'the server is really the one you asked for. The padlock in the address bar means that lock is '
              'on.'],
  'questions': [{'question': 'What does DNS do?',
                 'choices': ['Encrypts websites',
                             'Turns a name into an address machines can use',
                             'Stores your passwords'],
                 'answer': 1,
                 'explain': 'DNS is the directory. You type names; machines use addresses.'},
                {'question': 'What is a router doing with your packets?',
                 'choices': ['Reading your emails',
                             'Passing each packet towards its destination, one hop at a time',
                             'Deleting packets'],
                 'answer': 1,
                 'explain': 'Routers forward. They do not read the contents, they move the chunks closer.'},
                {'question': 'You see a padlock in the address bar. What does it prove?',
                 'choices': ['The site is honest',
                             "The connection is encrypted and the server's certificate checked out",
                             'Your computer is safe'],
                 'answer': 1,
                 'explain': 'The padlock proves the lock is on and the server identity checked. It does not '
                            'prove the site is honest.'}]},
 {'slug': 'stay-safe-device',
  'level': 'START HERE',
  'title': 'Staying safe on your own phone and laptop',
  'time': '10 min',
  'desc': 'Four habits that stop most everyday digital crime.',
  'image': 'stay-safe-device.svg',
  'objectives': ['List the four habits and why each works',
                 'Check your own lock screen and update status',
                 'Spot a fake sender in a message'],
  'exercise': 'Do the five-minute check on your own device: lock screen set, passphrase strong, updates '
              'installed, backups done, unknown apps removed. Write down which one you had skipped.',
  'content': ['Most everyday digital crime is not rare hacking. It is a phone with no lock, an old system '
              'nobody updated, a message from a fake sender, or a scam that wiped the only copy of family '
              'photos.',
              'The four habits are boring on purpose. Lock the screen with a real passphrase. Install '
              'updates, because patches close doors attackers walk through. Check the sender address, not '
              'just the name. And back up, ideally in two places, so ransomware cannot take the only copy.',
              'None of these needs money or expertise. Done together, they stop the crimes that actually '
              'happen to normal people.'],
  'questions': [{'question': 'A thief picks up your unlocked phone for two minutes. What stopped nothing?',
                 'choices': ['The wallpaper',
                             'A screen lock with a real passphrase: that is what stands between a finder and '
                             'your accounts',
                             'The phone case'],
                 'answer': 1,
                 'explain': 'A lock is the wall. Everything else is behind it.'},
                {'question': 'Your laptop is two years behind on updates. What is the risk?',
                 'choices': ['Slower typing',
                             'Known flaws stay open: attackers use old, documented holes long after patches '
                             'exist',
                             'Nothing, old means tested'],
                 'answer': 1,
                 'explain': 'Unpatched systems are the easiest targets. Updates close known doors.'},
                {'question': "A message says 'Your bank: click here' from a strange address. What is the "
                             'habit that stops it?',
                 'choices': ['Replying to ask',
                             "Checking the sender address and going to the bank's real site yourself",
                             'Deleting the bank app'],
                 'answer': 1,
                 'explain': 'Never trust the sender name. Verify the address, and navigate yourself.'}]}]


ACADEMY_COURSES = [{'slug': 'course-foundations',
  'title': 'Cybersecurity Foundations',
  'tagline': 'Start here. What cybersecurity is, how the internet works, and your first real skills: '
             'networking, Linux, Nmap and reporting. Free, forever.',
  'level': 'BEGINNER',
  'plan': 0,
  'plan_label': 'FREE',
  'cover': 'course-foundations.svg',
  'lessons': ['what-is-cybersecurity',
              'why-hackers-attack',
              'how-the-internet-works',
              'stay-safe-device',
              'networking-essentials',
              'kali-linux-basics',
              'nmap-fundamentals',
              'http-tls-headers',
              'cve-triage',
              'security-reporting']},
 {'slug': 'course-webapp',
  'title': 'Web Application Security',
  'tagline': 'The OWASP Top 10 end to end: XSS, SQL injection, access control, CSRF, SSRF, crypto failures '
             "and secure design. The course that turns 'I know a bit about hacking websites' into something "
             'real.',
  'level': 'INTERMEDIATE',
  'plan': 1,
  'plan_label': 'PRO',
  'cover': 'course-webapp.svg',
  'lessons': ['owasp-top10',
              'xss-explained',
              'sqli-deep-dive',
              'auth-flaws',
              'web-access-control',
              'csrf-ssrf',
              'crypto-misconfig',
              'secure-design',
              'secure-code-review']},
 {'slug': 'course-network',
  'title': 'Network Security',
  'tagline': 'TCP handshakes, firewalls, VPNs, packet analysis, DNS attacks and how a SOC reads logs. If the '
             'web course is about breaking in, this one is about watching the door.',
  'level': 'INTERMEDIATE',
  'plan': 1,
  'plan_label': 'PRO',
  'cover': 'course-network.svg',
  'lessons': ['tcp-handshake',
              'firewalls-vpn',
              'packet-analysis',
              'dns-security',
              'wifi-vpn-advanced',
              'soc-logs']},
 {'slug': 'course-email',
  'title': 'Email & Phishing Defense',
  'tagline': 'SPF, DKIM and DMARC in depth, the anatomy of a phishing email, and the social engineering '
             'plays behind both. The course that makes you see every inbox differently.',
  'level': 'INTERMEDIATE',
  'plan': 2,
  'plan_label': 'PRO PLUS',
  'cover': 'course-email.svg',
  'lessons': ['spf-dkim-dmarc-deep', 'phishing-anatomy', 'social-engineering']},
 {'slug': 'course-forensics',
  'title': 'Digital Forensics & Incident Response',
  'tagline': 'The incident lifecycle, evidence handling that holds up in court, and a practical '
             'first-24-hours playbook for when something actually breaks.',
  'level': 'INTERMEDIATE',
  'plan': 2,
  'plan_label': 'PRO PLUS',
  'cover': 'course-forensics.svg',
  'lessons': ['forensics-process', 'evidence-handling', 'ir-playbook']},
 {'slug': 'course-career',
  'title': 'Career Path & Certifications',
  'tagline': 'Security+ and CEH road maps, red team versus blue team roles, CVs, interviews, and building '
             'the home lab that proves all of it. Your bridge from lessons to a job.',
  'level': 'ALL LEVELS',
  'plan': 2,
  'plan_label': 'PRO PLUS',
  'cover': 'course-career.svg',
  'lessons': ['secplus-roadmap', 'ceh-vs-blue-team', 'cv-and-interview', 'lab-building']}]


def get_course_for_lesson(slug):
    for c in ACADEMY_COURSES:
        if slug in c["lessons"]:
            return c
    return None

def get_lesson(slug):
    for l in ACADEMY_LESSONS:
        if l["slug"] == slug:
            return l
    return None

def course_lessons(course):
    by = {l["slug"]: l for l in ACADEMY_LESSONS}
    return [by[s] for s in course["lessons"] if s in by]
