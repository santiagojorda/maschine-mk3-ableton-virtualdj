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
from ableton_ui import screen_kind, wants_graphics
from maschine_display import HEIGHT, WIDTH, MaschineDisplays
from mode import ABLETON, DJ, ModeWatcher
from screen_capture import RegionCapture, set_dpi_aware
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


HEARTBEAT_FILE = Path(__file__).resolve().parent.parent / ".venv" / "dj_screens.heartbeat"
MODE_FILE = Path(__file__).resolve().parent.parent / ".venv" / "ultimo_modo.txt"  # para volver al mismo modo tras un reinicio


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
    prototipo (si ya corre, sale solo). Su registro queda en .venv/vdj_puerto.log."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw if pythonw.exists() else sys.executable)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    for extra in (0x01000000, 0):  # CREATE_BREAKAWAY_FROM_JOB, si el job lo permite
        try:
            subprocess.Popen([executable, "-u", str(Path(__file__).with_name("vdj_puerto.py"))],
                             cwd=str(Path(__file__).parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=flags | extra, close_fds=True)
            return
        except OSError:
            continue


PROJECT_NAME = "Maschine MK3 as Ableton Push"
AUTHOR = "Santiago Jorda"


def _truetype(name, size):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def banner(text, credit=True):
    """Texto grande centrado; abajo, chico, el nombre del proyecto y el autor."""
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    font = _truetype("arialbd.ttf", 56)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    position = ((WIDTH - (right - left)) // 2 - left, (HEIGHT - (bottom - top)) // 2 - top)
    draw.text(position, text, fill=(255, 255, 255), font=font)
    if credit:
        small = _truetype("arial.ttf", 15)
        line = f"{PROJECT_NAME}  ·  {AUTHOR}"
        draw.text(((WIDTH - draw.textlength(line, font=small)) / 2, HEIGHT - 30), line, fill=(120, 120, 120),
                  font=small)
    return image


def splash():
    """Pantallas de bienvenida: el nombre del proyecto a la izquierda y el autor a la derecha."""
    left = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(left)
    for text, size, y, color in (("MASCHINE MK3", 44, 70, (255, 255, 255)),
                                 ("as Ableton Push", 30, 130, (255, 150, 30))):
        font = _truetype("arialbd.ttf", size)
        draw.text(((WIDTH - draw.textlength(text, font=font)) / 2, y), text, fill=color, font=font)
    right = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(right)
    for text, size, y, color in (("by", 22, 85, (140, 140, 140)), (AUTHOR, 40, 115, (255, 255, 255))):
        font = _truetype("arialbd.ttf", size)
        draw.text(((WIDTH - draw.textlength(text, font=font)) / 2, y), text, fill=color, font=font)
    return left, right


def banner_strip(text, height=HEIGHT):
    """Aviso en gris, centrado, como array listo para mandar."""
    image = Image.new("RGB", (WIDTH, height))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    width = draw.textlength(text, font=font)
    draw.text(((WIDTH - width) / 2, height / 2 - 12), text, fill=(150, 150, 150), font=font)
    return np.asarray(image)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--start", choices=[DJ, ABLETON], default=None,
                        help="modo al arrancar (por defecto, el último que se usó)")
    parser.add_argument("--midi-log", action="store_true", help="imprimir todos los mensajes MIDI que llegan")
    args = parser.parse_args()
    if args.start is None:
        args.start = saved_mode()

    config = load_config(args.config)
    screens = [config["screens"][name] for name in SCREEN_NAMES]

    set_dpi_aware()
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
    # Programa cerrado (o sin mandar datos): la izquierda dice solo su nombre y la derecha queda vacía
    ableton_banner = banner("ABLETON")
    blank = Image.new("RGB", (WIDTH, HEIGHT))
    browser_view = BrowserView(config.get("browser"))
    mode = None
    showing_browser = False
    next_due = [0.0, 0.0]
    last_sent = [None, None]
    last_frame = [None, None]  # última imagen mandada en modo gráfico, para mandar solo lo que cambia
    meters = MeterSmoother()
    last_version = 0  # para contar cuántos estados de Ableton llegan entre estadísticas
    sent = [0, 0]
    stats_start = time.perf_counter()
    last_full_refresh = time.perf_counter()
    last_port_check = time.perf_counter()
    report = Throttled()
    window_missing = np.asarray(banner("VIRTUAL DJ", credit=screens[0]["height"] == HEIGHT).crop((0, (HEIGHT - screens[0]["height"]) // 2, WIDTH,
                                                         (HEIGHT + screens[0]["height"]) // 2)))
    blank_rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    try:
        while True:
          beat()
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
                  if mode == DJ:
                      # Las bandas fuera de la zona de cada pantalla quedan en negro desde acá
                      displays.clear()

              browser = mode == DJ and watcher.browser
              if browser != showing_browser:
                  showing_browser = browser
                  print("--> browser" if browser else "--> ondas")
                  last_sent = [None, None]
                  last_frame = [None, None]
                  next_due = [0.0, 0.0]
                  if mode == DJ and not browser:
                      displays.clear()

              if mode != DJ:
                  frame_start = time.perf_counter()
                  state = ableton_text.state(max_age=2.0)
                  # VOLUME / SWING: la pantalla derecha muestra el encoder, igual que en modo DJ
                  encoder = state.get("encoder") if state else None
                  graphics = wants_graphics(state)
                  smoothed = meters.apply(state) if graphics else None
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
                      content = ableton_text.screen_lines(display) if state is not None else f"banner{display}"
                      if content == last_sent[display]:
                          continue
                      if content == "banner0":
                          image = ableton_banner
                      elif content == "banner1":
                          image = blank
                      else:
                          image = render_screen(*content)
                      displays.send_image(display, image)
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
                          Path(__file__).resolve().parent.parent.joinpath(".venv", "last_state.json").write_text(
                              json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
                      last_version = ableton_text.state_version
                      sent = [0, 0]
                      stats_start = time.perf_counter()
                  time.sleep(max(0.0, 1.0 / ABLETON_FPS - (time.perf_counter() - frame_start)))
                  continue

              now = time.perf_counter()
              vdj_open = capture.process_started() is not None if hasattr(capture, "process_started") else True
              for display, screen in enumerate(screens):
                  if now < next_due[display]:
                      continue
                  if display == DECKS_DISPLAY and not vdj_open:
                      # VirtualDJ cerrado: la derecha vacía, también en browser o VOLUME / SWING
                      next_due[display] = now + 1.0 / DECKS_FPS
                      if displays.send_changes(display, blank_rgb, last_frame[display]):
                          sent[display] += 1
                      last_frame[display] = blank_rgb
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
                          rgb = window_missing  # VirtualDJ cerrado o minimizado: se avisa en vez de negro
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
            displays.clear()
        except Exception:
            pass
        finally:
            displays.close()


if __name__ == "__main__":
    main()
