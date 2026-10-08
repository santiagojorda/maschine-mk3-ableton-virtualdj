"""Paso 6: el prototipo completo.

Modo DJ (SAMPLING): cada pantalla muestra en vivo las zonas de VirtualDJ de
config.json, apiladas de arriba a abajo y con su propia velocidad. BROWSER prende
y apaga, en la pantalla derecha, la lista de carpetas o temas que tiene el foco (vdj_browser.py);
si no, la derecha muestra el estado de los decks con los datos de VirtualDJ (dj_info.py, vdj_data.py). Con
"capture_from": "window" (por defecto) se captura la ventana de VirtualDJ en
sí, aunque esté tapada (no minimizada), y las zonas van en coordenadas de la
ventana; con "screen", lo que se ve en el monitor. Modo Ableton
(MIXER / PLUGIN): en las vistas mixer y dispositivo, faders y knobs dibujados
con el estado que manda el script (ableton_ui.py); en las demás, el texto
(ableton_text.py); hasta que llega algo, un cartel "ABLETON".

La Maschine acepta ~20 pantallas completas por segundo en total (~50 ms cada
una), así que conviene repartir: ondas rápido, info de los decks lento. Una
pantalla que no cambió no se reenvía.

Uso: python dj_screens.py [--config config.json] [--start dj]
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ableton_text import DEFAULT_PORT as ABLETON_TEXT_PORT
from ableton_text import AbletonText, render_screen
from ableton_ui import render_screen as render_ui_screen
from ableton_ui import PopupTracker, screen_kind, touched_knobs, wants_graphics
from maschine_display import HEIGHT, WIDTH, MaschineDisplays
from mode import ABLETON, DJ, ModeWatcher
from screen_capture import RegionCapture, set_dpi_aware
from leds import blank_leds
from paths import DATA_DIR, child_command, config_path
from dj_info import render_decks
from encoder_view import dj_encoder
from encoder_view import render_ableton as render_ableton_encoder
from vdj_browser import BrowserView
from vdj_data import BRIDGE_ADDRESS, VdjData
from window_capture import BackgroundWindowCapture

STATS_EVERY_S = 5.0
SCREEN_NAMES = ("left", "right")
ABLETON_FPS = 30
BROWSER_FPS = 12
BROWSER_DISPLAY = 1  # derecha: la izquierda sigue con las ondas
DECKS_DISPLAY = 1  # derecha, cuando no está el browser: estado de los decks
DECKS_FPS = 15
ENCODER_DISPLAY = 1  # VOLUME / SWING, en los dos modos
# Cada tanto se manda todo de nuevo, aunque no haya cambiado: si otro programa (el de NI al cambiar
# de modo, por ejemplo) dibujó en las pantallas, como solo se manda lo que cambia, quedaría pisado
FULL_REFRESH_SECONDS = 2.0


class MeterSmoother:
    """Medidores suaves: Ableton manda el estado 10 veces por segundo; entre dato y dato
    el medidor sube al instante y baja de a poco, así se ve fluido a 30 cuadros por segundo."""

    FALL_PER_SECOND = 1.5

    def __init__(self):
        self._levels = {}
        self._last = time.perf_counter()

    def apply(self, state):
        now = time.perf_counter()
        elapsed, self._last = now - self._last, now
        knobs = []
        for index, knob in enumerate(state.get("knobs") or []):
            if knob and "meter" in knob:
                level = max(knob["meter"], self._levels.get(index, 0.0) - self.FALL_PER_SECOND * elapsed)
                self._levels[index] = level
                knob = dict(knob, meter=level)
            knobs.append(knob)
        return dict(state, knobs=knobs)


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    config.setdefault("midi_port", "Maschine MK3 Ctrl MIDI")
    config.setdefault("ableton_text_port", ABLETON_TEXT_PORT)
    config.setdefault("capture_from", "window")
    for name in SCREEN_NAMES:
        screen = config["screens"][name]
        screen.setdefault("fit", "contain")
        screen.setdefault("fps", 10)
        screen.setdefault("regions", [])
        # Alto de la zona que se manda, centrada (el resto queda en negro). La Maschine tarda ~0,18 ms
        # por fila: 272 filas = 49 ms (20 fps máx.), 216 filas = 39 ms (25 fps).
        screen["height"] = min(HEIGHT, screen.get("height", HEIGHT)) // 2 * 2
    return config


HEARTBEAT_FILE = DATA_DIR / "dj_screens.heartbeat"
STOP_FILE = DATA_DIR / "detener"  # el supervisor lo crea para pedir un cierre ordenado
MODE_FILE = DATA_DIR / "ultimo_modo.txt"  # para volver al mismo modo tras un reinicio


def saved_mode():
    try:
        mode = MODE_FILE.read_text(encoding="ascii").strip()
    except OSError:
        return ABLETON
    return mode if mode in (DJ, ABLETON) else ABLETON


class Heartbeat:
    """Pulso para supervisor.py: escribe la hora en un archivo, como mucho una vez por segundo.
    Si deja de cambiar, el programa está colgado y el supervisor lo reinicia."""

    def __init__(self, path=HEARTBEAT_FILE):
        self._path = path
        self._last = 0.0

    def __call__(self):
        now = time.time()
        if now - self._last < 1.0:
            return
        self._last = now
        try:
            self._path.write_text(f"{now:.0f}", encoding="ascii")
        except OSError:
            pass


FIRST_STATE_WAIT_SECONDS = 1.0  # tope de espera del primer estado de Ableton al volver de DJ
FIRST_CAPTURE_WAIT_SECONDS = 1.0  # tope de espera de la primera captura de VirtualDJ al entrar a DJ
IDLE_BLANK_SECONDS = 15.0  # en reposo, cada cuánto se vuelven a apagar las luces
VDJ_SILENT_SECONDS = 4.0  # un deck sonando manda su posición todo el tiempo


def vdj_link_warning(vdj_data, capture):
    """Por qué los datos de VirtualDJ pueden estar viejos, o None si está todo bien."""
    if vdj_data is None:
        return "Sin puerto de datos de VirtualDJ"
    # (VirtualDJ se reconecta solo si el puerto se vuelve a crear: alcanza con mirar si llegan datos)
    with vdj_data.lock:
        playing = any(deck.get("playing") for deck in vdj_data.decks)
    if playing and time.time() - vdj_data.last_live > VDJ_SILENT_SECONDS:
        return "VirtualDJ no manda datos: reinicialo"
    return None


def vdj_port_running():
    """vdj_puerto.py tiene tomado el puerto UDP de pedidos: si se puede tomar, no está corriendo."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(BRIDGE_ADDRESS)
        return False
    except OSError:
        return True
    finally:
        probe.close()


class Throttled:
    """Un mensaje que se repite (USB desconectado, por ejemplo) se imprime cuando cambia o cada 30 s."""

    def __init__(self, every_seconds=30.0):
        self._last = None
        self._time = 0.0
        self._every = every_seconds

    def __call__(self, text):
        now = time.perf_counter()
        if text != self._last or now - self._time >= self._every:
            print(text)
            self._last, self._time = text, now


def start_vdj_port():
    """Lanza vdj_puerto.py aparte y sin ventana (pythonw), para que sobreviva a los reinicios del
    prototipo (si ya corre, sale solo). Su registro queda en vdj_puerto.log."""
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    for extra in (0x01000000, 0):  # CREATE_BREAKAWAY_FROM_JOB, si el job lo permite
        try:
            subprocess.Popen(child_command("port", windowless=True),
                             cwd=str(DATA_DIR), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=flags | extra, close_fds=True)
            return
        except OSError:
            continue


PROJECT_TITLE = "MASCHINE MK3 AS PUSH"
# Pantalla derecha del reposo: (texto, tamaño máximo, y, color)
AUTHOR_LINES = (("by", 22, 70, (140, 140, 140)), ("@santiagojorda", 38, 100, (255, 255, 255)),
                ("Maicol", 30, 155, (255, 150, 30)))


def _truetype(name, size):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _centered_text(draw, text, y, max_size, color, max_width=WIDTH - 40):
    """Texto centrado en negrita; achica la letra hasta que entre en el ancho."""
    size = max_size
    font = _truetype("arialbd.ttf", size)
    while size > 14 and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = _truetype("arialbd.ttf", size)
    draw.text(((WIDTH - draw.textlength(text, font=font)) / 2, y), text, fill=color, font=font)


def splash(title=PROJECT_TITLE, status=None):
    """Las pantallas de reposo, iguales para Ableton y para VirtualDJ. Izquierda: el título (el del proyecto, o el
    del programa que falta) y abajo, en gris, qué hacer (status). Derecha: el autor."""
    left = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(left)
    _centered_text(draw, title, 95, 40, (255, 255, 255))
    if status:
        _centered_text(draw, status, 165, 26, (150, 150, 150))
    right = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(right)
    for line, size, y, color in AUTHOR_LINES:
        _centered_text(draw, line, y, size, color)
    return left, right


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--start", choices=[DJ, ABLETON], default=None,
                        help="modo al arrancar (por defecto, el último que se usó)")
    parser.add_argument("--midi-log", action="store_true", help="imprimir todos los mensajes MIDI que llegan")
    args = parser.parse_args()
    if args.start is None:
        args.start = saved_mode()

    config = load_config(args.config)
    screens = [config["screens"][name] for name in SCREEN_NAMES]

    set_dpi_aware()
    STOP_FILE.unlink(missing_ok=True)  # uno viejo cerraría el programa apenas arranque
    beat = Heartbeat()
    beat()
    displays = MaschineDisplays.wait_for_device(on_wait=beat)
    try:
        for display, image in enumerate(splash()):
            displays.send_image(display, image)
        time.sleep(2.0)
    except Exception as error:  # la bienvenida no puede frenar el arranque
        print(f"Bienvenida: {error!r}")
    if config["capture_from"] == "window":
        capture = BackgroundWindowCapture(fps=max(screen["fps"] for screen in screens))
    else:
        capture = RegionCapture()
    watcher = ModeWatcher(
        port_hint=config["midi_port"],
        start_mode=args.start,
        on_message=(lambda message: print(f"MIDI {message}")) if args.midi_log else None,
    )
    ableton_text = AbletonText(config["ableton_text_port"])
    start_vdj_port()
    try:
        vdj_data = VdjData()
        print("Escuchando los datos de VirtualDJ (puerto 'MK3 Screens', vdj_puerto.py)")
    except Exception as error:
        vdj_data = None
        print(f"Sin datos de VirtualDJ: {error}")
    print(f"Escuchando '{watcher.port_name}' y el texto de Ableton en UDP {config['ableton_text_port']}. "
          f"Modo inicial: {args.start.upper()}. Ctrl+C para salir.")

    # Sin datos de Ableton (cerrado, o el script sin cargar): un cartel; nunca el último texto, que queda viejo
    # Reposo: Ableton cerrado, sin mandar datos o en standby (SHIFT + CHANNEL): la bienvenida del proyecto
    idle_images = {"standby": splash(), "ableton": splash(status="Iniciá Ableton")}  # en reposo / sin datos
    browser_view = BrowserView(config.get("browser"))
    mode = None
    showing_browser = False
    next_due = [0.0, 0.0]
    last_sent = [None, None]
    last_frame = [None, None]  # última imagen mandada en modo gráfico, para mandar solo lo que cambia
    meters = MeterSmoother()
    popup_tracker = PopupTracker()
    last_version = 0  # para contar cuántos estados de Ableton llegan entre estadísticas
    sent = [0, 0]
    stats_start = time.perf_counter()
    last_full_refresh = time.perf_counter()
    last_port_check = time.perf_counter()
    last_idle_blank = 0.0  # 0 = las luces se apagan apenas empieza el reposo
    ableton_wait_until = 0.0  # al volver a Ableton: hasta cuándo se espera su primer estado
    ableton_state_mark = 0
    capture_mark = None  # al entrar a DJ: cuántas capturas había; se espera una más antes de dibujar
    capture_deadline = 0.0

    def blank_unused_bands():
        # Si la zona capturada de una pantalla no la llena (height < 272), el resto tiene que quedar en negro
        for display, screen in enumerate(screens):
            if screen["height"] < HEIGHT:
                displays.send_rgb(display, np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8))

    report = Throttled()
    vdj_idle = splash("VIRTUAL DJ", "Iniciá VirtualDJ")
    vdj_idle_left = np.asarray(vdj_idle[0].crop((0, (HEIGHT - screens[0]["height"]) // 2, WIDTH,
                                                 (HEIGHT + screens[0]["height"]) // 2)))
    vdj_idle_right = np.asarray(vdj_idle[1])

    try:
        while True:
          beat()
          if STOP_FILE.exists():
              print("Cierre ordenado pedido por el supervisor")
              break
          try:
              # Lo que se puede caer sin que el prototipo se entere: el puerto MIDI de la Maschine
              # (al apagarla) y vdj_puerto.py (se vuelve a lanzar)
              watcher.ensure_connected()
              if time.perf_counter() - last_port_check >= 5.0:
                  last_port_check = time.perf_counter()
                  if not vdj_port_running():
                      print("vdj_puerto.py no está corriendo: lo vuelvo a lanzar (VirtualDJ se reconecta solo)")
                      start_vdj_port()
              if watcher.sync(ableton_text.reported_mode()):
                  print("(modo tomado del script de Ableton)")
              new_mode = watcher.mode
              if time.perf_counter() - last_full_refresh >= FULL_REFRESH_SECONDS:
                  last_full_refresh = time.perf_counter()
                  last_sent = [None, None]
                  last_frame = [None, None]
              if new_mode != mode:
                  mode = new_mode
                  print(f"--> modo {mode.upper()}")
                  try:
                      MODE_FILE.write_text(mode, encoding="ascii")
                  except OSError:
                      pass
                  last_sent = [None, None]
                  last_frame = [None, None]
                  next_due = [0.0, 0.0]
                  if hasattr(capture, "set_active"):
                      capture.set_active(mode == DJ)
                  if mode != DJ:
                      # Al volver a Ableton, lo que había se queda hasta que llega su primer estado: en DJ el script
                      # no manda estado, y sin él esperaría 2 s y mostraría "sin conexión" un instante
                      ableton_wait_until = time.perf_counter() + FIRST_STATE_WAIT_SECONDS
                      ableton_state_mark = ableton_text.state_version
                  if mode == DJ:
                      # Sin pasar por negro: lo que había se queda hasta que llega la primera captura nueva (la que
                      # está guardada es de la vez anterior en DJ)
                      capture_mark = getattr(capture, "captures", None)
                      capture_deadline = time.perf_counter() + FIRST_CAPTURE_WAIT_SECONDS
                      blank_unused_bands()

              browser = mode == DJ and watcher.browser
              if browser != showing_browser:
                  showing_browser = browser
                  print("--> browser" if browser else "--> ondas")
                  last_sent = [None, None]
                  last_frame = [None, None]
                  next_due = [0.0, 0.0]

              if mode != DJ:
                  frame_start = time.perf_counter()
                  state = ableton_text.state(max_age=2.0)
                  if (state is None and time.perf_counter() < ableton_wait_until
                          and ableton_text.state_version == ableton_state_mark):
                      time.sleep(0.01)
                      continue
                  # Reposo (Ableton cerrado o en standby): pads y botones sin luz, aunque el script no pueda
                  if state is None or state.get("standby"):
                      if time.perf_counter() - last_idle_blank >= IDLE_BLANK_SECONDS:
                          last_idle_blank = time.perf_counter()
                          try:
                              blank_leds(config["midi_port"])
                          except Exception as error:  # no es grave: el reposo sigue mostrando la bienvenida
                              report(f"No se pudieron apagar las luces: {error!r}")
                  else:
                      last_idle_blank = 0.0
                  # VOLUME / SWING: la pantalla derecha muestra el encoder, igual que en modo DJ
                  encoder = state.get("encoder") if state else None
                  graphics = wants_graphics(state)
                  smoothed = meters.apply(state) if graphics else None
                  if graphics:
                      smoothed = dict(smoothed, popups=popup_tracker.update(touched_knobs(state)))
                  for display in range(2):
                      try:
                          if display == ENCODER_DISPLAY and encoder:
                              image = render_ableton_encoder(encoder)
                          elif graphics:
                              # Session, mixer o dispositivo: solo se manda lo que cambió
                              image = render_ui_screen(smoothed, display)
                          else:
                              image = None
                          if image is not None:
                              rgb = np.asarray(image)
                              if displays.send_changes(display, rgb, last_frame[display]):
                                  sent[display] += 1
                              last_frame[display] = rgb
                              last_sent[display] = None
                              continue
                      except Exception as error:  # un cuadro perdido no frena la pantalla
                          print(f"Error dibujando Ableton: {error!r}")
                          last_frame[display] = None
                          continue
                      last_frame[display] = None
                      # El texto (vistas sin gráficos: clip, settings...) solo con datos frescos de Ableton
                      idle_kind = "ableton" if state is None else ("standby" if state.get("standby") else None)
                      content = (idle_kind, display) if idle_kind else ableton_text.screen_lines(display)
                      if content == last_sent[display]:
                          continue
                      displays.send_image(display, idle_images[idle_kind][display] if idle_kind
                                          else render_screen(*content))
                      last_sent[display] = content
                  elapsed = time.perf_counter() - stats_start
                  if elapsed >= STATS_EVERY_S:
                      if state is None:
                          print("Ableton: sin estado JSON (¿cerrado o script sin recargar?); se muestra el cartel")
                      else:
                          print(f"Ableton: dibuja {screen_kind(state) or 'texto'}, vista {state.get('view')}, "
                                f"session {state.get('session_view')}, encoder {state.get('encoder_mode')}, "
                                f"estados {ableton_text.state_version - last_version} en {elapsed:.0f} s, "
                                f"cuadros {sent[0] / elapsed:.1f} / {sent[1] / elapsed:.1f} por segundo")
                          (DATA_DIR / "last_state.json").write_text(
                              json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
                      last_version = ableton_text.state_version
                      sent = [0, 0]
                      stats_start = time.perf_counter()
                  time.sleep(max(0.0, 1.0 / ABLETON_FPS - (time.perf_counter() - frame_start)))
                  continue

              if capture_mark is not None:
                  if getattr(capture, "captures", capture_mark + 1) <= capture_mark \
                          and time.perf_counter() < capture_deadline:
                      time.sleep(0.01)
                      continue
                  capture_mark = None

              now = time.perf_counter()
              vdj_open = capture.process_started() is not None if hasattr(capture, "process_started") else True
              for display, screen in enumerate(screens):
                  if now < next_due[display]:
                      continue
                  if display == DECKS_DISPLAY and not vdj_open:
                      # VirtualDJ cerrado: la misma pantalla de reposo, también en browser o VOLUME / SWING
                      next_due[display] = now + 1.0 / DECKS_FPS
                      if displays.send_changes(display, vdj_idle_right, last_frame[display]):
                          sent[display] += 1
                      last_frame[display] = vdj_idle_right
                      continue
                  encoder_image = dj_encoder(vdj_data) if display == ENCODER_DISPLAY else None
                  if encoder_image is not None:
                      # VOLUME / SWING: la misma vista que en Ableton
                      next_due[display] = now + 1.0 / DECKS_FPS
                      rgb = np.asarray(encoder_image)
                      if displays.send_changes(display, rgb, last_frame[display]):
                          sent[display] += 1
                      last_frame[display] = rgb
                      continue
                  if browser and display == BROWSER_DISPLAY:
                      next_due[display] = now + 1.0 / BROWSER_FPS
                      try:
                          window = capture.latest() if hasattr(capture, "latest") else None
                          focus = browser_view.focus
                          rgb = browser_view.render_focused(window)
                          if browser_view.focus != focus:
                              print(f"--> browser: {browser_view.focus}")
                          if displays.send_changes(display, rgb, last_frame[display]):
                              sent[display] += 1
                          last_frame[display] = rgb
                      except Exception as error:
                          print(f"Error en el browser: {error!r}")
                          last_frame[display] = None
                      continue
                  if display == DECKS_DISPLAY:
                      next_due[display] = now + 1.0 / DECKS_FPS
                      try:
                          rgb = np.asarray(render_decks(vdj_data, vdj_link_warning(vdj_data, capture)))
                          if displays.send_changes(display, rgb, last_frame[display]):
                              sent[display] += 1
                          last_frame[display] = rgb
                      except Exception as error:
                          print(f"Error en los decks: {error!r}")
                          last_frame[display] = None
                      continue
                  next_due[display] = now + 1.0 / screen["fps"]
                  try:
                      if display == 0 and hasattr(capture, "latest") and capture.latest() is None:
                          rgb = vdj_idle_left  # VirtualDJ cerrado o minimizado: la pantalla de reposo
                      else:
                          rgb = capture.grab_stack(screen["regions"], screen["fit"], screen["height"])
                      frame = rgb.tobytes()
                      if frame != last_sent[display]:
                          displays.send_rgb(display, rgb, 0, (HEIGHT - screen["height"]) // 2)
                          last_sent[display] = frame
                          sent[display] += 1
                  except Exception as error:  # un cuadro perdido no corta el prototipo
                      report(f"Error en la pantalla {display}: {error}")
                      if isinstance(error, RuntimeError):  # la Maschine no está: no tiene sentido seguir este ciclo
                          raise

              elapsed = time.perf_counter() - stats_start
              if elapsed >= STATS_EVERY_S:
                  print(f"fps enviados: izquierda {sent[0] / elapsed:.1f}, derecha {sent[1] / elapsed:.1f}; "
                        f"datos de VirtualDJ: {vdj_data.messages if vdj_data else 'sin puerto'}")
                  sent = [0, 0]
                  stats_start = time.perf_counter()

              wait = min(next_due) - time.perf_counter()
              if wait > 0:
                  time.sleep(wait)
          except Exception as error:
              # Nada corta el prototipo: un error (por ejemplo, USB) se anota y se reintenta
              report(f"Error en el ciclo: {error!r}; sigo en medio segundo")
              last_sent = [None, None]
              last_frame = [None, None]
              time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.close()
        ableton_text.close()
        if vdj_data is not None:
            vdj_data.close()
        capture.close()
        try:
            # Al cerrar quedan en las pantallas la bienvenida (el reposo), no un cuadro cortado
            for display, image in enumerate(splash()):
                displays.send_image(display, image)
        except Exception:
            pass
        finally:
            displays.close()


if __name__ == "__main__":
    main()
