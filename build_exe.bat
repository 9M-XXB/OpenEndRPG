@echo off
rem ============================================================
rem  OpenEndRPG - one-click Windows build
rem  Double-click this file on a Windows machine (Python 3.10+
rem  on PATH required). Produces release\OpenEndRPG-windows.zip
rem  containing OpenEndRPG.exe - double-click the exe and the
rem  game lobby opens in your browser.
rem ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] Installing build tool (PyInstaller)...
python -m pip install --quiet --upgrade pyinstaller httpx
if errorlevel 1 goto :failed

echo [2/4] Building OpenEndRPG.exe (onefile, windowed)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name OpenEndRPG --add-data "web;web" rpg.py
if errorlevel 1 goto :failed

echo [3/4] Assembling release folder...
if exist release rmdir /s /q release
mkdir release
mkdir release\OpenEndRPG
copy /y dist\OpenEndRPG.exe release\OpenEndRPG\ >nul
copy /y packaging\使用说明.txt release\OpenEndRPG\README.txt >nul

echo [4/4] Zipping...
powershell -NoProfile -Command "Compress-Archive -Path 'release\OpenEndRPG\*' -DestinationPath 'release\OpenEndRPG-windows.zip' -Force"
if errorlevel 1 goto :failed

echo.
echo Done: release\OpenEndRPG-windows.zip
echo Unzip it anywhere; double-click OpenEndRPG.exe to play.
pause
goto :eof

:failed
echo.
echo Build FAILED - see messages above.
pause
