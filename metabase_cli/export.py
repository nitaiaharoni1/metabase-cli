"""Export Metabase dashboards and cards via API."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from metabase_cli.api import login


def _req(base_url: str, token: str, method: str, path: str, data: dict | None = None) -> dict | list:
    """Make authenticated request to Metabase API."""
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json", "X-Metabase-Session": token}
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def run_export(*, base_url: str, email: str, password: str, output: Path) -> None:
    """Export dashboards and cards to JSON files."""
    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    output.mkdir(parents=True, exist_ok=True)

    # Export dashboards
    dashboards = _req(base_url, token, "GET", "/api/dashboard")
    dash_list = dashboards if isinstance(dashboards, list) else dashboards.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and "name" in d and "id" in d]

    for d in dash_list:
        dash_id = d["id"]
        full = _req(base_url, token, "GET", f"/api/dashboard/{dash_id}")
        name = full.get("name", f"dashboard-{dash_id}").replace("/", "-")
        out_file = output / f"dashboard-{dash_id}-{name}.json"
        with open(out_file, "w") as f:
            json.dump(full, f, indent=2)
        print(f"Exported dashboard: {out_file.name}")

    # Export cards
    cards = _req(base_url, token, "GET", "/api/card")
    card_list = cards if isinstance(cards, list) else cards.get("data", [])
    card_list = [c for c in card_list if isinstance(c, dict) and "id" in c]

    for c in card_list:
        cid = c["id"]
        full = _req(base_url, token, "GET", f"/api/card/{cid}")
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


def run_export_to_code(
    *,
    base_url: str,
    email: str,
    password: str,
    output: Path,
    dashboard_names: list[str] | None = None,
    database_name: str = "OpenSketch Analytics",
) -> None:
    """Export dashboards to YAML config (dashboards as code)."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required for --to-code. Install with: pip install pyyaml", file=sys.stderr)
        raise SystemExit(1)

    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    dash_resp = _req(base_url, token, "GET", "/api/dashboard")
    dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and "name" in d and "id" in d]

    if dashboard_names:
        names_set = set(dashboard_names)
        dash_list = [d for d in dash_list if d["name"] in names_set]

    # Deduplicate dashboards by name (keep first)
    seen_dash: set[str] = set()
    dash_list = [d for d in dash_list if d["name"] not in seen_dash and not seen_dash.add(d["name"])]

    card_by_id: dict[int, dict] = {}
    for d in dash_list:
        full = _req(base_url, token, "GET", f"/api/dashboard/{d['id']}")
        for c in full.get("dashcards", full.get("cards", [])):
            cid = c.get("card_id") or c.get("id")
            if cid and cid not in card_by_id:
                try:
                    card = _req(base_url, token, "GET", f"/api/card/{cid}")
                    if card.get("dataset_query", {}).get("type") == "native":
                        card_by_id[cid] = card
                except Exception:
                    pass

    config_cards = []
    seen_card_names: set[str] = set()
    for card in card_by_id.values():
        if card["name"] in seen_card_names:
            continue
        seen_card_names.add(card["name"])
        sql = card.get("dataset_query", {}).get("native", {}).get("query", "")
        if not sql:
            continue
        config_cards.append({
            "name": card["name"],
            "sql": sql.strip(),
            "display": card.get("display", "table"),
            "visualization_settings": card.get("visualization_settings", {}),
        })

    config_dashboards = []
    for d in dash_list:
        full = _req(base_url, token, "GET", f"/api/dashboard/{d['id']}")
        layout = []
        for c in full.get("dashcards", full.get("cards", [])):
            cid = c.get("card_id") or c.get("id")
            card = card_by_id.get(cid) if cid else None
            if card:
                layout.append({
                    "card": card["name"],
                    "row": c.get("row", 0),
                    "col": c.get("col", 0),
                    "size_x": c.get("size_x", 6),
                    "size_y": c.get("size_y", 4),
                })
        config_dashboards.append({"name": full["name"], "cards": layout})

    if not config_cards and not any(d.get("cards") for d in config_dashboards):
        print(
            "Warning: No cards found in dashboards (API may return empty dashcards). "
            "Not overwriting output. Use metabase-cli configure to apply from YAML.",
            file=sys.stderr,
        )
        return

    config = {"database": database_name, "cards": config_cards, "dashboards": config_dashboards}
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"Exported to {output}")
