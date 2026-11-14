#!/bin/zsh
# OpenEndRPG - macOS build (mirrors build_exe.bat): produces release/OpenEndRPG-mac.zip
# Zip layout: OpenEndRPG.app + README.txt (bilingual usage note)
set -e
cd "$(dirname "$0")"
python3 -m pip install --quiet --upgrade pyinstaller httpx
python3 -m PyInstaller --noconfirm --clean --onefile --windowed --name OpenEndRPG --add-data "web:web" rpg.py
rm -rf release
mkdir -p release/stage
cp -R dist/OpenEndRPG.app release/stage/
cp packaging/使用说明.txt release/stage/README.txt
cd release/stage && zip -qry ../OpenEndRPG-mac.zip . && cd ../.. && rm -rf release/stage
echo "Done: release/OpenEndRPG-mac.zip"
