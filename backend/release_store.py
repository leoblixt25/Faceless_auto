"""GitHub Releases storage: upload the rendered MP4 as a release asset and
return a public download URL.

This replaces Firebase Storage (which required a billing-enabled bucket). GitHub
Releases are fully free on public repos and produce a stable public URL that the
frontend and the social publishers can fetch.

The upload is performed from inside the GitHub Actions runner, so we re-use the
same PAT the worker uses to dispatch. The PAT must have `repo` scope and is
provided via the `GITHUB_PAT` repo secret.
"""
import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

# GitHub repo is passed via env as {owner}/{repo} (e.g. "leoblixt25/Faceless_auto")
_DEFAULT_OWNER = "leoblixt25"
_DEFAULT_REPO = "Faceless_auto"

_API = "https://api.github.com"


def _headers():
    pat = os.getenv("GH_PAT")
    if not pat:
        raise RuntimeError(
            "Missing GH_PAT environment variable (needed to create a release)."
        )
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "faceless-video-engine",
    }


def _repo():
    ref = os.getenv("GITHUB_REPOSITORY") or f"{_DEFAULT_OWNER}/{_DEFAULT_REPO}"
    return ref.split("/", 1)


def _json_request(method, url, payload=None):
    req = urllib.request.Request(url, method=method, headers=_headers())
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        return exc.code, json.loads(detail) if detail else {}


def _sanitize_tag(doc_id: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9._-]", "-", doc_id or str(uuid4().hex))
    return f"v-{tag}"


def _upload_asset(upload_url: str, local_path: str, name: str) -> str:
    """POST binary file to the release upload URL and return its URL."""
    path = Path(local_path)
    content_type, _ = mimetypes.guess_type(name)
    content_type = content_type or "video/mp4"
    upload_url = upload_url.replace("{?name,label}", "")
    url = f"{upload_url}?name={urllib.parse.quote(name)}"

    with open(path, "rb") as fh:
        data = fh.read()

    req = urllib.request.Request(url, method="POST", headers=_headers())
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, data=data, timeout=600) as resp:
            asset = json.loads(resp.read().decode("utf-8"))
            return asset.get("browser_download_url") or asset.get("url", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(
            f"Release asset upload failed ({exc.code}): {detail}"
        ) from exc


def _find_or_create_release(token_ref, tag: str, name: str):
    owner, repo = _repo()
    # Try to fetch the release for this tag.
    status, rel = _json_request(
        "GET", f"{_API}/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(tag)}"
    )
    if status == 200:
        return rel
    if status != 404:
        raise RuntimeError(f"Unexpected release lookup status {status}: {rel}")

    # Create the release.
    payload = {
        "tag_name": tag,
        "name": name,
        "body": f"Rendered faceless video ({tag})",
        "draft": False,
        "prerelease": False,
    }
    status, created = _json_request(
        "POST", f"{_API}/repos/{owner}/{repo}/releases", payload
    )
    if status in (200, 201):
        return created

    # If create failed because tag already exists (race), refetch.
    if status == 422:
        _, existing = _json_request(
            "GET", f"{_API}/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(tag)}"
        )
        if existing:
            return existing
    raise RuntimeError(f"Release creation failed ({status}): {created}")


def upload_video(local_path: str, user_id: str, doc_id: str) -> str:
    """Upload a local MP4 as a GitHub release asset and return its public URL.

    Args:
        local_path: Absolute path to the rendered MP4 on the runner.
        user_id:     Owner user id (used in the asset filename only).
        doc_id:      Firestore video document id (used for the release tag).

    Returns:
        The public browser_download_url for the asset.
    """
    name = f"{doc_id or 'video'}_{uuid4().hex[:8]}.mp4"
    tag = _sanitize_tag(doc_id)
    release = _find_or_create_release(None, tag, f"Faceless video {doc_id}")
    upload_url = release.get("upload_url", "")
    if not upload_url:
        raise RuntimeError("Release created without an upload_url.")
    return _upload_asset(upload_url, local_path, name)
