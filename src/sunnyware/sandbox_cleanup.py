import json
import time
import logging
from pathlib import Path
from . import paths

logger = logging.getLogger(__name__)

def get_config() -> dict:
    CONFIG_FILE = paths.data_root() / "cleanup_config.json"
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enabled": False, "ttl_days": 7}

def save_config(cfg: dict):
    CONFIG_FILE = paths.data_root() / "cleanup_config.json"
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def run_cleanup(force: bool = False) -> dict:
    cfg = get_config()
    if not cfg.get("enabled") and not force:
        return {"status": "disabled", "deleted": 0}
    
    ttl_days = cfg.get("ttl_days", 7)
    cutoff = time.time() - (ttl_days * 86400)
    sb = paths.sandbox()
    deleted = 0
    
    if sb.exists():
        for f in sb.iterdir():
            if f.is_file():
                if f.stat().st_mtime < cutoff:
                    try:
                        f.unlink()
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {f}: {e}")
                        
    return {"status": "success", "deleted": deleted, "ttl_days": ttl_days}
