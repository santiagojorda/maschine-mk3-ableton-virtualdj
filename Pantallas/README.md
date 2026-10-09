# Pantallas (Maschine MK3 as Ableton Push)

Servidor y renderizador de pantallas en tiempo real para la Maschine MK3. Se encarga de dibujar la interfaz gráfica de Ableton Live 12 en las dos pantallas LCD a color (480 × 272 c/u).

Solo toma la interfaz USB de las pantallas (WinUSB en la interfaz 5); pads, botones y perillas siguen comunicándose por MIDI a través del Remote Script de Ableton.

## Ejecutable

`construir_exe.bat` compila la aplicación autocontenida en `dist\MaschineMK3AsPush\MaschineMK3AsPush.exe` (no requiere tener Python instalado para usarla).

| Comando | Qué hace |
|---|---|
| `MaschineMK3AsPush.exe` | Arranca el servicio de pantallas en segundo plano, sin ventana, y lo reinicia automáticamente si se desconecta la controladora. |
| `MaschineMK3AsPush.exe --salir` | Detiene y cierra todos los procesos del driver. |

El registro (`pantallas.log`), la configuración (`config.json`) y el estado quedan en `%LOCALAPPDATA%\MaschineMK3AsPush\`.  
Para que arranque automáticamente con Windows, colocá un acceso directo al .exe en `shell:startup`.

## Cómo funciona

- **Telemetría de Ableton:** El script MIDI de Ableton (`CustomMaschineMK3`) transmite su estado gráfico por UDP (puerto 9017).
- **Vistas en pantalla:** Se dibujan en tiempo real la vista Session (clips y escenas), el Mixer (vúmetros dinámicos y faders), Dispositivos/Plugins, Browser visual y modos de encoder (VOLUME / SWING / TEMPO) (`ableton_ui.py`, `encoder_view.py`).
- **Modo Reposo inteligente:** Al presionar <kbd>SHIFT</kbd> + <kbd>CHANNEL</kbd>, apaga botones y activa el salvapantallas con logo.
- `supervisor.py` vigila los procesos; `iniciar_pantallas.bat` lo arranca en consola para desarrollo rápido.

## Rendimiento y USB

- La Maschine recibe unos 5 MB/s por USB: una pantalla completa tarda ~50 ms (~20 fps). Se envían actualizaciones diferenciales (dirty rects) para máxima fluidez.
- Formato nativo: 2 pantallas de 480 × 272 en RGB565.
- Reconexión automática tolerante a desconexiones de cable USB o reinicios de Live.

## Más adelante

- [`PLAN.md`](PLAN.md): Arquitectura de driver nativo y soporte para entornos standalone.
