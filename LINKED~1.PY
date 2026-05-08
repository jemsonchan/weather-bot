#!/usr/bin/env python3
"""
linkedin_auth.py — One-time LinkedIn OAuth 2.0 token helper
============================================================
Run this script on your LOCAL computer (not the VPS) to get a LinkedIn
access token. Repeat every 60 days when the token expires.

Usage:
  python linkedin_auth.py --client-id YOUR_ID --client-secret YOUR_SECRET

The script will:
  1. Open LinkedIn in your browser for you to log in and approve
  2. Print your access token
  3. Offer to write it directly to your .env file
"""

import argparse
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
import os
import re

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "openid profile w_member_social"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

received_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global received_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            received_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorised! You can close this tab and return to the terminal.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Error — no code received. Please try again.</h2>")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def main():
    parser = argparse.ArgumentParser(description="Get a LinkedIn access token")
    parser.add_argument("--client-id", required=True, help="LinkedIn app Client ID")
    parser.add_argument("--client-secret", required=True, help="LinkedIn app Client Secret")
    args = parser.parse_args()

    # Build auth URL
    auth_params = {
        "response_type": "code",
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "weatherbot",
    }
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)

    # Start local callback server
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    print("\n=== LinkedIn Token Helper ===")
    print("Opening your browser for LinkedIn login...")
    print("Log in and approve the permissions when prompted.\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)

    if not received_code:
        print("ERROR: No authorisation code received within 2 minutes. Please try again.")
        return

    # Exchange code for token
    token_resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": received_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
    })
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = token_data.get("access_token", "")

    if not access_token:
        print("ERROR: Token exchange failed:", token_data)
        return

    print("\n✅ Access token received!\n")
    print(f"Access Token:\n{access_token}\n")
    print("Expires in:", token_data.get("expires_in", "unknown"), "seconds (~60 days)\n")

    # Offer to update .env
    env_path = ".env"
    if os.path.exists(env_path):
        update = input("Would you like to update .env with this token now? (y/n): ").strip().lower()
        if update == "y":
            account = input("Which account? Enter 'bcm' or 'roatan': ").strip().lower()
            key = "BCM_LI_ACCESS_TOKEN" if account == "bcm" else "ROA_LI_ACCESS_TOKEN"
            with open(env_path, "r") as f:
                content = f.read()
            # Replace existing value or append
            pattern = rf"^{key}=.*$"
            new_line = f"{key}={access_token}"
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
            else:
                content += f"\n{new_line}\n"
            with open(env_path, "w") as f:
                f.write(content)
            print(f"✅ .env updated with {key}")
        else:
            print(f"Copy the token above and paste it into .env as:")
            print(f"BCM_LI_ACCESS_TOKEN={access_token[:20]}...  (for Bitcoin Club Malta)")
            print(f"ROA_LI_ACCESS_TOKEN={access_token[:20]}...  (for Roatan Weather Bot)")
    else:
        print(f"No .env file found. Paste the token manually into your .env file.")

    print("\nDone! Remember to repeat this every 60 days.\n")


if __name__ == "__main__":
    main()
