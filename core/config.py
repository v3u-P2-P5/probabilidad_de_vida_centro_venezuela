"""Carga de configuración (config.yaml). Editable en caliente."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_zone(config: dict, zone_id: str) -> dict:
    for z in config["zonas"]:
        if z["id"] == zone_id:
            return z
    raise KeyError(f"Zona no encontrada: {zone_id}")
