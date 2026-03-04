"""Load Metabase credentials from env files."""
import os
from pathlib import Path


def load_env(repo_root: Path | None = None) -> None:
    """Load credentials: ~/.metabase.env (global) then .env.metabase, .env (project overrides)."""
    root = repo_root or Path.cwd()
    for env_path in [
        Path.home() / ".metabase.env",
        root / ".env.metabase",
        root / ".env",
    ]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
