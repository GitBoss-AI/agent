from pathlib import Path
import json
from datetime import datetime, timedelta

CACHE_DIR = Path("cache")
CACHE_TTL_HOURS = 12  # Cache freshness duration

CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_cache_path(prefix: str, owner: str, repo: str, range: str) -> Path:
    safe_owner = owner.replace("/", "_")
    safe_repo = repo.replace("/", "_")
    return CACHE_DIR / f"{prefix}_{safe_owner}_{safe_repo}_{range}.json"

def load_from_cache(path: Path):
    if path.exists():
        age = datetime.utcnow() - datetime.utcfromtimestamp(path.stat().st_mtime)
        if age < timedelta(hours=CACHE_TTL_HOURS):
            with open(path, "r") as f:
                return json.load(f)
    return None

def save_to_cache(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f)
