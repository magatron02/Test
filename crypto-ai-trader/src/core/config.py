import os
import shutil
import sys as _sys
import yaml
from pathlib import Path
from typing import Any, Dict


def _resolve_base() -> Path:
    if getattr(_sys, 'frozen', False):
        return Path(_sys.executable).parent
    env = os.environ.get('TRADER_BASE_DIR')
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent


BASE_DIR     = _resolve_base()
CONFIG_PATH  = BASE_DIR / "config" / "settings.yml"
EXAMPLE_PATH = (Path(_sys._MEIPASS) if getattr(_sys, 'frozen', False) else BASE_DIR) / "config" / "settings.example.yml"
DATA_DIR     = BASE_DIR / "data"
MODELS_DIR   = BASE_DIR / "models"


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


class Settings:
    def __init__(self):
        self._cfg = load_config()
        DATA_DIR.mkdir(exist_ok=True)
        MODELS_DIR.mkdir(exist_ok=True)

    def reload(self):
        self._cfg = load_config()

    def save(self):
        save_config(self._cfg)

    def get(self, *keys, default=None):
        val = self._cfg
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, default)
        return val

    def set(self, value, *keys):
        d = self._cfg
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    @property
    def app_port(self) -> int:
        return self.get("app", "port", default=8888)

    @property
    def app_name(self) -> str:
        return self.get("app", "name", default="AI Auto Trader")

    @property
    def trading_mode(self) -> str:
        return self.get("trading", "mode", default="demo")

    @property
    def ai_model(self) -> str:
        return self.get("ai", "default_model", default="hybrid")

    @property
    def symbols(self):
        return self.get("trading", "symbols", default=["BTC/USDT", "ETH/USDT"])

    @property
    def analysis_interval(self) -> int:
        return self.get("trading", "analysis_interval", default=300)

    @property
    def claude_api_key(self) -> str:
        return self.get("ai", "claude", "api_key", default="")

    @property
    def claude_model(self) -> str:
        return self.get("ai", "claude", "model", default="claude-sonnet-4-6")

    @property
    def base_dir(self) -> Path:
        return BASE_DIR

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    @property
    def models_dir(self) -> Path:
        return MODELS_DIR


settings = Settings()
