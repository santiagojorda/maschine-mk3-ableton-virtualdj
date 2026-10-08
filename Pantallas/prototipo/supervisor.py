"""Supervisor de las pantallas: mantiene vivos vdj_puerto.py y dj_screens.py.

- vdj_puerto.py (puerto de datos de VirtualDJ): lo lanza primero, para que exista antes
  de que se abra VirtualDJ, y lo vuelve a lanzar si muere.
- dj_screens.py: lo lanza y lo reinicia si se cierra o si se cuelga (deja de escribir su
  pulso, .venv/dj_screens.heartbeat). Si se cae seguido, espera cada vez más entre intentos.
- Todo lo que imprime dj_screens.py va a .venv/pantallas.log con la hora; el registro se
  rota al pasar de 5 MB (queda el anterior como pantallas.log.1).

Una sola instancia: si ya hay uno corriendo (por ejemplo, el del inicio de Windows), sale.

Uso: python supervisor.py      (en una consola: además muestra el registro)
     pythonw supervisor.py     (sin ventana: así lo arranca Windows al iniciar sesión)
"""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE.parent / ".venv"
LOG_PATH = VENV / "pantallas.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
HEARTBEAT_FILE = VENV / "dj_screens.heartbeat"
SINGLE_INSTANCE_ADDRESS = ("127.0.0.1", 9020)
HEARTBEAT_TIMEOUT = 15.0  # sin pulso por más que esto = colgado
STARTUP_GRACE = 30.0  # al arrancar puede tardar (Windows recién iniciado, la Maschine apagada...)
CHECK_EVERY = 1.0


class Log:
    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        self._console = sys.stdout if sys.stdout is not None and sys.stdout.isatty() else None

    def write(self, text):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text.rstrip()}\n"
        with self._lock:
            try:
                if self._path.exists() and self._path.stat().st_size > LOG_MAX_BYTES:
                    backup = self._path.with_suffix(".log.1")
                    if backup.exists():
                        backup.unlink()
                    self._path.rename(backup)
                with open(self._path, "a", encoding="utf-8") as file:
                    file.write(line)
            except OSError:
                pass
            if self._console is not None:
                try:
                    self._console.write(line)
                    self._console.flush()
                except (OSError, UnicodeError):
                    pass


def python(windowless):
    """El python del venv (pythonw si es sin ventana)."""
    folder = VENV / "Scripts"
    executable = folder / ("pythonw.exe" if windowless else "python.exe")
    return str(executable if executable.exists() else sys.executable)


def kill_tree(pid):
    # El python del venv es un lanzador que abre el python real: hay que matar el árbol entero
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)


def heartbeat_age():
    try:
        return time.time() - HEARTBEAT_FILE.stat().st_mtime
    except OSError:
        return None


class Screens:
    """dj_screens.py como proceso hijo, con su salida al registro."""

    def __init__(self, log):
        self._log = log
        self.process = None
        self.started = 0.0
        self.failures = []  # horas de las últimas caídas, para esperar más si se cae seguido

    def start(self):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.process = subprocess.Popen(
            [python(windowless=False), "-u", str(HERE / "dj_screens.py")], cwd=str(HERE),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        self.started = time.time()
        threading.Thread(target=self._copy_output, args=(self.process,), daemon=True).start()
        self._log.write(f"[supervisor] dj_screens.py arrancó (pid {self.process.pid})")

    def _copy_output(self, process):
        for raw in process.stdout:
            self._log.write(raw.decode("utf-8", "replace"))

    def stop(self, reason):
        if self.process is None:
            return
        self._log.write(f"[supervisor] reinicio dj_screens.py: {reason}")
        kill_tree(self.process.pid)
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        self.process = None
        now = time.time()
        self.failures = [moment for moment in self.failures if now - moment < 300] + [now]

    def backoff(self):
        # 2 s la primera vez, y el doble por cada caída de los últimos 5 minutos, hasta 60 s
        return min(60.0, 2.0 * 2 ** max(0, len(self.failures) - 1))

    def check(self):
        if self.process is None:
            self.start()
            return
        code = self.process.poll()
        if code is not None:
            self.stop(f"se cerró (código {code})")
            time.sleep(self.backoff())
            self.start()
            return
        age = heartbeat_age()
        if time.time() - self.started > STARTUP_GRACE and (age is None or age > HEARTBEAT_TIMEOUT):
            self.stop(f"colgado (sin pulso hace {age:.0f} s)" if age is not None else "sin pulso")
            time.sleep(self.backoff())
            self.start()


def vdj_port_running():
    from vdj_data import BRIDGE_ADDRESS
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(BRIDGE_ADDRESS)
        return False
    except OSError:
        return True
    finally:
        probe.close()


def start_vdj_port(log):
    subprocess.Popen([python(windowless=True), "-u", str(HERE / "vdj_puerto.py")], cwd=str(HERE),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    log.write("[supervisor] lancé vdj_puerto.py (VirtualDJ se reconecta solo)")


def main():
    sys.path.insert(0, str(HERE))
    lock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        lock.bind(SINGLE_INSTANCE_ADDRESS)
    except OSError:
        message = f"Ya hay un supervisor corriendo. El registro está en {LOG_PATH}"
        if sys.stdout is not None:
            print(message)
        return 0

    log = Log(LOG_PATH)
    log.write("[supervisor] arrancó")
    screens = Screens(log)
    last_port_check = 0.0
    try:
        while True:
            if time.time() - last_port_check > 5.0:
                last_port_check = time.time()
                if not vdj_port_running():
                    start_vdj_port(log)
                    time.sleep(1.0)  # que el puerto exista antes de que dj_screens.py lo busque
            screens.check()
            time.sleep(CHECK_EVERY)
    except KeyboardInterrupt:
        log.write("[supervisor] cerrado con Ctrl+C")
    finally:
        if screens.process is not None:
            kill_tree(screens.process.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
