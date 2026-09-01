"""Central configuration for the video engine.

Reads credentials from environment variables (as set by the GitHub Actions
workflow from repo secrets) or a local `.env` file when running on a
development machine.
"""
import os
import json
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            "Set it as a GitHub Actions secret or in a local .env file."
        )
    return value


def _optional(name, default=""):
    return os.getenv(name, default)


class Config:
    @property
    def groq_api_key(self):
        return _required("GROQ_API_KEY")

    @property
    def pexels_api_key(self):
        return _required("PEXELS_API_KEY")

    @property
    def seedance_api_key(self):
        # Optional — when set, videos are generated with AI (Seedance 2.0);
        # otherwise the pipeline falls back to Pexels stock footage.
        return _optional("SEEDANCE_API_KEY")

    @property
    def firebase_credentials_path(self):
        # Path to the service-account JSON file, or the JSON content itself.
        return _required("FIREBASE_CREDENTIALS")

    @property
    def firebase_storage_bucket(self):
        return _optional("FIREBASE_STORAGE_BUCKET")

    @property
    def google_client_secrets_path(self):
        return _optional("GOOGLE_CLIENT_SECRETS")

    @property
    def google_token_path(self):
        return _optional("GOOGLE_TOKEN", str(Path.home() / "google_token.json"))

    @property
    def instagram_access_token(self):
        return _optional("INSTAGRAM_ACCESS_TOKEN")

    @property
    def instagram_business_account_id(self):
        return _optional("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    @property
    def tiktok_access_token(self):
        return _optional("TIKTOK_ACCESS_TOKEN")

    @property
    def output_dir(self):
        return _optional("OUTPUT_DIR", "assets")


CONFIG = Config()
