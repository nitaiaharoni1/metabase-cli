"""Shared Metabase API helpers."""
import json
import urllib.error
import urllib.request


def req(base_url: str, token: str, method: str, path: str, data: dict | None = None) -> dict | list:
    """Make authenticated request to Metabase API."""
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json", "X-Metabase-Session": token}
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def login(base_url: str, email: str, password: str) -> str:
    """Login and return session token."""
    r = urllib.request.urlopen(
        urllib.request.Request(
            f"{base_url.rstrip('/')}/api/session",
            data=json.dumps({"username": email, "password": password}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    )
    return json.loads(r.read().decode())["id"]
