#!/usr/bin/env python3
"""Warn before the LinkedIn tokens expire.

LinkedIn access tokens last 60 days and there is no notification when one dies —
the first symptom is a failed post. This introspects each configured token and
fails the run while there is still time to re-authorize with linkedin_auth.py.
"""
import os, sys, time
import requests
from dotenv import load_dotenv

load_dotenv()

INTROSPECT_URL = "https://www.linkedin.com/oauth/v2/introspectToken"
WARN_DAYS = int(os.getenv("WARN_DAYS", "10"))
IN_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))


def introspect(client_id, client_secret, token):
    r = requests.post(INTROSPECT_URL, timeout=15, data={
        "client_id": client_id, "client_secret": client_secret, "token": token,
    })
    r.raise_for_status()
    return r.json()


def check(prefix):
    client_id = os.getenv(f"{prefix}_LI_CLIENT_ID", "")
    client_secret = os.getenv(f"{prefix}_LI_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        print(f"{prefix}: no client credentials configured — cannot check.")
        return True

    # A live refresh token is what keeps the bot going; only when there is none
    # does the 60-day access token become the thing that needs watching.
    refresh_token = os.getenv(f"{prefix}_LI_REFRESH_TOKEN", "")
    kind = "refresh token" if refresh_token else "access token"
    token = refresh_token or os.getenv(f"{prefix}_LI_ACCESS_TOKEN", "")
    if not token:
        print(f"{prefix}: no token configured — cannot check.")
        return True

    try:
        info = introspect(client_id, client_secret, token)
    except requests.RequestException as e:
        print(f"{prefix}: introspection failed: {e}")
        return False

    if info.get("status") != "active":
        fail(prefix, f"{kind} is {info.get('status', 'not active')} — re-run "
                     f"linkedin_auth.py --account {prefix.lower()}")
        return False

    days = (info["expires_at"] - time.time()) / 86400
    print(f"{prefix}: {kind} active, {days:.0f} days left.")
    if days <= WARN_DAYS:
        fail(prefix, f"{kind} expires in {days:.0f} days — re-run "
                     f"linkedin_auth.py --account {prefix.lower()}")
        return False
    return True


def fail(prefix, message):
    print(f"{prefix}: {message}")
    if IN_ACTIONS:
        print(f"::error title=LinkedIn token ({prefix})::{message}")


if __name__ == "__main__":
    results = [check("BCM"), check("ROA")]
    sys.exit(0 if all(results) else 1)
