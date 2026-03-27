#!/usr/bin/env python3
"""Fetch a secret from Delinea Secret Server using SDK Client Onboarding authentication."""

import os
import sys

import requests
from delinea.secrets.server import PasswordGrantAuthorizer, SecretServer, ServerSecret
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("TSS_BASE_URL", "").rstrip("/")
CLIENT_NAME = os.getenv("TSS_CLIENT_NAME", "")
ONBOARDING_KEY = os.getenv("TSS_ONBOARDING_KEY", "")
SECRET_ID = os.getenv("SECRET_ID", "")


def onboard_client() -> dict:
    """Register the SDK client to get client_id and client_secret. Runs on every execution."""
    if not all([BASE_URL, CLIENT_NAME, ONBOARDING_KEY]):
        sys.exit(
            "Error: TSS_BASE_URL, TSS_CLIENT_NAME, and TSS_ONBOARDING_KEY must be set in .env."
        )

    # Note: As requested, init runs every time a secret is retrieved.
    print(f"Onboarding client '{CLIENT_NAME}' with Secret Server...")
    
    # Secret Server on-prem onboarding endpoint
    url = f"{BASE_URL}/api/v1/sdk-client-accounts"
    payload = {
        "name": CLIENT_NAME,
        "onboardingKey": ONBOARDING_KEY,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit(f"Onboarding failed: {err} - {resp.text}")
    except requests.exceptions.RequestException as e:
        sys.exit(f"Connection error during onboarding: {e}")

    data = resp.json()
    client_id = data.get("clientId")
    client_secret = data.get("clientSecret")

    if not client_id or not client_secret:
        sys.exit(f"Failed to extract credentials from SDK onboarding response: {data}")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
    }


def fetch_secret() -> None:
    """Fetch and print the required secret fields."""
    if not SECRET_ID:
        sys.exit("Error: SECRET_ID must be set in .env.")

    creds = onboard_client()

    print(f"Successfully onboarded! Fetching Secret ID {SECRET_ID}...")
    try:
        # PasswordGrantAuthorizer internally executes the OAuth2 flow with grant_type=password
        # In the context of SDK clients, username is the clientId and password is the clientSecret
        authorizer = PasswordGrantAuthorizer(
            BASE_URL,
            username=creds["client_id"],
            password=creds["client_secret"]
        )

        secret_server = SecretServer(BASE_URL, authorizer=authorizer)
        raw_secret_json = secret_server.get_secret_json(int(SECRET_ID))
        
        # Parse the JSON response into the dataclass the SDK provides
        secret = ServerSecret(**json_to_dict(raw_secret_json))

        uname = secret.fields.get("username")
        pwd = secret.fields.get("password")

        uname_val = uname.value if uname else "<not set>"
        pwd_val = pwd.value if pwd else "<not set>"

        print(f"Retrieved username: {uname_val}")
        print(f"Retrieved password: {pwd_val}")

    except Exception as e:
        sys.exit(f"Failed to fetch secret: {e}")

def json_to_dict(raw_secret_json):
    import json
    if isinstance(raw_secret_json, str):
        return json.loads(raw_secret_json)
    return raw_secret_json

if __name__ == "__main__":
    fetch_secret()
