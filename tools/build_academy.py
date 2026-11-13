#!/usr/bin/env python3
"""Assemble the final academy_questions.py:
- existing 6 lessons kept verbatim (slugs/content/questions), only extra keys added
- 25 new lessons from the catalogue builder
- 6 courses, flat list kept for backward compatibility
"""
import importlib.util, pprint, json

ROOT = "/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/academy-course"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

old_mod = load("old_academy", ROOT + "/academy_questions.py")
old = old_mod.ACADEMY_LESSONS

ns = {}
exec(open("/tmp/new_lessons_code.py").read(), ns)
new = ns["NEW_LESSONS"]

def L(slug, level, title, time, desc, image, objectives, exercise, content, questions):
    return {"slug": slug, "level": level, "title": title, "time": time, "desc": desc, "image": image,
            "objectives": objectives, "exercise": exercise, "content": content, "questions": questions}

def Q(q, choices, answer, explain):
    return {"question": q, "choices": choices, "answer": answer, "explain": explain}

extra = [
L("web-access-control","WEB SECURITY","Access control and IDOR","14 min",
  "Broken access control and insecure direct object references.",
  "web-access-control.svg",
  ["Distinguish authentication from authorisation","Explain IDOR with a real example","Apply deny-by-default thinking"],
  "In your lab app, find one object id that comes from the user (invoice, profile, file). Check whether the code verifies the logged-in user owns it. Write the test you ran and the result.",
  ["Authorisation answers a different question from authentication. Login asks who you are; access control asks what you may touch. Broken access control is what happens when the second question is never asked on the server.",
   "An insecure direct object reference (IDOR) is the common shape: an invoice id, a document id, or a user id in the URL that the server trusts. Change the number, see someone else's data. The fix is an ownership check on every request, not a secret number.",
   "Deny by default: if the code cannot prove the user may see this object, refuse. Role checks belong on the server; hiding a button in the browser is decoration."],
  [Q("A URL shows /invoice/1042 and changing it to 1043 shows another customer's invoice. What is this?",
     ["Server misconfiguration","IDOR / broken access control: the server trusts the object id without an ownership check","A slow database"],1,
     "The server must verify the logged-in user owns invoice 1043. The number was never a secret."),
   Q("A button is hidden in the browser for non-admin users, but the API endpoint still responds to their requests. What is the flaw?",
     ["The button is the wrong colour","Authorisation enforced only in the browser, not the server","A CSS bug"],1,
     "Hiding UI is not authorisation. The endpoint must check permissions itself."),
   Q("A new feature lets users export their own reports as CSV. The page checks ownership. What should you ask?",
     ["Is the export endpoint checking ownership too, and logging the export?","Is the CSV coloured?","Which font is used?"],0,
     "New endpoints are new attack surface. Every one needs the same authorisation and logging as the page it feeds.")]),
L("crypto-misconfig","WEB SECURITY","Cryptographic failures and misconfiguration","14 min",
  "Weak crypto, default creds, verbose errors, debug modes.",
  "crypto-misconfig.svg",
  ["Spot weak cryptography in a design","List common misconfigurations by memory","Explain why verbose errors leak information"],
  "Review a lab site you own: check for default credentials, debug mode, verbose error pages, and TLS settings. Write one line per issue: what you observed, the risk, the fix.",
  ["Cryptographic failures are usually boring: home-grown ciphers, short keys, passwords stored reversibly, random numbers that are not random. The discipline is boring too: use proven libraries, long keys, and never invent crypto.",
   "Misconfiguration is the other half: default credentials, debug mode in production, sample pages left live, and verbose error messages that show stack traces, SQL, or file paths. Each one hands the attacker a map.",
   "Hardening is a checklist, not a vibe. Change defaults, turn debug off, strip sensitive detail from errors, and keep only the services and pages the site actually needs."],
  [Q("Passwords are stored with a fast reversible cipher so support can recover them. What is wrong?",
     ["It is not reversible","Recoverable passwords mean anyone who reads the store can reverse them; use a slow one-way hash with a salt","Support dislikes it"],1,
     "One-way hashing makes the store useless to an attacker. Recoverable storage defeats the purpose."),
   Q("A production error page prints the full SQL error, including the table name. An auditor flags it. Why?",
     ["SQL errors are ugly","Verbose errors leak schema details that make recon and injection easier","Errors are required by law"],1,
     "Error detail is recon material. Users get a generic message; details go to server logs."),
   Q("A staging server with debug mode on is reachable from the internet. Best response?",
     ["Turn debug off or restrict access now, then investigate what was exposed","Ignore staging, it is not production","Rename the server"],0,
     "Debug and staging exposure are launch-blocking. Reachable staging is part of the attack surface.")]),
L("csrf-ssrf","WEB SECURITY","CSRF and SSRF","15 min",
  "Forged requests and server-side request forgery.",
  "csrf-ssrf.svg",
  ["Explain CSRF in one paragraph","Explain SSRF and why the server is the target","Apply SameSite and allowlist defences"],
  "In your lab app, trigger a state-changing action in the browser, then repeat it with a plain form from another origin. Note what SameSite or a CSRF token does to the result.",
  ["Cross-site request forgery rides the victim's session: a malicious page makes the browser send a forged request to your app, and the browser helpfully attaches the cookies. The server sees a valid session and obeys.",
   "Server-side request forgery is the mirror image: the application itself fetches a URL the attacker supplies, and the attacker uses the server as a proxy into internal services, cloud metadata endpoints, or localhost admin panels.",
   "Defences are specific to each: SameSite cookies and anti-CSRF tokens for CSRF; for SSRF, an allowlist of hosts, no redirects to private addresses, and blocking of cloud metadata endpoints."],
  [Q("A victim's browser sends a forged POST that transfers money because cookies were attached. What attack is this?",
     ["XSS","CSRF","SQL injection"],1,
     "The browser attaches the session automatically. SameSite cookies and anti-CSRF tokens are the defences."),
   Q("The app fetches a user-supplied image URL, and the attacker supplies the cloud metadata address 169.254.169.254. What is the flaw and fix?",
     ["Slow image loading","SSRF: allowlist destinations and block metadata and private addresses","Missing CSS"],1,
     "The server must not fetch arbitrary attacker URLs. Allowlist hosts and block link-local and private ranges."),
   Q("Which attack needs no user to click anything?",
     ["CSRF","SSRF, the server makes the request on its own","Stored XSS"],1,
     "SSRF is driven server-side. No victim click is required, which is what makes it dangerous.")]),
L("secure-design","WEB SECURITY","Insecure design and logging failures","13 min",
  "Threat modelling, safe defaults, and logging that actually helps.",
  "secure-design.svg",
  ["Name insecure design patterns","Explain what security logging must capture","Write three logging fields for a login event"],
  "Take one lab feature and write three abuse cases it allows. Then list five log fields you would capture for each. Note which are missing today.",
  ["Insecure design is the flaw that is not a bug: the feature works as coded, and as coded it invites abuse. Refund flows callers can double-call, rate limits that only exist in the UI, and trust in client-side totals are design flaws, not typos.",
   "Logging failures complete the pair. If a login endpoint does not log failed attempts, user, and source, nobody notices credential stuffing. If sensitive data is logged in plaintext, the logs become the breach.",
   "Good logging is event-based: who, what, when, where, outcome. Protect the logs, alert on patterns, and never log passwords or tokens."],
  [Q("A refund endpoint works correctly but can be called twice and both refunds succeed. What kind of flaw is this?",
     ["A typo","Insecure design: the feature has no abuse case in mind","A CSS issue"],1,
     "The code does what it says. The design never considered being called twice."),
   Q("A login endpoint logs only successful logins. An account is emptied by credential stuffing. What is missing?",
     ["Faster login","Security logging: failed attempts, account, and source","A bigger database"],1,
     "Without failed-attempt logging there is no detection and no investigation trail."),
   Q("Logs contain full passwords for debugging. What is the correct action?",
     ["Keep them, debugging matters","Stop immediately, purge or restrict the logs, and treat them as exposed secrets","Encrypt the passwords in the logs"],1,
     "Passwords in logs are exposed secrets. Stop logging them and assess the damage.")]),
L("wifi-vpn-advanced","NETWORK SECURITY","Wireless and VPN security","14 min",
  "WPA, enterprise auth, VPN types, and the mistakes that matter.",
  "wifi-vpn-advanced.svg",
  ["Compare WPA2 and WPA3 protection","Explain site-to-site versus remote-access VPN","Spot weak pre-shared keys and split tunnelling"],
  "Check the Wi-Fi settings on a network you own: mode, cipher, admin password, WPS state. Write the three changes you would make first and why.",
  ["Wireless security lives or dies on the handshake and the password. WPA2 with a short passphrase falls to offline cracking; WPA3 and long passphrases raise the cost enormously. Enterprise authentication moves the check to a server.",
   "Remote-access VPNs connect one user to the network; site-to-site VPNs join whole networks. Split tunnelling sends only some traffic through the tunnel, which is convenient and quietly risky.",
   "A VPN protects the path, not the endpoints. Weak pre-shared keys, unpatched clients, and split tunnels are where VPN security actually fails."],
  [Q("A home router uses WPA2-PSK with passphrase password123. What is the risk?",
     ["None","Offline dictionary cracking: the handshake can be attacked at the attacker's own speed, and short passphrases fall fast","WPA2 is always broken"],1,
     "WPA2 strength depends on passphrase length. Short passphrases are crackable offline."),
   Q("A laptop's VPN is split-tunnelled, so banking traffic goes direct. What is the trade-off?",
     ["No trade-off","Convenience and speed, bought by sending some traffic outside the tunnel","The VPN is off"],1,
     "Split tunnelling means some traffic skips the tunnel. That is a deliberate, documented risk or a hole."),
   Q("A site-to-site VPN protects offices A and B. Traffic from A to the bank still appears in plaintext on the bank's side. Why?",
     ["The tunnel is broken","VPNs protect the path between endpoints, not destinations beyond them; TLS handles the rest","Offices are too far apart"],1,
     "Encryption ends at the tunnel endpoint. End-to-end protections are separate layers.")]),
L("soc-logs","NETWORK SECURITY","SOC, logs and detection basics","16 min",
  "How a security operations centre reads logs and builds detections.",
  "soc-logs.svg",
  ["Explain what a SOC analyst does all day","Write one detection rule in plain language","Explain false positives and tuning"],
  "Write one detection rule in plain English for your lab, e.g. 'more than 10 failed logins from one IP in 5 minutes'. Then list two legitimate things that would trigger it.",
  ["A security operations centre watches telemetry: authentication logs, network flows, endpoint alerts, and cloud events. The job is triage: decide what is noise, what is worth a look, and what is an incident, in that order, quickly.",
   "Detections are written as rules over events: condition, threshold, window, action. A good rule names the attack pattern in plain language before it names a tool.",
   "False positives are the tax on detection. Every rule needs tuning: baselining normal behaviour, allowlisting known jobs, and retiring rules that only cry wolf."],
  [Q("A rule fires 4,000 times a day and nobody reads it. What is the right move?",
     ["Delete all rules","Tune or retire it: an unread rule protects nothing and trains the team to ignore alerts","Add more alerts"],1,
     "Alert fatigue is a detection failure. Tune the rule or remove it."),
   Q("A detection says '10 failed logins from one IP in 5 minutes'. A legitimate user mistype triggers it twice a week. What is the proper response?",
     ["Disable the rule","Tune it: check the source, allowlist the known case, and keep the rule for real attacks","Ignore all failed logins"],1,
     "Tuning keeps the rule and removes the noise. Disabling it removes the protection."),
   Q("What does a SOC analyst spend most of the day doing?",
     ["Attacking other companies","Triaging telemetry: separating noise from incidents, in minutes, with evidence","Writing marketing copy"],1,
     "Triage is the core skill: fast, evidence-based decisions under uncertainty.")]),
# --- Start Here (absolute zero) ---
L("what-is-cybersecurity","START HERE","What is cybersecurity?","8 min",
  "The CIA triad in plain words, and why it matters to you.",
  "what-is-cybersecurity.svg",
  ["Explain confidentiality, integrity and availability in one sentence each","Give one example of each from daily life","Say why all three matter together"],
  "Pick one account you use every day. Write one line for each promise: how it stays confidential, how it stays unchanged, how it stays available. Notice which promise is weakest.",
  ["Cybersecurity is protecting information and systems from people who would steal, change, or break them. That is the whole subject. Everything else is technique.",
   "The field breaks into three promises, called the CIA triad. Confidentiality: only the right people can read it. Integrity: it is the same as when it was sent. Availability: it works when you need it.",
   "A leaked password breaks confidentiality. A changed bank balance breaks integrity. A hospital system offline breaks availability. Every lesson in this academy protects one of these three."],
  [Q("Which of these is confidentiality?",
     ["The file exists when you need it","Only the right people can read it","The file is unchanged"],1,
     "Confidentiality is about who can read. Availability is about access, integrity about change."),
   Q("Someone edits your school report after you submitted it. Which promise broke?",
     ["Confidentiality","Integrity: the content changed without authority","Availability"],1,
     "Integrity means the thing is what it was supposed to be. Edited content breaks it."),
   Q("A shop's tills are down for a day and nobody can pay. Which promise broke?",
     ["Confidentiality","Integrity","Availability"],2,
     "Availability is about the system working when needed.")]),
L("why-hackers-attack","START HERE","Why hackers attack, and what they want","9 min",
  "Money, data, access and fame: the real motives behind attacks.",
  "why-hackers-attack.svg",
  ["Name the four main attacker motives","Explain why money is the most common one","Describe one attack you have heard of and its motive"],
  "Find one news headline about a hack you remember. Write three sentences: what happened, what the attacker wanted, and which of the four motives it matches.",
  ["Real attackers are mostly in it for money. Ransomware locks a business and sells the key back. Fraud sells stolen accounts and cards. Same motive, different shops.",
   "Data is the second motive. Passwords, identity details and company secrets are sold in packs on criminal marketplaces, because one stolen record can be used a hundred times.",
   "Access is the third: a small company is attacked to reach the big company that trusts it. The fourth is fame: some attackers want to be known for the breach. That one is the rarest and the loudest."],
  [Q("A business pays $50,000 to get its files back after ransomware. What was the motive?",
     ["Fame","Money: the files were the hostage","Curiosity"],1,
     "Ransomware is a business model. The files are worthless to the attacker except as leverage."),
   Q("An attacker steals staff passwords, then uses them to attack the staff's big client. What motive is this?",
     ["Money only","Access and footholds: the small company is the door to the big one","A mistake"],1,
     "Supply-chain and trust attacks use a smaller target as a stepping stone."),
   Q("Which motive do the headlines talk about most, but happens least?",
     ["Money","Fame and notoriety","Data selling"],1,
     "Famous solo attackers get the news. Organised money crimes get the volume.")]),
L("how-the-internet-works","START HERE","How the internet works, in plain words","10 min",
  "Names, packets and locks: the whole journey in four steps.",
  "how-the-internet-works.svg",
  ["Explain what DNS does in one sentence","Describe a packet and a router","Say what TLS adds to a connection"],
  "Open a site you use daily. Note its name, then ask: what address did your browser find, which packets carried the page, and did a lock show in the address bar? Write the journey in four sentences.",
  ["When you type a name like example.com, your browser first asks a directory called DNS: what address does this name point to? Names are for people, addresses are for machines.",
   "Your request then travels as packets, small labelled chunks, passed from router to router across the internet like postcards through sorting offices. They may take different roads and arrive in a different order.",
   "TLS is the lock. It scrambles the contents so nobody on the road can read them, and it proves the server is really the one you asked for. The padlock in the address bar means that lock is on."],
  [Q("What does DNS do?",
     ["Encrypts websites","Turns a name into an address machines can use","Stores your passwords"],1,
     "DNS is the directory. You type names; machines use addresses."),
   Q("What is a router doing with your packets?",
     ["Reading your emails","Passing each packet towards its destination, one hop at a time","Deleting packets"],1,
     "Routers forward. They do not read the contents, they move the chunks closer."),
   Q("You see a padlock in the address bar. What does it prove?",
     ["The site is honest","The connection is encrypted and the server's certificate checked out","Your computer is safe"],1,
     "The padlock proves the lock is on and the server identity checked. It does not prove the site is honest.")]),
L("stay-safe-device","START HERE","Staying safe on your own phone and laptop","10 min",
  "Four habits that stop most everyday digital crime.",
  "stay-safe-device.svg",
  ["List the four habits and why each works","Check your own lock screen and update status","Spot a fake sender in a message"],
  "Do the five-minute check on your own device: lock screen set, passphrase strong, updates installed, backups done, unknown apps removed. Write down which one you had skipped.",
  ["Most everyday digital crime is not rare hacking. It is a phone with no lock, an old system nobody updated, a message from a fake sender, or a scam that wiped the only copy of family photos.",
   "The four habits are boring on purpose. Lock the screen with a real passphrase. Install updates, because patches close doors attackers walk through. Check the sender address, not just the name. And back up, ideally in two places, so ransomware cannot take the only copy.",
   "None of these needs money or expertise. Done together, they stop the crimes that actually happen to normal people."],
  [Q("A thief picks up your unlocked phone for two minutes. What stopped nothing?",
     ["The wallpaper","A screen lock with a real passphrase: that is what stands between a finder and your accounts","The phone case"],1,
     "A lock is the wall. Everything else is behind it."),
   Q("Your laptop is two years behind on updates. What is the risk?",
     ["Slower typing","Known flaws stay open: attackers use old, documented holes long after patches exist","Nothing, old means tested"],1,
     "Unpatched systems are the easiest targets. Updates close known doors."),
   Q("A message says 'Your bank: click here' from a strange address. What is the habit that stops it?",
     ["Replying to ask","Checking the sender address and going to the bank's real site yourself","Deleting the bank app"],1,
     "Never trust the sender name. Verify the address, and navigate yourself.")]),
]

# patch old lessons with the new keys (image/objectives/exercise)
PATCH = {
"networking-essentials": (
 "networking-essentials.svg",
 ["Explain IP, port, TCP, UDP and DNS in one sentence each","Interpret A and MX DNS answers","Correct the myth that an open port means compromise"],
 "In your lab, run `ss -tlnp` (or `netstat -tlnp`) and list the listening services. Read one DNS A answer and one MX answer with dig. Write two sentences: what is listening, and where mail for the domain goes."),
"kali-linux-basics": (
 "kali-linux-basics.svg",
 ["Navigate with pwd, ls, cd and whoami","Inspect network interfaces with ip addr","Apply safe lab habits before running unfamiliar tools"],
 "In a VM, practise pwd, ls -la, cd .. and whoami, then check ip addr and note your interfaces. Find one online guide that suggests piping a script into bash and list three reasons you would not run it."),
"nmap-fundamentals": (
 "nmap-fundamentals.svg",
 ["Interpret open, closed and filtered port states","Use -sV and port selection deliberately","Avoid naming a CVE from a banner alone"],
 "In your lab, run `nmap -sV -p 22,80,443 127.0.0.1` and write each port's state. Add a firewall rule that drops one port, re-scan, and note what changed from closed to filtered."),
"http-tls-headers": (
 "http-tls-headers.svg",
 ["Read an HTTP request and response","Explain status codes 200, 301, 401, 403, 404","Verify HSTS and CSP on a real site"],
 "Run `curl -sI https://cyberlord.name.ng` and note the status, Strict-Transport-Security and Content-Security-Policy headers. Curl the http version and confirm it redirects to https. Write one line per finding."),
"cve-triage": (
 "cve-triage.svg",
 ["Match a CVE to product, version and configuration","Prioritise by exposure and impact, not score alone","Apply compensating controls when patching must wait"],
 "Pick one CVE from your lab inventory. Run it through the four gates: product, version, exposure, impact. Decide: patch now, compensating controls, or schedule. Write your one-sentence rationale and the evidence behind it."),
"security-reporting": (
 "security-reporting.svg",
 ["Structure a finding: title, asset, evidence, impact, fix","Separate observations from assumptions","Flag out-of-scope items without overstating them"],
 "Take one lab observation (a listening service or a missing header) and write a full finding: title, asset, reproducible evidence, impact, remediation, retest step. Ask a friend what they would do next."),
}
for l in old:
    img, obj, ex = PATCH[l["slug"]]
    l["image"] = img; l["objectives"] = obj; l["exercise"] = ex

all_lessons = old + new + extra
by = {l["slug"]: l for l in all_lessons}

COURSES = [
 {"slug":"course-foundations","title":"Cybersecurity Foundations","tagline":"Start here. What cybersecurity is, how the internet works, and your first real skills: networking, Linux, Nmap and reporting. Free, forever.","level":"BEGINNER","plan":0,"plan_label":"FREE","cover":"course-foundations.svg",
  "lessons":["what-is-cybersecurity","why-hackers-attack","how-the-internet-works","stay-safe-device","networking-essentials","kali-linux-basics","nmap-fundamentals","http-tls-headers","cve-triage","security-reporting"]},
 {"slug":"course-webapp","title":"Web Application Security","tagline":"The OWASP Top 10 end to end: XSS, SQL injection, access control, CSRF, SSRF, crypto failures and secure design. The course that turns 'I know a bit about hacking websites' into something real.","level":"INTERMEDIATE","plan":1,"plan_label":"PRO","cover":"course-webapp.svg",
  "lessons":["owasp-top10","xss-explained","sqli-deep-dive","auth-flaws","web-access-control","csrf-ssrf","crypto-misconfig","secure-design","secure-code-review"]},
 {"slug":"course-network","title":"Network Security","tagline":"TCP handshakes, firewalls, VPNs, packet analysis, DNS attacks and how a SOC reads logs. If the web course is about breaking in, this one is about watching the door.","level":"INTERMEDIATE","plan":1,"plan_label":"PRO","cover":"course-network.svg",
  "lessons":["tcp-handshake","firewalls-vpn","packet-analysis","dns-security","wifi-vpn-advanced","soc-logs"]},
 {"slug":"course-email","title":"Email & Phishing Defense","tagline":"SPF, DKIM and DMARC in depth, the anatomy of a phishing email, and the social engineering plays behind both. The course that makes you see every inbox differently.","level":"INTERMEDIATE","plan":2,"plan_label":"PRO PLUS","cover":"course-email.svg",
  "lessons":["spf-dkim-dmarc-deep","phishing-anatomy","social-engineering"]},
 {"slug":"course-forensics","title":"Digital Forensics & Incident Response","tagline":"The incident lifecycle, evidence handling that holds up in court, and a practical first-24-hours playbook for when something actually breaks.","level":"INTERMEDIATE","plan":2,"plan_label":"PRO PLUS","cover":"course-forensics.svg",
  "lessons":["forensics-process","evidence-handling","ir-playbook"]},
 {"slug":"course-career","title":"Career Path & Certifications","tagline":"Security+ and CEH road maps, red team versus blue team roles, CVs, interviews, and building the home lab that proves all of it. Your bridge from lessons to a job.","level":"ALL LEVELS","plan":2,"plan_label":"PRO PLUS","cover":"course-career.svg",
  "lessons":["secplus-roadmap","ceh-vs-blue-team","cv-and-interview","lab-building"]},
]

# validation
total_course_lessons = sum(len(c["lessons"]) for c in COURSES)
orphans = [l["slug"] for l in all_lessons if not any(l["slug"] in c["lessons"] for c in COURSES)]
missing = [s for c in COURSES for s in c["lessons"] if s not in by]
print("lessons total:", len(all_lessons))
print("course slots:", total_course_lessons)
print("orphans (in no course):", orphans)
print("missing slugs:", missing)
print("min questions:", min(len(l["questions"]) for l in all_lessons))
print("lessons with no image:", [l["slug"] for l in all_lessons if not l.get("image")])
print("answers not at index 0:", sum(1 for l in all_lessons if any(q["answer"] != 0 for q in l["questions"])), "of", len(all_lessons))
import os
for l in all_lessons:
    p = os.path.join(ROOT, "static", "academy", l["image"])
    if not os.path.exists(p):
        print("IMAGE MISSING:", l["slug"], l["image"])
for c in COURSES:
    p = os.path.join(ROOT, "static", "academy", c["cover"])
    print("cover ok" if os.path.exists(p) else "COVER MISSING", c["cover"])

json.dump({"lessons": all_lessons, "courses": COURSES}, open("/tmp/academy_data.json", "w"), indent=1)
print("saved /tmp/academy_data.json")
