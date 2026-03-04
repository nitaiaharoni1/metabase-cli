"""Archive dashboards and cards via Metabase API."""
import urllib.error

from metabase_cli.api import login, req


def run_archive_dashboard(
    *,
    base_url: str,
    email: str,
    password: str,
    dashboard_id: int | None = None,
    dashboard_name: str | None = None,
    name: str | None = None,
) -> None:
    """Archive a dashboard by ID or name."""
    name_val = dashboard_name or name
    if dashboard_id is None and not name_val:
        print("Error: provide --id or --name", file=__import__("sys").stderr)
        raise SystemExit(1)

    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=__import__("sys").stderr)
        raise SystemExit(1)

    dash_id = dashboard_id
    if dash_id is None:
        dash_resp = req(base_url, token, "GET", "/api/dashboard")
        dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
        for d in dash_list or []:
            if isinstance(d, dict) and d.get("name") == name_val:
                dash_id = d.get("id")
                break
        if dash_id is None:
            print(f"Error: dashboard '{name_val}' not found", file=__import__("sys").stderr)
            raise SystemExit(1)

    try:
        full = req(base_url, token, "GET", f"/api/dashboard/{dash_id}")
        if isinstance(full, dict) and full.get("archived"):
            print(f"Dashboard id={dash_id} already archived")
            return
        full["archived"] = True
        req(base_url, token, "PUT", f"/api/dashboard/{dash_id}", full)
        name = full.get("name", dash_id)
        print(f"Archived dashboard: {name} (id={dash_id})")
    except urllib.error.HTTPError as e:
        print(f"Failed to archive dashboard: {e.code} {e.read().decode()}", file=__import__("sys").stderr)
        raise SystemExit(1)


def run_archive_cards_by_database(
    *,
    base_url: str,
    email: str,
    password: str,
    database_id: int,
) -> None:
    """Archive all cards that use the given database."""
    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=__import__("sys").stderr)
        raise SystemExit(1)

    cards_resp = req(base_url, token, "GET", "/api/card")
    card_list = cards_resp if isinstance(cards_resp, list) else cards_resp.get("data", [])
    to_archive = [
        c for c in (card_list or [])
        if isinstance(c, dict) and c.get("database_id") == database_id and not c.get("archived")
    ]

    if not to_archive:
        print(f"No cards found for database_id={database_id}")
        return

    archived = 0
    for c in to_archive:
        cid = c.get("id")
        name = c.get("name", cid)
        try:
            full = req(base_url, token, "GET", f"/api/card/{cid}")
            if isinstance(full, dict):
                full["archived"] = True
                req(base_url, token, "PUT", f"/api/card/{cid}", full)
                print(f"Archived card: {name} (id={cid})")
                archived += 1
        except urllib.error.HTTPError as e:
            print(f"Failed to archive card {cid}: {e.code} {e.read().decode()}", file=__import__("sys").stderr)

    print(f"Archived {archived} card(s) from database_id={database_id}")
