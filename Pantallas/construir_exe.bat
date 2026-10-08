@echo off
rem Arma el ejecutable en dist\MaschineMK3AsPush\ (hace falta el entorno: python -m venv .venv y pip install -r requirements.txt)
cd /d "%~dp0"
.venv\Scripts\pip install -q pyinstaller
.venv\Scripts\python prototipo\hacer_icono.py
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --noconsole --name MaschineMK3AsPush ^
  --icon prototipo\icono.ico --paths prototipo ^
  --add-data "prototipo\config.example.json;." ^
  --add-data "prototipo\vdj\MK3-Screens.xml;vdj" ^
  --add-data "prototipo\vdj\MK3SCREENS - Datos pantallas.xml;vdj" ^
  --collect-all libusb_package --hidden-import mido.backends.rtmidi --hidden-import rtmidi ^
  prototipo\maschine_mk3.py
echo.
echo Listo: dist\MaschineMK3AsPush\MaschineMK3AsPush.exe
pause
