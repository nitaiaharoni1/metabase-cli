"""Export Metabase dashboards and cards via API."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def req(base_url: str, token: str, method: str, path: str, data: dict | None = None) -> dict | list:
    """Make authenticated request to Metabase API."""
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json", "X-Metabase-Session": token}
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def run_export(*, base_url: str, email: str, password: str, output: Path) -> None:
    """Export dashboards and cards to JSON files."""
    # Login
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                f"{base_url.rstrip('/')}/api/session",
                data=json.dumps({"username": email, "password": password}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        )
        token = json.loads(r.read().decode())["id"]
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    output.mkdir(parents=True, exist_ok=True)

    # Export dashboards
    dashboards = req(base_url, token, "GET", "/api/dashboard")
    dash_list = dashboards if isinstance(dashboards, list) else dashboards.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and "name" in d and "id" in d]

    for d in dash_list:
        dash_id = d["id"]
        full = req(base_url, token, "GET", f"/api/dashboard/{dash_id}")
        name = full.get("name", f"dashboard-{dash_id}").replace("/", "-")
        out_file = output / f"dashboard-{dash_id}-{name}.json"
        with open(out_file, "w") as f:
            json.dump(full, f, indent=2)
        print(f"Exported dashboard: {out_file.name}")

    # Export cards
    cards = req(base_url, token, "GET", "/api/card")
    card_list = cards if isinstance(cards, list) else cards.get("data", [])
    card_list = [c for c in card_list if isinstance(c, dict) and "id" in c]

    for c in card_list:
        cid = c["id"]
        full = req(base_url, token, "GET", f"/api/card/{cid}")
        name = full.get("name", f"card-{cid}").replace("/", "-")
        out_file = output / f"card-{cid}-{name}.json"
        with open(out_file, "w") as f:
            json.dump(full, f, indent=2)
        print(f"Exported card: {out_file.name}")

    # Manifest
    with open(output / "manifest.json", "w") as f:
        json.dump(
            {
                "dashboards": len(dash_list),
                "cards": len(card_list),
                "dashboard_ids": [d["id"] for d in dash_list],
            },
            f,
            indent=2,
        )
    print(f"\nExported {len(dash_list)} dashboards, {len(card_list)} cards to {output}/")
