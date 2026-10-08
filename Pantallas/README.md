# Pantallas

Programa que dibuja en las dos pantallas de la Maschine MK3, sin reemplazar al programa de Native Instruments:
este solo toma la interfaz USB de las pantallas (la 5); pads, botones y luces siguen pasando por el de NI.

- **Modo Ableton:** el script de Ableton manda su estado por UDP (puerto 9017) y acá se dibujan la vista session,
  el mixer, los dispositivos, el browser y VOLUME / SWING / TEMPO (`ableton_ui.py`, `encoder_view.py`).
- **Modo DJ:** las ondas salen de capturar la ventana de VirtualDJ (`window_capture.py`); el estado de los decks
  llega por el puerto MIDI virtual "MK3 Screens" (`vdj_puerto.py`, `vdj_data.py`, `dj_info.py`) y el browser se
  recorta de la ventana (`vdj_browser.py`).

## Programas

| Archivo | Qué hace |
|---|---|
| `prototipo/supervisor.py` | Arranca y vigila todo: si las pantallas se cierran o se cuelgan, las reinicia |
| `prototipo/dj_screens.py` | Las pantallas |
| `prototipo/vdj_puerto.py` | Mantiene el puerto "MK3 Screens" para los datos de VirtualDJ |
| `prototipo/vdj/generar.py` | Genera e instala el dispositivo de datos en VirtualDJ (`--instalar`) |
| `iniciar_pantallas.bat` | Arranca el supervisor en una consola |

El registro queda en `.venv/pantallas.log`.

## Datos útiles

- La Maschine recibe unos 5 MB/s por USB: una pantalla completa tarda ~50 ms, así que se mandan solo las partes
  que cambian y cada 2 s se redibuja todo.
- Pantallas de 480 × 272, RGB565.
- Si una transferencia USB falla, se reconecta sola; si se apaga la Maschine, espera a que vuelva.

## Más adelante

[`PLAN.md`](PLAN.md): un driver completo en Go que reemplace al programa de NI, y la idea de llevarlo a un
Push 3 standalone.
