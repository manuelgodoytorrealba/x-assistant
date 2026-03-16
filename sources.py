import yaml
from pathlib import Path

SOURCES_FILE = Path("data/sources.yaml")


def load_sources():
    if not SOURCES_FILE.exists():
        raise FileNotFoundError("sources.yaml not found")

    with open(SOURCES_FILE, "r") as f:
        data = yaml.safe_load(f)

    return data.get("sources", [])
