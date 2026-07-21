#!/usr/bin/env python3
"""Run the LinkedIn OAuth flow locally and print the secrets the bot needs.

    python linkedin_auth.py --account bcm --client-id XXX --client-secret YYY

Add http://localhost:8080/callback to the app's "Authorized redirect URLs"
(LinkedIn developer portal -> your app -> Auth) before running this.
"""
import argparse, http.server, secrets, sys, urllib.parse, webbrowser
import requests

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "openid profile w_member_social"

_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        _result.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
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

    print("Waiting for the LinkedIn redirect...")
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
    p = argparse.ArgumentParser()
    p.add_argument("--account", choices=["bcm", "roatan"], required=True)
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", required=True)
    args = p.parse_args()
    prefix = "BCM" if args.account == "bcm" else "ROA"

    tokens = authorize(args.client_id, args.client_secret)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    urn = ""
    info = requests.get(USERINFO_URL, timeout=15, headers={"Authorization": f"Bearer {access_token}"})
    if info.ok:
        urn = f"urn:li:person:{info.json()['sub']}"

    print(f"\nAccess token expires in {tokens.get('expires_in')}s (~60 days).")
    if refresh_token:
        print(f"Refresh token expires in {tokens.get('refresh_token_expires_in')}s (~365 days).")
    else:
        print("\nNo refresh token returned — this app is not enrolled for programmatic refresh.\n"
              "The bot will keep using the static access token and you will need to rerun this\n"
              "script every 60 days. To enable refresh, request it for the app in the LinkedIn\n"
              "developer portal.")

    print("\nRun these to update the GitHub secrets:\n")
    print(f'  gh secret set {prefix}_LI_ACCESS_TOKEN -R jemsonchan/weather-bot -b "{access_token}"')
    if urn:
        print(f'  gh secret set {prefix}_LI_AUTHOR_URN -R jemsonchan/weather-bot -b "{urn}"')
    if refresh_token:
        print(f'  gh secret set {prefix}_LI_REFRESH_TOKEN -R jemsonchan/weather-bot -b "{refresh_token}"')
        print(f'  gh secret set {prefix}_LI_CLIENT_ID -R jemsonchan/weather-bot -b "{args.client_id}"')
        print(f'  gh secret set {prefix}_LI_CLIENT_SECRET -R jemsonchan/weather-bot -b "{args.client_secret}"')


if __name__ == "__main__":
    main()
