# Maschine MK3 as Ableton Push

Convertí tu **Maschine MK3** en un controlador al estilo **Ableton Push** para Live 12: la grilla de clips de la
vista session en las pantallas, lanzar clips con el encoder, mixer con faders y medidores, dispositivos con sus
perillas, browser… Y con un botón, la misma Maschine pasa a controlar **VirtualDJ**, con las ondas de los decks en
pantalla. Los dos programas quedan abiertos a la vez.

Por **Santiago Jorda**.

## Qué hace

**En Ableton Live**

- **Vista session en las pantallas** (ARRANGER): grilla de 8 tracks × 4 escenas con los colores y nombres de los
  clips. Un marco verde muestra los 4 tracks que están en los pads y un cursor blanco, el clip seleccionado.
- **Navegar como en un Push**: la rueda mueve el cursor, apretarla lanza el clip, y los pads y la grilla siguen
  al cursor.
- **Perillas de la vista session**: con ◀ manejan el volumen de los 8 tracks; con ▶, el dispositivo seleccionado.
  Al tocar una aparece su valor en un pop-up.
- **Mixer** con faders, medidores de nivel, paneo y envíos. **Dispositivos** con sus perillas, en el color de la
  cadena del rack o del track.
- **Browser** en las pantallas: la lista a la derecha (arranca en la User Library) y, a la izquierda, la grilla
  para ver dónde va a caer lo que cargues.
- **VOLUME / SWING / TEMPO**: volumen master, auriculares o tempo en la rueda, con su vista en la pantalla.
- **Atajos**: borrar el clip del track fijado (VARIATION), llevar una perilla a su valor por defecto
  (RESTART + perilla) o a cero (ERASE + doble toque, MUTE + perilla).

**En VirtualDJ** (botón SAMPLING)

- **Ondas de los dos decks** en la pantalla izquierda, en vivo.
- **Estado de los decks** en la derecha: tema, artista, BPM, BPM original, pitch, SYNC / MASTER, pitch lock, loop,
  volumen y filtro, con avisos al cambiar el loop, el sync o el pitch lock.
- **Browser** con la tapa de cada tema y una marca en los que ya pasaste.
- **Pads** para hot cues, transporte y loops, y **stems** (voz, instrumental, kick, hats, sin batería, solo batería).
- **Efectos** (reverb, flanger, echo), preescucha, crossfader en la tira táctil.

## Cómo está armado

| Parte | Carpeta | Qué hace |
|---|---|---|
| Script de Ableton | [`Ableton/CustomMaschineMK3`](Ableton/CustomMaschineMK3) | Toda la lógica en Live: vistas, perillas, botones, modo DJ |
| Mapeo de VirtualDJ | [`VirtualDJ`](VirtualDJ) | Definición del controlador y qué hace cada control en VirtualDJ |
| Plantilla del Controller Editor | [`Controller Editor`](Controller%20Editor) | Pone la Maschine en modo MIDI con la plantilla **CUSTOM MASCHINE** |
| Pantallas | [`Pantallas`](Pantallas) | Programa que dibuja en las pantallas de la Maschine (Ableton y VirtualDJ) |

Las pantallas son un programa aparte: si se cierra, pads, perillas y botones siguen funcionando igual.

## Requisitos

- Windows 11 con **Windows MIDI Services** (permite que Ableton y VirtualDJ usen la Maschine a la vez).
- Maschine MK3 y **Native Instruments Controller Editor** (modo MIDI).
- **Ableton Live 12 Suite**.
- **VirtualDJ** con stems (opcional).
- Para las pantallas: **Python 3.12**, **[Zadig](https://zadig.akeo.ie/)** y **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)**
  (trae el driver de puertos MIDI virtuales que usan los datos de VirtualDJ).

## Instalación

### 1. Controller Editor

Cerrarlo, copiar `Controller Editor/Configuration.ncc` a `Documentos\Native Instruments\Controller Editor\` y
volver a abrirlo. En la Maschine, elegir la plantilla **CUSTOM MASCHINE**.

### 2. Ableton

1. Copiar la carpeta `Ableton/CustomMaschineMK3` a
   `C:\ProgramData\Ableton\Live 12 Suite\Resources\MIDI Remote Scripts\`.
2. En *Preferences → Link, Tempo & MIDI*: Control Surface = **CustomMaschineMK3**, Input y Output =
   **Maschine MK3 Ctrl MIDI**.

### 3. VirtualDJ (opcional)

Copiar `VirtualDJ/Devices/MaschineMK3-VDJ.xml` a `%LocalAppData%\VirtualDJ\Devices\` y
`VirtualDJ/Mappers/MASCHINEMK3VDJ - Mapeo Personalizado.xml` a `%LocalAppData%\VirtualDJ\Mappers\`.
Reiniciar VirtualDJ.

### 4. Pantallas

1. **Zadig** (Options → List All Devices): poner **WinUSB** solo en **"Maschine MK3 BD (Interface 5)"**.
   No tocar las otras interfaces de la Maschine (0, 4 y 6): las usa el programa de Native Instruments y la 6 es
   la del firmware. Después, desenchufar y volver a enchufar la Maschine.
2. Armar el ejecutable, desde la carpeta `Pantallas` (hace falta Python 3.12 solo para este paso):

   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   construir_exe.bat
   ```

   Queda en `dist\MaschineMK3AsPush\MaschineMK3AsPush.exe`.

3. Para VirtualDJ, instalar el dispositivo de datos y reiniciar VirtualDJ:

   ```
   dist\MaschineMK3AsPush\MaschineMK3AsPush.exe --instalar-vdj
   ```

4. **Prender las pantallas:** doble clic en `MaschineMK3AsPush.exe`. Corre sin ventana y se reinicia solo si algo
   falla. Para detenerlas: `MaschineMK3AsPush.exe --salir`. Para que arranque con Windows, poner un acceso directo
   al .exe en la carpeta Inicio (`shell:startup`). Sin armar el .exe también se puede arrancar con
   `iniciar_pantallas.bat`.

La captura de las ondas está pensada para VirtualDJ en pantalla completa (1920 × 1200, skin PRO). Con otra
resolución o skin, ajustar las zonas en `prototipo/config.json`.

## Uso en Ableton

### Reposo (standby)

En reposo la Maschine está apagada del todo: pads y botones sin luz y sin respuesta, y las pantallas muestran
*Maschine mk3 as Push* a la izquierda y *by @santiagojorda / Maicol* a la derecha, en vez de lo que haya detrás. Pasa lo mismo cuando Ableton
está cerrado.

| Control | Qué hace |
|---|---|
| **SHIFT + CHANNEL** | Pasa a reposo (también saca a VirtualDJ del modo DJ) |
| **CHANNEL** | Despierta |
| **SAMPLING** / **MIXER** / **PLUGIN** | Despiertan y van a VirtualDJ / al mixer / al dispositivo |

El script arranca en reposo. Para que arranque despierto, poner `START_IN_STANDBY = False` en `Config.py`.

### Vistas

| Botón | Vista |
|---|---|
| **ARRANGER** | Vista session: grilla de clips en las dos pantallas |
| **MIXER** | Mixer: faders, paneo y envíos de 8 tracks |
| **PLUGIN** | Perillas del dispositivo seleccionado |
| **BROWSER** | Browser: lista a la derecha, grilla a la izquierda |
| **SAMPLING** | Pasa a VirtualDJ |

### Vista session

| Control | Qué hace |
|---|---|
| Girar la rueda | Mover el cursor de track en track |
| Inclinar la rueda arriba / abajo | Mover el cursor de escena en escena |
| Apretar la rueda | Lanzar el clip (o el slot) donde está el cursor |
| SHIFT + girar / inclinar | Mover los pads y la grilla a mano |
| ◀ / ▶ | Perillas en el volumen de los 8 tracks / en el dispositivo seleccionado |
| VARIATION | Borrar el clip del track fijado (Ctrl+Z lo recupera) |

Cuando el cursor sale de los pads, los pads se corren 4 tracks; cuando salen de la grilla, la grilla se corre 4
tracks. Hacia arriba o abajo, de a 1 escena.

### Perillas

| Combinación | Qué hace |
|---|---|
| RESTART + tocar una perilla | Valor por defecto (en el mixer, volumen a 0 dB) |
| ERASE + doble toque | A cero (mixer y vista session) |
| **SHIFT + RESTART** | Todos los volúmenes del mixer (tracks y retornos) a su valor por defecto; el master no se toca |
| MUTE + tocar | A cero; repetirlo vuelve al valor anterior (mixer y vista session) |

### Browser

Girar la rueda recorre la lista, inclinarla a la derecha entra a una carpeta, a la izquierda vuelve atrás y
apretarla carga. Cada vez que abrís el browser arranca dentro de **User Library**, que junta las carpetas que
agregaste a Live (por ejemplo DRUMS o CANCIONES) con lo que hay en la User Library; volviendo atrás se ve todo lo demás.

### Rueda: VOLUME, SWING y TEMPO

Con **VOLUME**, **SWING** o **TEMPO** la rueda maneja el volumen master, el de auriculares o el tempo, y la
pantalla derecha lo muestra. Cualquier botón de vista o de página de pads los apaga.

## Uso en VirtualDJ

**SAMPLING** pasa la Maschine a VirtualDJ; **MIXER** o **PLUGIN** la devuelven a Ableton. PLAY, STOP y TAP siguen
siendo de Ableton.

### Pantallas

- **Izquierda:** las ondas de los dos decks.
- **Derecha:** el estado de los decks, o el browser (botón **BROWSER**), o el volumen con VOLUME / SWING.
- El browser se cierra solo al tocar una perilla, cambiar de página de pads, usar el crossfader o un efecto.

### Pads

Columnas 1-2 = deck 1, columnas 3-4 = deck 2.

| Página | Pads |
|---|---|
| **KEYBOARD** | Hot cues 1-8 (ERASE + pad los borra) |
| **PAD MODE** | PLAY, PAUSA, SYNC, LOOP (prende y apaga), PITCH LOCK, LOOP ½, LOOP ×2 |
| **CHORDS** | Stems: RESET, INSTRUMENTAL, VOZ, KICK, HATS |
| **STEP** | Apagados |

Botones 1-4 sobre la pantalla: **DRUMLESS** (sin kick ni hats) y **BATERÍA** (solo kick y hats) del deck 1 / 2.

### Perillas y botones

| Control | Qué hace |
|---|---|
| Perillas 1 / 2 | Jog del deck 1 / 2 (SHIFT: saltar ±16 tiempos) |
| Perillas 3 / 4 | Tempo del deck 1 / 2 |
| Perillas 5 / 6 | Volumen del deck 1 / 2 |
| Perillas 7 / 8 | Filtro del deck 1 / 2 |
| RESTART + tocar una perilla | Jog: inicio del tema. Las demás: valor por defecto |
| SHIFT + RESTART | Apaga todos los efectos de los dos decks y pone los dos filtros en el centro |
| A / C / E / G | Deck 1: Reverb / Flanger / Echo / preescucha |
| B / D / F / H | Deck 2: lo mismo |
| ◀ / ▶ | Elegir el deck 1 / 2 |
| Rueda | Browser: girar recorre, apretar pasa entre carpetas y temas, inclinar a un costado carga en el deck 1 / 2 |
| Tira táctil | Crossfader |

## Modificar

- **VirtualDJ:** las páginas de pads y sus luces se generan con `VirtualDJ/generate_pads.py`; después hay que
  reinstalar los dos XML y reiniciar VirtualDJ.
- **Ableton:** después de cambiar el script, recargarlo eligiendo None y otra vez CustomMaschineMK3 en
  Preferences. Log: `%AppData%\Ableton\Live 12.x\Preferences\Log.txt`.
- **Registros:** todo queda registrado con fecha, hora y nivel, incluidos los errores con su detalle. Con `python tools/registros.py [minutos] [texto]` se ven todos juntos, en orden:
  - script de Ableton: `Preferences\Log.txt` de Live (líneas `CustomMaschineMK3:`) y `CustomMaschineMK3.log`
    (detalle del marco, se apaga con `LOGGING = False` en `Config.py`);
  - pantallas y supervisor: `%LOCALAPPDATA%\MaschineMK3AsPush\pantallas.log`;
  - puerto de datos de VirtualDJ: `%LOCALAPPDATA%\MaschineMK3AsPushdj_puerto.log`.
- **Pantallas:** más detalles en
  [`Pantallas/README.md`](Pantallas/README.md) y [`CONTEXTO-TECNICO.md`](CONTEXTO-TECNICO.md).

## Créditos y licencia

Creado por **Santiago Jorda**.

El script de Ableton parte de CustomMaschineMK3 (© 2024-2025 chiaki), software libre bajo GPL-3.0; este proyecto
se distribuye bajo la misma licencia. Ver [`LICENSE`](LICENSE).
