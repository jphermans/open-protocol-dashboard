@echo off
REM Build a standalone Windows executable of the Tool CRUD Dashboard.
REM Run from inside the project folder on a Windows machine.
setlocal

if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat

pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm ^
  --onefile ^
  --windowed ^
  --name OpenProtocolDashboard ^
  --add-data "app;app" ^
  --collect-all streamlit ^
  --collect-all sqlalchemy ^
  --collect-all pandas ^
  --hidden-import streamlit ^
  --hidden-import sqlalchemy.dialects.postgresql ^
  --hidden-import sqlalchemy.dialects.mysql ^
  --hidden-import sqlalchemy.dialects.sqlite ^
  run.py

echo.
echo Built: dist\OpenProtocolDashboard.exe
endlocal
