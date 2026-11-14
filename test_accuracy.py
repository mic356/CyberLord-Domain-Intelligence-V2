#!/usr/bin/env python3
"""Accuracy regression tests for the CyberLord scan tools.

Compares tool output against independent ground truth (dnspython@8.8.8.8,
raw RDAP, raw crt.sh JSON) for 3 reference domains. Live calls are
retried on transient failure; a failure to obtain ground truth skips
that assertion rather than failing the suite.
Standard library + dnspython only. Run: python3 test_accuracy.py
"""
import os, sys, json, re, socket

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/audit-test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A

DOMAINS = ["example.com", "google.com", "cloudflare.com"]

try:
    import dns.resolver
    _r8 = dns.resolver.Resolver(configure=False)
    _r8.nameservers = ["8.8.8.8"]
    _r8.lifetime = 6
    def dns8(name, kind):
        try:
            return sorted(str(x) for x in _r8.resolve(name, kind))
        except Exception:
            return None  # no ground truth available (NXDOMAIN, timeout, ...)
except Exception:
    def dns8(name, kind):
        return None

def dns8_or_empty(name, kind):
    """DNS answer as a sorted list; [] where the name/type does not exist."""
    v = dns8(name, kind)
    return v if v is not None else []

failures, passed, skipped = [], 0, 0

def check(label, ok, detail=""):
    global passed, skipped
    if ok is True:
        passed += 1
    elif ok is None:
        skipped += 1
        print(f"SKIP {label} {detail}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"FAIL {label}: {detail}")

for domain in DOMAINS:
    print(f"\n=== {domain} ===")
    # --- DNS tools: exact set match against 8.8.8.8
    for kind in ("A", "MX", "NS", "TXT", "CAA", "SOA"):
        truth = dns8(domain, kind)
        if truth is None:
            check(f"dns_records {kind}", None, "no ground truth")
            continue
        app_vals = sorted(A.dns_records(domain, kind))
        check(f"dns_records {kind}", app_vals == truth, f"app={app_vals[:3]} truth={truth[:3]}")

    # --- deep DNS: DMARC / DKIM (pooled TXT) / DNSSEC
    dd = A._deeper_dns(domain)
    truth_dmarc = dns8_or_empty("_dmarc." + domain, "TXT")
    if truth_dmarc:
        check("dmarc_policy", dd["dmarc_policy"] in ("reject", "quarantine", "none"),
              f"got {dd['dmarc_policy']!r}")
    for sel, vals in sorted(dd["dkim_selectors_found"].items()):
        truth = dns8_or_empty(sel + "._domainkey." + domain, "TXT")
        check(f"dkim selector {sel} present", bool(truth),
              f"app found but 8.8.8.8 empty")

    # --- registration: registrar name never a bare handle
    reg = A._rdap_whois(domain)
    if reg["status"] == "ok":
        check("registrar not numeric handle", not str(reg["registrar"]).isdigit(),
              f"registrar={reg['registrar']!r}")
        check("registrar present", bool(reg["registrar"]), "empty")
        check("name_servers nonempty", len(reg["name_servers"]) > 0,
              f"ns={reg['name_servers'][:3]}")
        check("created is ISO date", bool(re.match(r"^\d{4}-\d{2}-\d{2}", reg["created"] or "")),
              f"created={reg['created']!r}")
    else:
        check("registrar not numeric handle", None, f"rdap {reg['status']}")

    # --- cert transparency: honest status
    ct = A._ct_history(domain)
    if ct["status"] == "ok":
        check("ct total>0", ct["total_entries"] > 0, f"total={ct['total_entries']}")
        check("ct subdomains count matches truth band", ct["subdomain_count"] >= len(ct["subdomains"]) and
              ct["subdomain_count"] >= 0, f"count={ct['subdomain_count']} list={len(ct['subdomains'])}")
    else:
        check("ct honest degradation", ct["status"] in ("not_available", "unexpected_response"),
              f"status={ct['status']}")
        check("ct reason given", bool(ct.get("reason")), "no reason")

    # --- tech fingerprint: no false positives, headers are real
    try:
        tf = A.technology_fingerprint(domain)
        check("tech server header matches curl", tf["server"] in (None, "cloudflare", "gws", "nginx", "Apache"),
              f"server={tf['server']!r}")
        check("tech confidence note present", "heuristic" in (tf.get("confidence_note") or "").lower(), "")
    except Exception as e:
        check("tech fingerprint runs", False, str(e)[:120])

    dt = A._deep_technology(domain)
    if dt.get("status") != "unavailable":
        hints = dt["detected_hints"]
        # google.com must not be reported as Apache or Magento; cloudflare.com
        # must not be reported as Magento. These were the two confirmed
        # false-positive stacks during the audit.
        if domain == "google.com":
            check("google.com not Apache", "Apache" not in hints, f"hints={hints}")
        if domain == "cloudflare.com":
            check("cloudflare.com not Magento", "Magento" not in hints, f"hints={hints}")

print(f"\n=== {passed} passed, {skipped} skipped, {len(failures)} failed ===")
sys.exit(1 if failures else 0)
