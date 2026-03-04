"""Archive duplicate collections in Metabase via API."""
import urllib.error

from metabase_cli.api import login, req


def _collect_ids_by_name(items: list, name: str, out: list[int]) -> None:
    """Recursively collect all collection IDs matching name."""
    items = items or []
    if not isinstance(items, list):
        items = [items]
    for item in items:
        if isinstance(item, dict):
            if item.get("name") == name:
                cid = item.get("id")
                if cid is not None:
                    out.append(cid)
            for key in ("children", "children__", "subcollections"):
                _collect_ids_by_name(item.get(key) or [], name, out)


def run_cleanup(
    *,
    base_url: str,
    email: str,
    password: str,
    collection_name: str,
) -> None:
    """Archive duplicate collections, keeping the one with most items."""
    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}")
        raise SystemExit(1)

    ids: list[int] = []
    for endpoint in ["/api/collection/tree", "/api/collection"]:
        try:
            data = req(base_url, token, "GET", endpoint)
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            _collect_ids_by_name(data if isinstance(data, list) else [data], collection_name, ids)
            if ids:
                break
        except Exception:
            continue

    if len(ids) <= 1:
        print(f"Found {len(ids)} '{collection_name}' collection(s). Nothing to clean up.")
        return

    counts: list[tuple[int, int]] = []
    for cid in ids:
        try:
            items = req(base_url, token, "GET", f"/api/collection/{cid}/items")
            n = len(items) if isinstance(items, list) else 0
            counts.append((cid, n))
        except Exception:
            counts.append((cid, 0))

    counts.sort(key=lambda x: -x[1])
    keep_id = counts[0][0]
    archive_ids = [cid for cid, _ in counts[1:]]

    print(f"Keeping collection id={keep_id} ({counts[0][1]} items)")
    for cid in archive_ids:
        try:
            coll = req(base_url, token, "GET", f"/api/collection/{cid}")
            if isinstance(coll, dict):
                coll["archived"] = True
                req(base_url, token, "PUT", f"/api/collection/{cid}", coll)
            else:
                req(base_url, token, "PUT", f"/api/collection/{cid}", {"archived": True})
            print(f"Archived duplicate collection id={cid}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"Failed to archive id={cid}: {e.code} {body}")
        except Exception as e:
            print(f"Failed to archive id={cid}: {e}")

    print("Done.")
