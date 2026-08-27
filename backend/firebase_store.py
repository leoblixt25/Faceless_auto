"""Firebase integration: upload the rendered MP4 to Storage and update the
video document's status in Firestore.

Runs inside the GitHub Actions runner where the full Firebase Admin SDK is
available (unlike the Cloudflare Worker).
"""
import json
import os
from pathlib import Path
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, firestore, storage

from config import CONFIG

_app = None


def _credentials_object():
    """Return the firebase-admin credentials from the env secret.

    Supports FIREBASE_CREDENTIALS being either a path to a JSON file or the
    raw service-account JSON content.
    """
    raw = CONFIG.firebase_credentials_path
    candidate = Path(raw)
    if candidate.exists():
        return credentials.Certificate(str(candidate))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS must be a path to a service-account JSON "
            "file OR its raw JSON content."
        )
    return credentials.Certificate(payload)


def _get_app():
    global _app
    config = {}
    if CONFIG.firebase_storage_bucket:
        config["storageBucket"] = CONFIG.firebase_storage_bucket
    if _app is None:
        _app = firebase_admin.initialize_app(_credentials_object(), config)
    return _app


def _db():
    return firestore.client(_get_app())


def _bucket():
    _get_app()
    return storage.bucket()


def get_document(doc_id: str):
    """Return the Firestore video document data, or None if not found."""
    doc_ref = _db().collection("videos").document(doc_id)
    snap = doc_ref.get()
    return snap.to_dict() if snap.exists else None


def update_status(doc_id: str, status: str, **extra):
    """Update the video document's status and merge any extra fields."""
    updates = {"status": status, "updatedAt": firestore.SERVER_TIMESTAMP}
    updates.update(extra)
    _db().collection("videos").document(doc_id).update(updates)
    return doc_id


def upload_video(local_path: str, user_id: str, doc_id: str) -> str:
    """Upload a local MP4 to Firebase Storage and return its public URL."""
    bucket = _bucket()
    ext = Path(local_path).suffix or ".mp4"
    destination = f"videos/{user_id}/{doc_id}_{uuid4().hex}{ext}"
    blob = bucket.blob(destination)

    blob.upload_from_filename(local_path, content_type="video/mp4")
    blob.make_public()

    return blob.public_url
