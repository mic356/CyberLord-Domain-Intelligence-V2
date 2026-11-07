"""Restricted Kali scan worker. Run behind a private VPN or strict HTTPS firewall."""
import os, re, hmac, socket, ipaddress, subprocess
import phonenumbers
import phonenumbers.carrier, phonenumbers.timezone
from flask import Flask, request, jsonify
app=Flask(__name__)
TOKEN=os.environ.get('KALI_WORKER_TOKEN','')
ALLOWED=[x.strip().lower().lstrip('.') for x in os.environ.get('KALI_ALLOWED_DOMAINS','').split(',') if x.strip()]

def resolve_public(host):
    try: items=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)
    except socket.gaierror: raise ValueError('Target did not resolve')
    ips=sorted({x[4][0] for x in items})
    if not ips or any(not ipaddress.ip_address(x).is_global for x in ips): raise ValueError('Only public IP targets are permitted')
    return ips

def authorized(host):
    return any(host==d or host.endswith('.'+d) for d in ALLOWED)

def run(args, timeout=90):
    p=subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return {'exit_code':p.returncode,'stdout':p.stdout[-12000:],'stderr':p.stderr[-3000:]}

@app.post('/scan')
def scan():
    if not TOKEN or not hmac.compare_digest(request.headers.get('Authorization',''), 'Bearer '+TOKEN): return jsonify(error='Unauthorized'),401
    data=request.get_json(silent=True) or {}; host=(data.get('target') or '').strip().lower().rstrip('.')
    if not re.fullmatch(r'(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',host): return jsonify(error='Invalid domain'),400
    if not data.get('authorization_confirmed') or not authorized(host): return jsonify(error='Target is not in the worker allowlist or authorization was not confirmed'),403
    try: ips=resolve_public(host)
    except ValueError as e: return jsonify(error=str(e)),400
    modules=data.get('modules') or []; results={'target':host,'resolved_public_ips':ips,'checks':{},'safety':'No exploit scripts, brute force, credential attacks or UDP scans are run.'}
    # Scan resolved addresses, not an unchecked hostname, to reduce DNS rebinding risk.
    if 'nmap' in modules:
        if not shutil_which('nmap'): results['checks']['nmap']={'error':'nmap is not installed'}
        else: results['checks']['nmap']=run(['nmap','-Pn','-sT','-sV','--top-ports','100','-T2','--max-retries','1','--host-timeout','90s',*ips],100)
    if 'whatweb' in modules:
        if not shutil_which('whatweb'): results['checks']['whatweb']={'error':'whatweb is not installed'}
        else: results['checks']['whatweb']=run(['whatweb','--no-errors','--color=never','-a','1','https://'+host],45)
    if 'testssl' in modules:
        binary=shutil_which('testssl.sh') or shutil_which('testssl')
        if not binary: results['checks']['testssl']={'error':'testssl.sh is not installed'}
        else: results['checks']['testssl']=run([binary,'--fast','--quiet','--warnings','off',host],120)
    return jsonify(results)

def shutil_which(name):
    import shutil
    return shutil.which(name)

@app.post('/phone-intel')
def phone_intel():
    if not TOKEN or not hmac.compare_digest(request.headers.get('Authorization',''), 'Bearer '+TOKEN):
        return jsonify(error='Unauthorized'),401
    data=request.get_json(silent=True) or {}
    raw=(data.get('phone') or '').strip()
    region=(data.get('default_region') or 'NG').upper()
    if not re.fullmatch(r'[+0-9().\-\s]{7,25}', raw) or not re.fullmatch(r'[A-Z]{2}', region):
        return jsonify(error='Provide a phone number and a two-letter default region'),400
    try:
        number=phonenumbers.parse(raw, None if raw.startswith('+') else region)
    except phonenumbers.NumberParseException:
        return jsonify(error='The phone number could not be parsed'),400
    if not phonenumbers.is_possible_number(number):
        return jsonify(error='The phone number is not possible for the supplied region'),400
    return jsonify({
        'e164':phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        'international':phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        'national':phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL),
        'valid':phonenumbers.is_valid_number(number),
        'possible':phonenumbers.is_possible_number(number),
        'region':phonenumbers.region_code_for_number(number),
        'number_type':str(phonenumbers.number_type(number)),
        'carrier_hint':phonenumbers.carrier.name_for_number(number, 'en'),
        'timezone_hints':list(phonenumbers.timezone.time_zones_for_number(number)),
        'source':'Google libphonenumber numbering metadata bundled with the worker',
        'limitations':'This is passive numbering-plan enrichment, not a live telecom query. It cannot identify a subscriber, verify ownership, locate a handset or access calls, SMS or messaging accounts.'
    })

@app.get('/health')
def health(): return jsonify(status='ok',allowlist_count=len(ALLOWED))

if __name__=='__main__': app.run(host='127.0.0.1',port=8787)
