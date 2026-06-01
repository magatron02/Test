#!/usr/bin/env bash
set -e

# Version = 1.0.{commits since Aiterra rename commit 925d2f7}
PATCH=$(git rev-list --count 925d2f7..HEAD)
VERSION="1.0.${PATCH}"
NAME="Aiterra-v${VERSION}"
SRC="crypto-ai-trader"
OUT="${NAME}.zip"

echo "Version : ${VERSION}"
echo "Building: ${OUT}"

rm -rf "/tmp/${NAME}" "${OUT}"
mkdir -p "/tmp/${NAME}"

# Stage files via Python (no rsync needed)
python3 - <<PYEOF
import shutil, os

src  = "crypto-ai-trader"
dst  = "/tmp/${NAME}"
ver  = "${VERSION}"

EXCLUDE_DIRS  = {"venv", "__pycache__", "dist", "build", "backend", "mobile", ".git"}
# Never ship user data: API keys (settings.yml), trade history (trades.db),
# or the live trained model (signal_model.pkl). The model is shipped as a
# seed instead (see below) so updates never clobber a user-trained model.
EXCLUDE_FILES = {".env", "docker-compose.yml", "CHECK.bat", "SETUP.bat",
                 "CREATE_SHORTCUT.bat", "trades.db", "make_release.sh",
                 "settings.yml", "signal_model.pkl"}
EXCLUDE_EXT   = {".pyc", ".pyo", ".pyd", ".bak"}

TEXT_EXTS = {".bat", ".py", ".html", ".md", ".txt", ".yml", ".yaml", ".spec", ".json"}

def patch_version(text):
    return text.replace("v1.0.0", f"v{ver}").replace('"1.0.0"', f'"{ver}"').replace("1.0.0", ver)

def should_skip(name, is_dir):
    if is_dir  and name in EXCLUDE_DIRS:  return True
    if not is_dir and name in EXCLUDE_FILES: return True
    if not is_dir and os.path.splitext(name)[1] in EXCLUDE_EXT: return True
    return False

for root, dirs, files in os.walk(src):
    dirs[:] = [d for d in dirs if not should_skip(d, True)]
    rel      = os.path.relpath(root, src)
    dest_dir = os.path.join(dst, rel)
    os.makedirs(dest_dir, exist_ok=True)
    for f in files:
        if should_skip(f, False):
            continue
        src_path  = os.path.join(root, f)
        dest_path = os.path.join(dest_dir, f)
        ext = os.path.splitext(f)[1].lower()
        if ext in TEXT_EXTS:
            try:
                text = open(src_path, encoding="utf-8").read()
                open(dest_path, "w", encoding="utf-8").write(patch_version(text))
            except Exception:
                shutil.copy2(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)

for d in ["data", "models"]:
    os.makedirs(os.path.join(dst, d), exist_ok=True)
    open(os.path.join(dst, d, ".gitkeep"), "w").close()

# Ship the trained model as a SEED. On first run the app copies it to the
# active signal_model.pkl; thereafter the user's model is never overwritten.
live_model = os.path.join(src, "models", "signal_model.pkl")
if os.path.exists(live_model):
    shutil.copy2(live_model, os.path.join(dst, "models", "signal_model.seed.pkl"))
    print("  Bundled signal_model.seed.pkl")

print(f"  Staged OK  (version {ver})")
PYEOF

# Zip
cd /tmp
zip -rq "${OLDPWD}/${OUT}" "${NAME}/" \
    -x "*/.DS_Store" "*/Thumbs.db" "*/__pycache__/*"

echo "Done: ${OUT}  ($(du -sh "${OLDPWD}/${OUT}" | cut -f1))"
