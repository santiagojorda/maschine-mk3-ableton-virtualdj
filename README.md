# 🎹 Maschine MK3 as Ableton Push

[![Ableton Live 12](https://img.shields.io/badge/Ableton%20Live-12%20Suite-00D2B4.svg)](https://www.ableton.com)
[![Native Instruments](https://img.shields.io/badge/Hardware-Maschine%20MK3-black.svg)](https://www.native-instruments.com)
[![Windows 11](https://img.shields.io/badge/OS-Windows%2011%20MIDI%20Services-0078D4.svg)](https://microsoft.com)
[![Manual Web](https://img.shields.io/badge/Manual-All%20Operations%20(Web)-brightgreen.svg)](https://santiagojorda.github.io/maschine-mk3-as-ableton-push/)
[![YouTube Playlist](https://img.shields.io/badge/YouTube-Maicol%20Session-FF0000?logo=youtube&logoColor=white)](https://www.youtube.com/watch?v=ImqHw-zkiZQ&list=PLxk2dEOPjuEYO00P264yMStEUhukVkO1y)
[![Instagram](https://img.shields.io/badge/Instagram-@santiagojorda-E4405F?logo=instagram&logoColor=white)](http://instagram.com/santiagojorda)

![Maschine MK3 as Ableton Push by @santiagojorda](docs/images/maschine-mk3-as-push-standby.png)

Convertí tu **Maschine MK3** en un potente controlador al estilo **Ableton Push** para **Live 12**:
- 📺 **Grilla de clips en tiempo real** en las dos pantallas a color.
- 🎛️ **Navegación tipo Push**: lanzá clips y escenas con el encoder 4D.
- 🎚️ **Mixer gráfico**: faders verticales, medidores de nivel (vúmetros) dinámicos y paneo estéreo.
- 🔌 **Control de dispositivos y plugins**: perillas con valores y nombres sincronizados.
- 📁 **Browser visual**: lista de carpetas a la derecha y grilla de destino a la izquierda.
- 🛑 **Modo Reposo inteligente**: protege las pantallas y evita toques accidentales.

> 📖 **[Ver Manual Web de Todas las Operaciones](https://santiagojorda.github.io/maschine-mk3-as-ableton-push/)**: guía visual interactiva completa con diagramas de botones y perillas.

---

### 🎵 El Origen: Maicol Sessions
Todo esto empezó por mis sesiones combinando **Maschine MK3** y **Ableton Live**: una combinación tremenda donde el sampler de Maschine resulta súper cómodo y versátil con sus perillas dedicadas, y tener el control estilo Push permite manejar absolutamente todo el set sin tocar el mouse.

- 📺 **YouTube Playlist:** [Maicol Session: Ableton Push + Maschine MK3](https://www.youtube.com/watch?v=ImqHw-zkiZQ&list=PLxk2dEOPjuEYO00P264yMStEUhukVkO1y)
- 📸 **Instagram:** [@santiagojorda](http://instagram.com/santiagojorda)

---

## 📸 Vistas en las Pantallas de Ableton

Las dos pantallas de la Maschine MK3 muestran la interfaz gráfica nativa de Ableton en vivo:

### 1. Vista Session (`ARRANGER`)
Grilla completa de **8 pistas × 4 escenas** con los nombres y colores reales de tus clips. Un marco verde destaca las 4 pistas asignadas a los pads (zonas A–H) y un cursor blanco marca el clip seleccionado en Live. Los clips en reproducción se identifican con un borde verde.

![Vista Session en las pantallas](docs/images/ableton-session-view.png)

---

### 2. Vista Mixer (`MIXER`)
Faders verticales por canal, vúmetros con graduación verde/amarillo/rojo, paneo estéreo y niveles exactos en dB. Las pistas llevan su color correspondiente y el marco verde indica las pistas vinculadas a los pads.

![Vista Mixer en las pantallas](docs/images/ableton-mixer-view.png)

---

### 3. Vista Dispositivo / Plugins (`PLUGIN`)
Las 8 perillas toman los parámetros del instrumento o efecto de audio seleccionado. Muestra el nombre del dispositivo, el color asignado a la cadena o pista y los valores exactos en tiempo real (frecuencia, resonancia, drive, dry/wet, etc.).

![Vista Dispositivo en las pantallas](docs/images/ableton-device-view.png)

---

### 4. Vista Browser (`BROWSER`)
Navegador de sonidos integrado: la pantalla izquierda mantiene la grilla de sesión para ver exactamente dónde caerá el elemento seleccionado, mientras la pantalla derecha permite explorar tu **User Library**, carpetas y presets cómodamente con el encoder.

![Vista Browser en las pantallas](docs/images/ableton-browser-view.png)

---

## 🎮 Guía Rápida de Controles

### 🛑 Reposo (Standby)
Para cuidar las pantallas y evitar toques accidentales cuando no estés tocando:

| Control | Acción |
|---|---|
| **SHIFT + CHANNEL** | Pasa a reposo: apaga pads y botones, y muestra el salvapantallas con logo. |
| **CHANNEL** | Despierta la controladora. |
| **MIXER** / **PLUGIN** / **ARRANGER** | Despiertan la controladora y van directamente a esa vista. |

---

### 🔲 Vistas Principales

| Botón | Vista |
|---|---|
| **ARRANGER** | **Vista Session:** grilla de clips en las dos pantallas. |
| **MIXER** | **Vista Mixer:** faders, medidores de nivel, paneo y envíos de 8 pistas. |
| **PLUGIN** | **Vista Dispositivo:** perillas del plugin o efecto seleccionado. |
| **BROWSER** | **Vista Browser:** lista en pantalla derecha, grilla en pantalla izquierda. |

---

### 🕹️ Navegación de Clips y Escenas (Estilo Push)

| Control | Acción |
|---|---|
| **Girar rueda (Encoder)** | Mover el cursor de pista en pista. |
| **Inclinar rueda (Arriba / Abajo)** | Mover el cursor de escena en escena. |
| **Apretar rueda** | Lanzar el clip (o disparar la celda) bajo el cursor. |
| **SHIFT + girar / inclinar** | Desplazar manualmente la grilla y pads (4 pistas al costado, 1 escena arriba/abajo). |
| **Botones A–H** | Saltar rápido de a 4 pistas: A (1-4), B (5-8), C (9-12), etc. |
| **Botones ◀ / ▶** | En vista Session, alternan las 8 perillas entre volumen de pistas y parámetros del dispositivo. |
| **VARIATION** | **Borrar clip:** elimina el clip bajo el cursor en vista Session (o el último grabado en otras vistas; recuperable con `Ctrl+Z`). |
| **EVENTS** | **Crear escena:** inserta una nueva escena debajo de la actual, detiene el clip de esa pista y ubica el cursor allí. |

---

### 🎛️ Atajos y Modificadores en Perillas

| Combinación | Acción |
|---|---|
| **RESTART + tocar perilla** | Restablece el parámetro a su valor por defecto (en mixer: 0 dB). |
| **ERASE + doble toque** | Lleva el parámetro a cero (paneo al centro, etc.). |
| **SHIFT + RESTART** | Restablece todos los volúmenes del mixer a su valor por defecto (el Master no se modifica). |
| **MUTE + tocar perilla** | Detiene el clip que está sonando en la pista de esa perilla. |
| **SOLO + tocar perilla** | Activa o desactiva la preescucha (Solo) de esa pista. |
| **RESTART + SOLO** | Desactiva todas las preescuchas activas. |
| **FOLLOW + tocar perilla** | Dispara el clip de esa pista en la escena donde está posicionado el cursor. |

---

### 🔊 Volumen Master, Auriculares y Tempo

Al presionar cualquiera de estos botones, el encoder principal toma el control y la pantalla derecha muestra el valor numérico y gráfico:
- **VOLUME:** Volumen Master.
- **SWING:** Volumen de auriculares / preescucha (Cue).
- **TEMPO:** Tempo general en BPM.
- Presionar cualquier botón de vista o pad apaga este modo.

---

## 🚀 Instalación Rápida (3 Pasos)

> 💡 **Requisitos:** Windows 10/11, Ableton Live 12 Suite y Maschine MK3 conectada por USB.

### 1️⃣ Plantilla en Controller Editor
1. Cerrá **Controller Editor**.
2. Copiá el archivo `Controller Editor/Configuration.ncc` en:  
   `Documentos\Native Instruments\Controller Editor\`
3. Abrí **Controller Editor** y en la Maschine seleccioná la plantilla **CUSTOM MASCHINE**.

### 2️⃣ Script en Ableton Live
1. Copiá la carpeta `Ableton/CustomMaschineMK3` dentro de:  
   `C:\ProgramData\Ableton\Live 12 Suite\Resources\MIDI Remote Scripts\`
2. En Ableton Live (*Opciones → Preferencias → Link, Tempo & MIDI*):
   - **Superficie de control:** `CustomMaschineMK3`
   - **Entrada:** `Maschine MK3 Ctrl MIDI`
   - **Salida:** `Maschine MK3 Ctrl MIDI`

### 3️⃣ Pantallas de la Maschine
1. **Driver USB (solo la primera vez):**
   - Abrí el programa gratuito **[Zadig](https://zadig.akeo.ie/)** (*Options → List All Devices*).
   - Seleccioná **`Maschine MK3 BD (Interface 5)`**, elegí **WinUSB** y hacé clic en **Install Driver** *(no toques las otras interfaces)*. Desconectá y volvé a conectar el cable USB.
2. **Encender las pantallas:**
   - Ejecutá `Pantallas\iniciar_pantallas.bat` (o `MaschineMK3AsPush.exe` si armaste el ejecutable).
   - ¡Listo! Las pantallas se encenderán mostrando la sesión de Live.

---

## 🔄 Cómo Volver al Uso Normal de la Maschine

Si querés usar la Maschine MK3 como siempre con el software oficial de **Native Instruments** (Maschine 2 / Komplete):

### 1. En el día a día (sin desinstalar nada)
1. **Cerrá las pantallas:** Cerrá la ventana de `iniciar_pantallas.bat` (o cerrá `MaschineMK3AsPush.exe`).
2. **Volver al software Maschine:**
   - Abrí el software **Maschine 2**.
   - En el controlador, presioná **`SHIFT + CHANNEL`** (MIDI) para alternar entre el modo MIDI y el modo nativo del software Maschine.
   - ¡Listo! Todo vuelve a funcionar exactamente como viene de fábrica.

### 2. Restaurar el driver original de NI (si alguna vez querés quitar WinUSB)
Si en algún momento querés dejar la Maschine de fábrica al 100% y retirar el driver WinUSB de la interfaz 5:
1. Abrí el **Administrador de Dispositivos** de Windows (`devmgmt.msc`).
2. Buscá en *Dispositivos de bus serie universal* (o *Universal Serial Bus devices*) la entrada **`Maschine MK3 BD (Interface 5)`**.
3. Hacé clic derecho → **Desinstalar el dispositivo** (marcando la casilla de eliminar el controlador).
4. Desconectá y volvé a conectar el cable USB de la Maschine. Windows reinstalará automáticamente el driver original oficial de Native Instruments.

---

## 📝 Diagnóstico y Registros

Para ver los registros de Ableton y de las pantallas en tiempo real:
```bash
python tools/registros.py [minutos] [filtro]
```

---

## 👤 Creador y Créditos

- **Desarrollo y concepto:** Santiago Jorda (Maicol)  
  - 📺 [Maicol Session en YouTube](https://www.youtube.com/watch?v=ImqHw-zkiZQ&list=PLxk2dEOPjuEYO00P264yMStEUhukVkO1y)  
  - 📸 Instagram: [@santiagojorda](http://instagram.com/santiagojorda)
- **Base del script:** *CustomMaschineMK3* (chiaki).
