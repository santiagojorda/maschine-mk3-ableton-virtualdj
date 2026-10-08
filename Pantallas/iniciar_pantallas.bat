@echo off
title Maschine MK3 Display Driver
cd /d "%~dp0"
rem El supervisor prende el puerto de datos de VirtualDJ y las pantallas, y las reinicia si se caen o se cuelgan.
rem Normalmente ya arranca solo con Windows (acceso directo en la carpeta Inicio); si ya corre, este avisa y sale.
echo Pantallas Maschine MK3 - registro en .venv\pantallas.log. Para salir, cerra esta ventana.
.venv\Scripts\python prototipo\supervisor.py
pause
