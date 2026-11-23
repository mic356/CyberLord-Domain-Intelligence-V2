"""CyberLord restricted scan worker.

Only scans domains explicitly listed in KALI_ALLOWED_DOMAINS and only after
the caller confirms authorization. Designed to run as a separate Render
Web Service using the included Dockerfile.
"""
import hmac
import ipaddress
import os
import re
import shutil
import socket
import subprocess

import phonenumbers
import phonenumbers.carrier
import phonenumbers.timezone
from flask import Flask, jsonify, request

app = Flask(__name__)

TOKEN = os.environ.get("KALI_WORKER_TOKEN", "").strip()


def load_allowed_domains():
    """Accept comma-, semicolon-, or newline-separated domain names."""
    raw = os.environ.get("KALI_ALLOWED_DOMAINS", "")
    entries = re.split(r"[,;\n\r]+", raw)
    domains = set()
    for entry in entries:
        domain = entry.strip().lower().rstrip(".").lstrip(".")
        if domain:
            domains.add(domain)
    return domains


ALLOWED_DOMAINS = load_allowed_domains()


def authorized(host):
    return any(host == domain or host.endswith("." + domain)
               for domain in ALLOWED_DOMAINS)


def require_token():
    supplied = request.headers.get("Authorization", "")
    expected = "Bearer " + TOKEN
    return bool(TOKEN) and hmac.compare_digest(supplied, expected)


def resolve_public(host):
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Target did not resolve")
    ips = sorted({record[4][0] for record in records})
    if not ips:
        raise ValueError("Target did not resolve")
    for value in ips:
        if not ipaddress.ip_address(value).is_global:
            raise ValueError("Only public IP targets are permitted")
    return ips


def run_command(args, timeout=90):
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-3000:],
    }


def valid_domain(host):
    return bool(re.fullmatch(
        r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
        host,
    ))


@app.get("/health")
def health():
    # Do not expose the token or the actual allowlisted domain names.
    return jsonify(
        status="ok",
        allowlist_count=len(ALLOWED_DOMAINS),
        token_configured=bool(TOKEN),
    )


@app.post("/scan")
def scan():
    if not require_token():
        return jsonify(error="Unauthorized"), 401

    data = request.get_json(silent=True) or {}
    host = (data.get("target") or "").strip().lower().rstrip(".")
    if not valid_domain(host):
        return jsonify(error="Invalid domain"), 400
    if not data.get("authorization_confirmed") or not authorized(host):
        return jsonify(
            error="Target is not in the worker allowlist or authorization was not confirmed"
        ), 403

    try:
        ips = resolve_public(host)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    modules = data.get("modules") or []
    if not isinstance(modules, list):
        return jsonify(error="modules must be a list"), 400
    allowed_modules = {"nmap", "whatweb", "testssl"}
    if any(module not in allowed_modules for module in modules):
        return jsonify(error="One or more requested modules are not supported"), 400

    results = {
        "target": host,
        "resolved_public_ips": ips,
        "checks": {},
        "safety": (
            "Low-intensity checks only. No exploit scripts, brute force, "
            "credential attacks, stealth/evasion, or UDP scans are run."
        ),
    }

    if "nmap" in modules:
        if not shutil.which("nmap"):
            results["checks"]["nmap"] = {"error": "nmap is not installed"}
        else:
            results["checks"]["nmap"] = run_command(
                [
                    "nmap", "-Pn", "-sT", "-sV", "--top-ports", "100",
                    "-T2", "--max-retries", "1", "--host-timeout", "90s",
                    *ips,
                ],
                timeout=100,
            )

    if "whatweb" in modules:
        if not shutil.which("whatweb"):
            results["checks"]["whatweb"] = {"error": "whatweb is not installed"}
        else:
            results["checks"]["whatweb"] = run_command(
                ["whatweb", "--no-errors", "--color=never", "-a", "1",
                 "https://" + host],
                timeout=45,
            )

    if "testssl" in modules:
        binary = shutil.which("testssl.sh") or shutil.which("testssl")
        if not binary:
            results["checks"]["testssl"] = {"error": "testssl.sh is not installed"}
        else:
            results["checks"]["testssl"] = run_command(
                [binary, "--fast", "--quiet", "--warnings", "off", host],
                timeout=130,
            )

    return jsonify(results)


@app.post("/phone-intel")
def phone_intel():
    if not require_token():
        return jsonify(error="Unauthorized"), 401

    data = request.get_json(silent=True) or {}
    raw = (data.get("phone") or "").strip()
    region = (data.get("default_region") or "NG").upper()
    if not re.fullmatch(r"[+0-9().\-\s]{7,25}", raw) or not re.fullmatch(r"[A-Z]{2}", region):
        return jsonify(error="Provide a phone number and a two-letter default region"), 400

    try:
        number = phonenumbers.parse(raw, None if raw.startswith("+") else region)
    except phonenumbers.NumberParseException:
        return jsonify(error="The phone number could not be parsed"), 400

    if not phonenumbers.is_possible_number(number):
        return jsonify(error="The phone number is not possible for the supplied region"), 400

    return jsonify({
        "e164": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        "international": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "national": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL),
        "valid": phonenumbers.is_valid_number(number),
        "possible": phonenumbers.is_possible_number(number),
        "region": phonenumbers.region_code_for_number(number),
        "number_type": str(phonenumbers.number_type(number)),
        "carrier_hint": phonenumbers.carrier.name_for_number(number, "en"),
        "timezone_hints": list(phonenumbers.timezone.time_zones_for_number(number)),
        "source": "Google libphonenumber numbering metadata bundled with the worker",
        "limitations": (
            "Passive numbering-plan enrichment only. It cannot identify a "
            "subscriber, verify ownership, locate a handset, or access calls, "
            "SMS, or messaging accounts."
        ),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8787")))
