# Maschine MK3 — Ableton Live + VirtualDJ

Un Maschine MK3 en modo MIDI que controla **Ableton Live 12 y VirtualDJ abiertos al mismo tiempo**.
Un botón pasa el control a VirtualDJ, otro lo devuelve a Ableton, y los dos programas se ponen de acuerdo
para que cada uno ignore lo que no le toca.

Incluye:

- el **script de Ableton** (Remote Script `CustomMaschineMK3`, modificado con el modo VirtualDJ),
- la **definición y el mapeo de VirtualDJ** para el Maschine,
- la **plantilla del Controller Editor** (`CUSTOM MASCHINE`),
- una **guía de uso** con todos los controles: [`Custom Maschine - All Operations.html`](Custom%20Maschine%20-%20All%20Operations.html) (se abre en el navegador, sin internet),
- el **contexto técnico** para seguir modificándolo: [`CONTEXTO-TECNICO.md`](CONTEXTO-TECNICO.md).

## Requisitos

- Windows 11 con **Windows MIDI Services** (permite que Ableton y VirtualDJ abran el puerto del Maschine a la vez).
- Ableton Live 12 Suite.
- VirtualDJ con stems (probado con la versión instalada en 2026).
- Native Instruments Controller Editor, con el Maschine MK3 en modo MIDI.
- Python 3 solo para regenerar los pads de VirtualDJ (`generate_pads.py`).

## Contenido

| Carpeta / archivo | Qué es | Dónde se instala |
|---|---|---|
| `Ableton/CustomMaschineMK3/` | Script de Ableton con el modo VirtualDJ (con su historial de git) | `C:\ProgramData\Ableton\Live 12 Suite\Resources\MIDI Remote Scripts\CustomMaschineMK3\` |
| `VirtualDJ/Devices/MaschineMK3-VDJ.xml` | Definición del controlador (controles, luces, pantallas) | `%LocalAppData%\VirtualDJ\Devices\` |
| `VirtualDJ/Mappers/MASCHINEMK3VDJ - Mapeo Personalizado.xml` | Mapeo: qué hace cada control | `%LocalAppData%\VirtualDJ\Mappers\` |
| `VirtualDJ/generate_pads.py` | Genera las páginas de pads, sus luces y el modo info en los dos XML | — |
| `VirtualDJ/maschine_vdj_bridge.py` | Puente MIDI con log, solo para diagnóstico (no se usa) | — |
| `Controller Editor/Configuration.ncc` | Configuración del Controller Editor con la plantilla **CUSTOM MASCHINE** | `Documentos\Native Instruments\Controller Editor\` |
| `Custom Maschine - All Operations.html` | Guía de uso completa | — |
| `CONTEXTO-TECNICO.md` | Cómo está hecho, mapa MIDI, lecciones y pendientes | — |

## Instalación

1. **Controller Editor:** cerrarlo, copiar `Configuration.ncc` a `Documentos\Native Instruments\Controller Editor\` y abrirlo. En el Maschine, elegir la plantilla **CUSTOM MASCHINE**.
2. **Ableton:** copiar la carpeta `Ableton/CustomMaschineMK3` a `MIDI Remote Scripts` (ruta de arriba). En *Preferences → Link, Tempo & MIDI*: Control Surface = **CustomMaschineMK3**, Input y Output = **Maschine MK3 Ctrl MIDI**.
3. **VirtualDJ:** copiar la definición a `Devices` y el mapeo a `Mappers`, y reiniciar VirtualDJ.

## Uso

### Cambiar de programa

| Control | Qué hace |
|---|---|
| **SAMPLING** | Pasa a VirtualDJ ("modo DJ"). Ableton deja de responder y de escribir luces y pantalla. Activa el key lock en los dos decks. |
| **MIXER** / **PLUGIN** | Vuelve a Ableton (y entra a su modo mixer o dispositivo). |
| **LOCK** en modo DJ | Fija los pads a VirtualDJ: al volver a Ableton, los pads y sus 4 botones de página siguen siendo de VirtualDJ. |
| **LOCK** en Ableton | Suelta los pads fijados. Si no estaban fijados, hace su función normal de Ableton. |

### Controles compartidos

| Control | En Ableton | En modo DJ |
|---|---|---|
| **PLAY**, **STOP**, **SHIFT + STOP** | Transporte de Ableton | Igual: siguen siendo de Ableton |
| **TAP**, **SHIFT + TAP** | Tap tempo, metrónomo | Igual: siguen siendo de Ableton |
| **FOLLOW** | Ableton Link de Ableton | Ableton Link de VirtualDJ |
| **VOLUME** / **SWING** / **TEMPO** | Encoder = volumen master / auriculares / tempo | Encoder = volumen master / auriculares; TEMPO los apaga |
| **REC** | Grabar | No hace nada |
| Botones 1-4 sobre la pantalla | Nada (son de VirtualDJ) | KICK y HATS del deck 1 (1, 2) y del deck 2 (3, 4); también andan estando en Ableton |
| Botones 5-8 sobre la pantalla | Asignaciones MIDI propias de Ableton | Siguen siendo de Ableton |

VOLUME, SWING y TEMPO se excluyen entre sí y se comparten: el que dejes activo sigue activo al cambiar de programa.
En Ableton tienen prioridad sobre el Browser y Settings: toman el encoder en cualquier vista, y al apretar de nuevo
el encoder vuelve a navegar.
Mientras el modo está activo, la pantalla izquierda lo muestra (**VOLUMEN MASTER**, **VOLUMEN AURIS** o el tempo) sin tocar el encoder.

### Pads en VirtualDJ

Columnas 1-2 = deck 1, columnas 3-4 = deck 2. La página se elige con los botones de la izquierda.

| Página | Pads (por deck) |
|---|---|
| **KEYBOARD** | Hot cues 1-8. Tocar guarda o salta; **ERASE + pad** borra. Luz azul (deck 1) o naranja (deck 2) si el cue existe. |
| **PAD MODE** | De abajo hacia arriba: PLAY (verde) / PAUSA (rojo) · — / SYNC (amarillo) · LOOP 4 (violeta) / PITCH LOCK (naranja, el candado de VirtualDJ) · LOOP ½ / LOOP ×2 (celeste) |
| **CHORDS** (stems) | Columna derecha de arriba hacia abajo: RESET (amarillo), INSTRUMENTAL (azul, melodía + bajo), VOZ (verde), KICK (rojo). A la izquierda de KICK: HATS (naranja). |
| **STEP** | Todos apagados y sin función |

Luces: tenue = disponible, fuerte = activo (o el stem suena). Los pads de stems son independientes y pueden
estar varios prendidos; RESET prende todos. Al tocar un stem, la pantalla del deck muestra su nombre y ON/OFF.

### Perillas en VirtualDJ

| Perilla | Qué hace | ERASE + tocar |
|---|---|---|
| 1 / 2 | Jog del deck 1 / 2. **SHIFT** = saltar ±16 tiempos | Vuelve suave al tempo original |
| 3 / 4 | Tempo del deck 1 / 2 (±1 BPM por paso; el tono no cambia) | Vuelve suave al tempo original |
| 5 / 6 | Volumen del deck 1 / 2 | Volumen al 100 % |
| 7 / 8 | Filtro del deck 1 / 2 | Filtro al centro |

Al tocar una perilla, la pantalla muestra qué controla y su valor (1-4 en la pantalla izquierda, 5-8 en la derecha).

### Encoder grande en VirtualDJ

| Acción | Qué hace |
|---|---|
| Girar | Moverse por la lista (carpetas o temas) |
| Apretar | Pasar entre carpetas y temas |
| Inclinar arriba / abajo | Subir / bajar de a uno |
| Inclinar izquierda / derecha | Carpetas: abrir/cerrar. Temas: cargar en el deck 1 / 2 |
| SHIFT + inclinar a un costado | Copiar en ese deck el tema del otro deck, en la misma posición |
| Tocar | Muestra título, artista y BPM del tema elegido (o el nombre de la carpeta) |

### Botones en VirtualDJ

| Control | Qué hace |
|---|---|
| A / C / E / G | Deck 1: Reverb / Flanger / Echo / preescucha (PFL). Luz azul si está activo. |
| B / D / F / H | Deck 2: lo mismo, con luz naranja |
| ◀ / ▶ | Elegir el deck 1 / 2 |
| RESTART | Volver al inicio del tema del deck elegido |
| NOTES | Preescuchar el tema elegido mientras se mantiene |
| SELECT (mantener) | Modo info: tocar un control muestra su nombre en vez de ejecutarlo |
| ERASE (mantener) | Borrar hot cues y restablecer perillas |
| Touch strip | Crossfader (las luces muestran la posición) |

Pantalla izquierda = deck 1, derecha = deck 2: título arriba; BPM y MASTER / SYNC / NO SYNC abajo.
Los acentos no se ven (Windows MIDI los descarta).

### Cambios en Ableton respecto del script original

- **SAMPLING** entra al modo DJ (ya no abre el editor de clips).
- **FOLLOW** = Ableton Link (antes: cuantización de grabación).
- **SWING** = volumen de auriculares (cue) en el encoder; se sacaron el groove y SHIFT + SWING (posición del arrangement).
- En el Browser, la perilla 1 ya no cambia el volumen de la preescucha.
- VOLUME / SWING / TEMPO también funcionan en el Browser y en Settings (antes ahí no hacían nada).
- En el touch strip en modo **PITCH**, las luces siguen el dedo y vuelven al centro al soltar.

## Modificar

**VirtualDJ:** las páginas de pads, sus luces y el modo info se generan; no se editan a mano.

```
cd VirtualDJ
python generate_pads.py
```

Editar `TRANSPORT`, `STEMS` o `HELP_BUTTONS` en `generate_pads.py` y correrlo. Después **instalar los dos XML**
(Devices y Mappers) y reiniciar VirtualDJ: si cambia un color, la luz nueva vive en la definición.
El resto del mapeo se edita en el XML directamente. Detalles, mapa MIDI y lecciones en [`CONTEXTO-TECNICO.md`](CONTEXTO-TECNICO.md).

**Ableton:** el script vive en `Ableton/CustomMaschineMK3` (rama de trabajo `feature/vdj-mode` en la copia instalada).
Para recargarlo: reiniciar Ableton, o elegir None y otra vez CustomMaschineMK3 en Preferences.
Log: `%AppData%\Ableton\Live 12.x\Preferences\Log.txt`.

## Si algo se desfasa

Cada programa lleva su propio estado. Si se reinicia uno solo:

- **MIXER / PLUGIN**: los dos salen del modo DJ.
- **SAMPLING**: los dos entran al modo DJ.
- **LOCK** estando en Ableton: los dos sueltan los pads.

Cambios en la definición de VirtualDJ requieren reiniciar VirtualDJ. Cambios solo en el mapeo: alcanza con desactivar y activar el Maschine.

## Limitaciones conocidas

- No se pueden mostrar acentos ni imágenes en las pantallas.
- Los nombres de los controles que muestra el Maschine ("V-Pot 1", etc.) son fijos de la plantilla.

## Licencia

El script de Ableton se basa en CustomMaschineMK3 (© 2024-2025 chiaki), software libre bajo **GPL-3.0**;
las modificaciones y el resto del repositorio se distribuyen bajo la misma licencia. Ver [`LICENSE`](LICENSE).
