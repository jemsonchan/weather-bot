#!/usr/bin/env python3
"""Run the LinkedIn OAuth flow locally and print the secrets the bot needs.

    python linkedin_auth.py --account bcm

Put the app credentials in a local .env first (see .env.example):

    BCM_LI_CLIENT_ID=...
    BCM_LI_CLIENT_SECRET=...

Add http://localhost:8080/callback to the app's "Authorized redirect URLs"
(LinkedIn developer portal -> your app -> Auth) before running this.
"""
import argparse, http.server, os, secrets, subprocess, sys, time, urllib.parse, webbrowser
import requests
from dotenv import load_dotenv

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "openid profile w_member_social"

_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        # Browsers probe localhost with favicon and prefetch requests; only the
        # redirect actually carrying the grant should end the wait.
        if not ({"code", "error"} & query.keys()):
            self.send_error(404)
            return
        _result.update(query)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Authorized. You can close this tab and return to the terminal.")

    def log_message(self, *args):
        pass


def authorize(client_id, client_secret):
    state = secrets.token_urlsafe(16)
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)

    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": SCOPES,
    })
    url = f"{AUTH_URL}?{params}"
    print(f"Opening browser to authorize:\n{url}\n")
    webbrowser.open(url)

    print("Waiting for the LinkedIn redirect...", flush=True)
    server.timeout = 5
    deadline = time.monotonic() + 900
    while not _result:
        if time.monotonic() > deadline:
            sys.exit("Timed out waiting for the LinkedIn redirect.")
        server.handle_request()
    server.server_close()

    if "error" in _result:
        sys.exit(f"Authorization failed: {_result['error'][0]} — {_result.get('error_description', [''])[0]}")
    if _result.get("state", [""])[0] != state:
        sys.exit("State mismatch — aborting.")

    r = requests.post(TOKEN_URL, timeout=15, data={
        "grant_type": "authorization_code",
        "code": _result["code"][0],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    r.raise_for_status()
    return r.json()


def main():
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--account", choices=["bcm", "roatan"], required=True)
    p.add_argument("--repo", default="jemsonchan/weather-bot")
    args = p.parse_args()
    prefix = "BCM" if args.account == "bcm" else "ROA"

    client_id = os.getenv(f"{prefix}_LI_CLIENT_ID", "")
    client_secret = os.getenv(f"{prefix}_LI_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        sys.exit(f"Set {prefix}_LI_CLIENT_ID and {prefix}_LI_CLIENT_SECRET in .env (see .env.example).")

    tokens = authorize(client_id, client_secret)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    urn = ""
    info = requests.get(USERINFO_URL, timeout=15, headers={"Authorization": f"Bearer {access_token}"})
    if info.ok:
        urn = f"urn:li:person:{info.json()['sub']}"
        print(f"\nAuthorized as: {info.json().get('name', '?')} ({urn})")
        print("The bot will post as this profile — stop now if that is the wrong account.")

    print(f"\nAccess token expires in {tokens.get('expires_in')}s (~60 days).")
    if refresh_token:
        print(f"Refresh token expires in {tokens.get('refresh_token_expires_in')}s (~365 days).")
    else:
        print("\nNo refresh token returned — this app is not enrolled for programmatic refresh.\n"
              "The bot will keep using the static access token and you will need to rerun this\n"
              "script every 60 days. To enable refresh, request it for the app in the LinkedIn\n"
              "developer portal.")

    to_set = {f"{prefix}_LI_ACCESS_TOKEN": access_token}
    if urn:
        to_set[f"{prefix}_LI_AUTHOR_URN"] = urn
    if refresh_token:
        to_set[f"{prefix}_LI_REFRESH_TOKEN"] = refresh_token
        to_set[f"{prefix}_LI_CLIENT_ID"] = client_id
        to_set[f"{prefix}_LI_CLIENT_SECRET"] = client_secret

    # Piped via stdin, never argv or stdout — these values must not end up in
    # shell history, process listings or terminal scrollback.
    print(f"\nWriting {len(to_set)} secrets to {args.repo}:")
    for name, value in to_set.items():
        r = subprocess.run(["gh", "secret", "set", name, "-R", args.repo],
                           input=value, text=True, capture_output=True)
        print(f"  {name}: {'ok' if r.returncode == 0 else 'FAILED — ' + r.stderr.strip()}")


if __name__ == "__main__":
    main()
