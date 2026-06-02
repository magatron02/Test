"""
Aiterra data migrator.

Run automatically by UPDATE.bat (and safe to run by hand). Its job is to make
upgrading painless and non-destructive:

  * In-place update (new files extracted over an existing folder):
      keeps your settings.yml exactly, only ADDS any new config keys that this
      version introduced (your values always win). A timestamped .bak is saved.

  * Side-by-side update (new versioned folder next to the old one):
      finds the most recent previous Aiterra install and imports your
      settings.yml (merged with new defaults), trade history (data/) and trained
      AI model (models/*.pkl) into this version.

Nothing the user entered before is ever deleted or overwritten with a blank.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml ships with the app deps
    print("[WARN] pyyaml not available yet — skipping config merge. "
          "Run UPDATE.bat which installs dependencies first.")
    sys.exit(0)

NEW = Path(__file__).resolve().parent


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge `override` onto `base`. Values in `override` (the
    user's saved settings) always win; keys present only in `base` (new
    defaults shipped with this version) are added. Lists are replaced whole."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_yaml(p: Path) -> dict:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[WARN] Could not read {p.name}: {e}")
        return {}


def save_yaml(p: Path, data: dict) -> None:
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=True)


def backup(p: Path) -> None:
    if p.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = p.with_suffix(p.suffix + f".{stamp}.bak")
        try:
            shutil.copy2(p, bak)
            print(f"    - backup saved: {bak.name}")
        except Exception as e:
            print(f"[WARN] Could not back up {p.name}: {e}")


def find_old_install() -> Path | None:
    """Find the newest sibling folder that looks like a previous Aiterra
    install (has config/settings.yml), excluding this folder."""
    parent = NEW.parent
    best = None
    best_mtime = -1.0
    try:
        siblings = list(parent.iterdir())
    except Exception:
        return None
    for d in siblings:
        try:
            if not d.is_dir() or d.resolve() == NEW:
                continue
            cfg = d / "config" / "settings.yml"
            if not cfg.exists():
                continue
            # prefer Aiterra-named folders, then by modification time
            named = d.name.lower().startswith("aiterra")
            mtime = cfg.stat().st_mtime + (10**12 if named else 0)
            if mtime > best_mtime:
                best_mtime, best = mtime, d
        except Exception:
            continue
    return best


def copy_new_only(src_dir: Path, dst_dir: Path, label: str, suffixes=None) -> int:
    """Copy files from src_dir into dst_dir without overwriting anything that
    already exists in dst_dir. Returns the number of files copied."""
    if not src_dir.exists():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src_dir.iterdir():
        if not f.is_file():
            continue
        if suffixes and f.suffix not in suffixes:
            continue
        dst = dst_dir / f.name
        if dst.exists():
            continue
        try:
            shutil.copy2(f, dst)
            n += 1
        except Exception as e:
            print(f"[WARN] Could not copy {f.name}: {e}")
    if n:
        print(f"    - {label}: imported {n} file(s)")
    return n


def main() -> None:
    cfg_dir = NEW / "config"
    cfg_dir.mkdir(exist_ok=True)
    (NEW / "data").mkdir(exist_ok=True)
    (NEW / "models").mkdir(exist_ok=True)

    example = cfg_dir / "settings.example.yml"
    target = cfg_dir / "settings.yml"
    example_cfg = load_yaml(example) if example.exists() else {}

    # ── Case 1: in-place update (settings.yml already here) ──────────────
    if target.exists():
        user_cfg = load_yaml(target)
        merged = deep_merge(example_cfg, user_cfg)
        if merged != user_cfg:
            backup(target)
            save_yaml(target, merged)
            print("[OK] settings.yml kept — new options from this version were added.")
        else:
            print("[OK] settings.yml already up to date — nothing to change.")
        return

    # ── Case 2: fresh folder — import from a previous install ────────────
    old = find_old_install()
    if old is None:
        if example.exists():
            shutil.copy2(example, target)
            print("[OK] No previous install found — created a fresh settings.yml.")
        return

    print(f"[+] Found previous version: {old.name}")
    old_cfg = load_yaml(old / "config" / "settings.yml")
    merged = deep_merge(example_cfg, old_cfg)
    save_yaml(target, merged)
    print("    - settings.yml: imported (your API keys / tokens preserved)")

    copy_new_only(old / "data", NEW / "data", "trade history (data/)")
    copy_new_only(old / "models", NEW / "models", "trained AI model (models/)",
                  suffixes={".pkl"})

    print(f"[OK] Migration complete — your data from {old.name} is now in this version.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[WARN] Migration step hit a problem: {e}")
        print("       Your old folder is untouched. You can manually copy")
        print("       config\\settings.yml, data\\ and models\\ from it if needed.")
