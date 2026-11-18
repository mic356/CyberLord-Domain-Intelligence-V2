#!/usr/bin/env python3
"""
CyberLord Domain Intelligence - Internet Explorer
A comprehensive domain intelligence and OSINT tool for ethical hackers and security researchers.
"""

import os, json, sys, re, socket, ssl, base64, io, smtplib, time, secrets, threading, subprocess, ipaddress, xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError

DAILY_FREE_SCAN_LIMIT = int(os.getenv("FREE_DAILY_SCAN_LIMIT", "3"))
PREBUNK_TTLS = {"api": 60, "ip-whois": 60, "phone": 30, "email_exposure": 300, "breach": 6*3600, "dns": 3600, "cve": 6*3600, "tls": 3600, "http": 900, "email": 6*3600, "http_headers": 900, "wayback": 6*3600, "archive": 6*3600, "dnsrecon": 3600, "theharvester": 6*3600, "nmap": 3600, "port": 3600, "hydra": 3600, "metasploit": 3600, "dirb": 3600, "wpscan": 3600, "nikto": 3600, "sqlmap": 3600, "john": 3600, "johncrack": 3600, "social": 3600, "username": 3600, "social_person": 6*3600, "exif": 3600, "image_intelligence": 3600, "metadata": 3600, "screenshot": 3600, "video_intelligence": 3600, "person": 6*3600, "cloned": 6*3600, "relationship": 6*3600, "relationship_map": 6*3600, "keyword_search": 3600, "youtube": 3600, "deep_scan": 3600, "social_image": 3600, "account_timeline": 3600, "attitude": 3600, "ai_persona": 3600, "qualitative": 3600, "warning": 3600, "onion": 3600, "ai": 300, "wulnerability": 3600, "breach_correlation": 3600, "risk_assessment": 3600, "timeline": 3600, "scan_cluster": 3600, "batch_api": 300, "security": 3600, "network": 3600, "ssl_certificate": 3600, "openapi": 3600, "password": 3600, "cdn": 3600, "performance": 3600, "spider": 3600, "vuln_scanner": 3600, "dns_lookup": 3600, "geolocation_info": 3600, "whois": 3600, "security_headers": 3600, "email_security": 3600}
TUTOR_FREE_DAILY_LIMIT = 3
COURSE_ACCESS_PLANS = {"pro", "pro_plus", "tutor_pro"}
CODE_LAB_MAX_QUESTIONS = 3
PLATFORM_DISPLAY_NAMES = {"telegram": "Telegram", "reddit": "Reddit", "youtube": "YouTube", "x": "X", "instagram": "Instagram", "threads": "Threads", "tiktok": "TikTok", "facebook": "Facebook", "shodan": "Shodan", "github": "GitHub", "pastebin": "Pastebin", "haveibeenpwned": "Have I Been Pwned", "emailrep": "EmailRep", "stackoverflow": "Stack Overflow", "whatsapp": "WhatsApp"}

API_CACHE = {}
def _cache_get(key):
    if key not in API_CACHE: return None
    ts, ttl, val = API_CACHE[key]
    if time.time()-ts > ttl:
        del API_CACHE[key]; return None
    return val
def _cache_set(key, ttl, val):
    API_CACHE[key] = (time.time(), ttl, val)

def normalize_domain(v):
    v = re.sub(r"^(?:https?://)?(?:www\\.)?", "", v.strip().lower())
    v = v.split("/")[0]
    if not (re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", v) and "." in v):
        raise ValueError("Enter a valid bare domain, e.g. example.com")
    return v

def _squad_amount_kobo(tier):
    return {
        "free": None, "pro": 630000, "tutor_pro": 630000, "pro_plus": 1260000,
    }.get((tier or "").strip().lower())

def squad_enabled():
    return os.getenv("SQUAD_ENABLED", "").strip().lower() == "true" and bool(os.getenv("SQUAD_SECRET_KEY"))

def squad_base_url():
    return "https://api-d.squadco.com" if os.getenv("SQUAD_ENV", "sandbox").strip().lower() == "live" else "https://sandbox-api-d.squadco.com"

print("SQUAD helpers chunk loaded, remaining app.py continues in next push via CREATE_OR_UPDATE append simulation", flush=True)
