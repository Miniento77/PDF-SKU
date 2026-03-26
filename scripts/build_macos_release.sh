#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="$ROOT_DIR/.venv/bin/python"
PIP="$ROOT_DIR/.venv/bin/pip"
SPEC_FILE="$ROOT_DIR/packaging/macos/LabelPdfSku.spec"

VERSION="$("$PYTHON" - <<'PY'
from pathlib import Path

for line in Path("pyproject.toml").read_text(encoding="utf-8").splitlines():
    if line.startswith("version = "):
        print(line.split("=", 1)[1].strip().strip('"'))
        break
else:
    raise SystemExit("未能从 pyproject.toml 读取版本号。")
PY
)"

APP_NAME="LabelPdfSku"
ZIP_NAME="${APP_NAME}-${VERSION}-macOS.zip"
PKG_NAME="${APP_NAME}-${VERSION}-macOS.pkg"

"$PIP" install --disable-pip-version-check pyinstaller

rm -rf build dist release
"$PYTHON" -m PyInstaller "$SPEC_FILE" --noconfirm --clean

mkdir -p release build/pkgroot
ditto -c -k --keepParent "dist/${APP_NAME}.app" "release/${ZIP_NAME}"
cp -R "dist/${APP_NAME}.app" "build/pkgroot/${APP_NAME}.app"
pkgbuild \
  --root "build/pkgroot" \
  --identifier "com.miniento.labelpdfsku" \
  --version "$VERSION" \
  --install-location /Applications \
  "release/${PKG_NAME}"

echo "构建完成："
echo "  release/${ZIP_NAME}"
echo "  release/${PKG_NAME}"
