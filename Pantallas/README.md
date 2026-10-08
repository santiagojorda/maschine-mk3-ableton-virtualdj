# Pantallas

Programa que dibuja en las dos pantallas de la Maschine MK3 (parte de [Maschine MK3 as Ableton Push](../README.md)). Solo toma la interfaz USB de las pantallas; pads, botones y luces siguen pasando por el programa de Native Instruments.

## Ejecutable

`construir_exe.bat` arma `dist\MaschineMK3AsPush\MaschineMK3AsPush.exe` (una carpeta con el programa y todo lo que
necesita; no hace falta tener Python para usarlo, solo para armarlo).

| Comando | Qué hace |
|---|---|
| `MaschineMK3AsPush.exe` | Arranca las pantallas y el puerto de datos de VirtualDJ, sin ventana, y las reinicia si se caen o se cuelgan. Si ya está corriendo, avisa |
| `MaschineMK3AsPush.exe --salir` | Lo detiene todo |
| `MaschineMK3AsPush.exe --instalar-vdj` | Instala en VirtualDJ el dispositivo de datos (reiniciar VirtualDJ después) |

El registro (`pantallas.log`), la configuración (`config.json`) y el estado quedan en
`%LOCALAPPDATA%\MaschineMK3AsPush\`. Para que arranque con Windows, poner un acceso directo al .exe en
`shell:startup`.

## Cómo funciona

- **Modo Ableton:** el script de Ableton manda su estado por UDP (puerto 9017) y acá se dibujan la vista session, el mixer, los dispositivos, el browser y VOLUME / SWING / TEMPO (`ableton_ui.py`, `encoder_view.py`).
- **Modo DJ:** las ondas salen de capturar la ventana de VirtualDJ (`window_capture.py`); el estado de los decks llega por el puerto MIDI virtual "MK3 Screens" (`vdj_puerto.py`, `vdj_data.py`, `dj_info.py`) y el browser se recorta de la ventana (`vdj_browser.py`).
- `supervisor.py` vigila todo; `iniciar_pantallas.bat` lo arranca en una consola (sin armar el .exe).

## Datos útiles

- La Maschine recibe unos 5 MB/s por USB: una pantalla completa tarda ~50 ms, así que se mandan solo las partes que cambian y cada 2 s se redibuja todo.
- Pantallas de 480 × 272, RGB565.
- Si una transferencia USB falla, se reconecta sola; si se apaga la Maschine, espera a que vuelva.

## Más adelante

[`PLAN.md`](PLAN.md): un driver completo en Go que reemplace al programa de NI, y la idea de llevarlo a un Push 3 standalone.
