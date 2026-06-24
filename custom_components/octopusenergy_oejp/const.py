import json
import os

DOMAIN = "octopusenergy_oejp"
DEFAULT_NAME = "Octopus Energy OEJP"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BASE_URL = "base_url"
DEFAULT_BASE_URL = "https://api.oejp-kraken.energy"
PLATFORMS = ["sensor"]

# Read version directly from manifest.json to avoid duplication
try:
    _manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(_manifest_path, "r", encoding="utf-8") as _f:
        _manifest = json.load(_f)
        VERSION = _manifest.get("version", "0.1.0")
except Exception:
    VERSION = "0.1.0"
