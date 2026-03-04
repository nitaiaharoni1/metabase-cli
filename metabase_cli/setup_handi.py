"""One-time Handi Metabase setup: archive sample data, dedupe cards."""
import sys
import urllib.error

from metabase_cli.api import login
from metabase_cli.archive import run_archive_dashboard, run_archive_cards_by_database
from metabase_cli.duplicate_cards import run_cleanup_duplicate_cards


def run_setup_handi(
    *,
    base_url: str,
    email: str,
    password: str,
) -> None:
    """One-time Handi setup: archive sample dashboards/cards, dedupe."""
    try:
        login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    print("1. Archiving E-commerce Insights dashboard...")
    try:
        run_archive_dashboard(
            base_url=base_url,
            email=email,
            password=password,
            dashboard_name="E-commerce Insights",
        )
    except (SystemExit, Exception):
        print("   (skipped)")

    print("2. Archiving sample database cards...")
    try:
        run_archive_cards_by_database(
            base_url=base_url,
            email=email,
            password=password,
            database_id=1,
        )
    except (SystemExit, Exception):
        print("   (skipped)")

    print("3. Cleaning up duplicate cards...")
    run_cleanup_duplicate_cards(
        base_url=base_url,
        email=email,
        password=password,
        collection=None,
        dry_run=False,
    )

    print("\nHandi Metabase setup complete. Run 'npm run metabase:apply' to apply dashboards from handi.yaml.")
