#!/usr/bin/env python3
"""PatewayAI Dashboard API — query balance, usage logs, and API key stats via web API.

Usage:
    python pateway_api.py balance              # show balance + quota summary
    python pateway_api.py keys                 # show all API keys with usage
    python pateway_api.py usage [period]       # usage summary (24h/7d/30d, default 7d)
    python pateway_api.py logs [--page N] [--size M]  # detailed usage logs
    python pateway_api.py modes                # service modes and supported models
    python pateway_api.py key-models           # API keys with supported models via their service mode
    python pateway_api.py all                  # show everything

Flags (before subcommand):
    --relogin    Ignore cached token, force fresh login.
"""

import os
import sys
import json
import time
import base64
import threading
import urllib.request
import urllib.error

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API_BASE = os.environ.get("PATEWAY_API_BASE", "https://web.pateway.ai/api/v1")
TOKEN_FILE = os.path.expanduser(os.environ.get("PATEWAY_TOKEN_FILE", "~/.hermes/cache/pateway_token.json"))

# ── credentials ──────────────────────────────────────────────
# Set these in your shell or secret manager. Do not hard-code credentials.
EMAIL = os.environ.get("PATEWAY_EMAIL", "")
PASSWORD = os.environ.get("PATEWAY_PASSWORD", "")

# ── RSA public key (SPKI DER, base64) ─────────────────────────
PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAncHQP+2eA2eAGoGpCtMwWOAQ1zCgYVqPT1U/"
    "00q3BXX2XBhqwhLu+LMXTmz3qA0G57ThLIzjY+4ZIA9gLEPy/nwrnyzSachXeIriWGQkEWV21gWA7x6I"
    "LnwvrswDSolROC3ONpmjt+aMFA0hJ58ItXWL6O6b4RC5WWLoqKHAmsLER3aKGaY7CFK0yQD4DuUNoWHB"
    "Q1wXOrLB6PwRuUHK3yjUMoH2/MKk0wmtPBzzJDRGs7UoRFW2sjohyISvp9mbtJKN2CgwZSwxMCTOuLW+"
    "nVzizAaHnzxK2Ci96m27YMREXl/aIb3olRLli4u7pvA9S2j/ZWxcb1vg9wWAb34trQIDAQAB"
)

# ── Rate limiter ──────────────────────────────────────────────
_MIN_INTERVAL = 1.5          # seconds between API calls
_MAX_RETRIES = 3             # max retries on rate-limit
_RATE_LOCK = threading.Lock()
_LAST_REQUEST = 0.0


def _rate_limit():
    """Block until the minimum interval has passed since the last request."""
    global _LAST_REQUEST
    with _RATE_LOCK:
        elapsed = time.time() - _LAST_REQUEST
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _LAST_REQUEST = time.time()


_PUBLIC_KEY = None
_TOKEN_CACHE_VALID = False  # True after first successful token load or login


def _get_public_key():
    """Lazily load the RSA public key."""
    global _PUBLIC_KEY
    if _PUBLIC_KEY is None:
        der_bytes = base64.b64decode(PUBLIC_KEY_B64)
        _PUBLIC_KEY = serialization.load_der_public_key(der_bytes)
    return _PUBLIC_KEY


def _encrypt_password(password: str) -> str:
    """Encrypt password using RSA-OAEP (SHA-256), return base64 ciphertext."""
    pubkey = _get_public_key()
    ciphertext = pubkey.encrypt(
        password.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode()


def _req(method, path, body=None, _retry_auth=True):
    """Make an authenticated API request with rate limiting."""
    token = _get_token()

    _rate_limit()

    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-token", token)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Accept", "application/json")

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())

        except urllib.error.HTTPError as e:
            err_body = e.read().decode()

            # Token expired — re-login once, then retry
            if e.code == 401 and _retry_auth:
                sys.stderr.write("[pateway] token expired, re-logging in...\n")
                _login(force=True)
                return _req(method, path, body, _retry_auth=False)

            # Rate limited — exponential backoff
            if e.code == 429:
                if attempt < _MAX_RETRIES:
                    wait = 2 ** attempt
                    sys.stderr.write(f"[pateway] rate-limited (429), retrying in {wait}s "
                                     f"(attempt {attempt}/{_MAX_RETRIES})...\n")
                    time.sleep(wait)
                    continue
                return {"code": -1, "message": f"Rate limited after {_MAX_RETRIES} retries"}

            return {"code": -1, "message": f"HTTP {e.code}: {err_body}"}

        except urllib.error.URLError as e:
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                sys.stderr.write(f"[pateway] network error, retrying in {wait}s...\n")
                time.sleep(wait)
                continue
            return {"code": -1, "message": f"Network error: {e.reason}"}

    return {"code": -1, "message": "Max retries exceeded"}


def _get_token():
    """Get cached token or login. Respects --relogin flag."""
    global _TOKEN_CACHE_VALID

    if "--relogin" in sys.argv:
        return _login(force=True)

    try:
        with open(TOKEN_FILE) as f:
            cached = json.load(f)
        if cached.get("expires_at", 0) > time.time() + 60:
            if not _TOKEN_CACHE_VALID:
                remaining = int(cached["expires_at"] - time.time())
                sys.stderr.write(f"[pateway] using cached token "
                                 f"(expires in ~{remaining // 3600}h {(remaining % 3600) // 60}m)\n")
                _TOKEN_CACHE_VALID = True
            return cached["token"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    return _login()


def _login(force=False):
    """Login and cache token."""
    global _TOKEN_CACHE_VALID
    if not EMAIL or not PASSWORD:
        raise RuntimeError("Missing credentials: set PATEWAY_EMAIL and PATEWAY_PASSWORD")

    if not force:
        # Already logged in this session, use cached
        try:
            with open(TOKEN_FILE) as f:
                cached = json.load(f)
            if cached.get("expires_at", 0) > time.time() + 60:
                return cached["token"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    sys.stderr.write("[pateway] logging in...\n")
    _rate_limit()

    url = f"{API_BASE}/auth/login"
    body = {"email": EMAIL, "password": _encrypt_password(PASSWORD)}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())

    if result.get("code") != 0:
        raise RuntimeError(f"Login failed: {result.get('message')}")

    token = result["data"]["token"]
    # Token expires ~7 days, cache for 6 days to be safe
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "expires_at": time.time() + 6 * 86400}, f)
    os.chmod(TOKEN_FILE, 0o600)

    sys.stderr.write("[pateway] login OK, token cached for 6 days\n")
    _TOKEN_CACHE_VALID = True
    return token


# ── commands ──────────────────────────────────────────────────


def cmd_balance():
    data = _req("GET", "/balance/summary")
    if data["code"] != 0:
        return print(f"Error: {data['message']}")
    d = data["data"]
    print(f"Available Quota:    ${d['availableBalance']}")
    print(f"Monthly Spending:   ${d['monthlySpending']}")
    print(f"Total Rewards:      ${d['totalGiftEarned']}")


def cmd_keys():
    data = _req("GET", "/user/api-keys")
    if data["code"] != 0:
        return print(f"Error: {data['message']}")
    keys = data["data"]
    print(f"{'Key Name':<20} {'Status':<10} {'Mode':<12} {'Limit':<12} {'Used/Month':>12}")
    print("-" * 74)
    for k in keys:
        limit = k.get("monthlyLimit", 0) or 0
        limit_str = "No limit" if limit == 0 else f"${limit}"
        used = k.get("monthUsage", 0) or 0
        mode = k.get("serviceModeTagZh") or k.get("serviceModeTagEn") or "-"
        print(f"{k['apiKeyName']:<20} {k['status']:<10} {mode:<12} {limit_str:<12} ${used:>11.2f}")


def cmd_usage(period="7d"):
    if period not in {"24h", "7d", "30d"}:
        return print(f"Invalid period: {period}. Use: 24h, 7d, 30d")
    data = _req("GET", f"/usage/summary?period={period}")
    if data["code"] != 0:
        return print(f"Error: {data['message']}")
    d = data["data"]
    c = d["cards"]
    print(f"Period: {period}")
    print(f"Total Cost:      ${c['totalCost']}")
    print(f"Requests:        {c['requestCount']}")
    print(f"Input Tokens:    {c['inputTokens']:,}")
    print(f"Output Tokens:   {c['outputTokens']:,}")
    print()
    print("Usage Trend:")
    for t in d.get("trend", []):
        print(f"  {t['time']}  cost=${t['cost']:.2f}  tokens={t['totalTokens']:,}")


def cmd_logs(page=1, size=20):
    data = _req("GET", f"/usage/details?page={page}&pageSize={size}")
    if data["code"] != 0:
        return print(f"Error: {data['message']}")
    items = data["data"]["list"]
    print(f"{'Time':<22} {'Key':<14} {'Mode':<12} {'Model':<22} {'Tokens':>10} {'Cost':>8}")
    print("-" * 95)
    for item in items:
        t = item["eventTime"]
        key = item["keyName"]
        mode = item.get("serviceModeTagZh") or item.get("serviceModeTagEn") or "-"
        model = item["model"]
        tokens = f"{item['totalTokens']:,}"
        cost = f"${item.get('totalCost', 0)}"
        print(f"{t:<22} {key:<14} {mode:<12} {model:<22} {tokens:>10} {cost:>8}")


def cmd_modes():
    data = _req("GET", "/service-modes/options")
    if data["code"] != 0:
        return print(f"Error: {data['message']}")
    modes = data["data"]["list"]
    for mode in modes:
        mode_id = mode["serviceModeId"]
        tag = mode.get("tagZh") or mode.get("tagEn") or "-"
        default = " (default)" if mode.get("isDefault") else ""
        desc = mode.get("descriptionZh") or mode.get("descriptionEn") or ""
        print(f"Mode {mode_id}: {tag}{default}")
        if desc:
            print(f"  {desc.strip()}")
        for model in mode.get("modelNames", []):
            print(f"  - {model}")
        print()


def cmd_key_models():
    keys_data = _req("GET", "/user/api-keys")
    if keys_data["code"] != 0:
        return print(f"Error: {keys_data['message']}")
    modes_data = _req("GET", "/service-modes/options")
    if modes_data["code"] != 0:
        return print(f"Error: {modes_data['message']}")

    models_by_mode = {
        m["serviceModeId"]: m.get("modelNames", [])
        for m in modes_data["data"]["list"]
    }
    for k in keys_data["data"]:
        mode = k.get("serviceModeTagZh") or k.get("serviceModeTagEn") or "-"
        masked_key = k.get("apiKey", "")
        suffix = masked_key[-4:] if masked_key else "-"
        models = models_by_mode.get(k.get("serviceModeId"), [])
        print(f"{k['apiKeyName']} ({k['status']}, *{suffix}) — {mode}, monthUsage=${k.get('monthUsage', 0) or 0:.2f}")
        for model in models:
            print(f"  - {model}")
        print()


def cmd_all():
    print("═══ BALANCE ═══")
    cmd_balance()
    print("\n═══ API KEYS ═══")
    cmd_keys()
    print("\n═══ SERVICE MODES ═══")
    cmd_modes()
    print("\n═══ API KEY SUPPORTED MODELS ═══")
    cmd_key_models()
    print("\n═══ USAGE (7d) ═══")
    cmd_usage("7d")
    print("\n═══ RECENT LOGS ═══")
    cmd_logs(1, 10)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "--relogin":
        if len(sys.argv) < 3:
            print("Usage: pateway_api.py --relogin <subcommand>")
            sys.exit(1)
        cmd = sys.argv[2]

    if cmd == "balance":
        cmd_balance()
    elif cmd == "keys":
        cmd_keys()
    elif cmd == "usage":
        period = sys.argv[-1] if sys.argv[-1] in {"24h", "7d", "30d"} else "7d"
        cmd_usage(period)
    elif cmd == "logs":
        p = next((int(sys.argv[i+1]) for i, a in enumerate(sys.argv) if a == "--page"), 1)
        s = next((int(sys.argv[i+1]) for i, a in enumerate(sys.argv) if a == "--size"), 20)
        cmd_logs(p, s)
    elif cmd == "modes":
        cmd_modes()
    elif cmd == "key-models":
        cmd_key_models()
    elif cmd == "all":
        cmd_all()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
