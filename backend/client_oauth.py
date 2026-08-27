#!/usr/bin/env python3
"""One-time helper to obtain a YouTube upload OAuth token.

Run once locally to authorize your Google account and produce the token file
referenced by GOOGLE_TOKEN. The token is then set as a GitHub Actions secret.
"""
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import CONFIG

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _dump(creds, token_path):
    os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or SCOPES),
            },
            f,
            indent=2,
        )
    print(f"Token saved to {token_path}")


def main():
    client_secrets = CONFIG.google_client_secrets_path
    if not client_secrets:
        raise SystemExit("Set GOOGLE_CLIENT_SECRETS to your client_secret JSON path.")

    token_path = CONFIG.google_token_path

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if creds and creds.valid and creds.token:
        print("Token already valid. Re-saving.")
        _dump(creds, token_path)
        return

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    _dump(creds, token_path)


if __name__ == "__main__":
    main()
