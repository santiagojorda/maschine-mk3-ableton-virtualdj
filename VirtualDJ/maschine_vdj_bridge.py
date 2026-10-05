"""
Puente VirtualDJ -> Maschine MK3.

VirtualDJ manda su salida (LEDs, pantalla) al puerto virtual "Maschine VDJ Out".
Este script la reenvia sin cambios a "Maschine MK3 Ctrl MIDI" y anota cada mensaje
en maschine_vdj_bridge.log (los textos de pantalla se decodifican para leerlos facil).

Necesita el driver teVirtualMIDI (viene con loopMIDI / rtpMIDI). Solo usa la libreria estandar.
Uso: python maschine_vdj_bridge.py   (Ctrl+C para salir)
"""

import ctypes
import ctypes.wintypes as W
import os
import queue
import sys
import threading
import time

VIRTUAL_PORT_NAME = "Maschine VDJ Out"
MASCHINE_OUT_NAME = "Maschine MK3 Ctrl MIDI"
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maschine_vdj_bridge.log")

TE_VM_FLAGS_PARSE_RX = 1
TE_VM_FLAGS_INSTANTIATE_RX_ONLY = 4
MHDR_DONE = 1
MCU_DISPLAY_HEADER = bytes([0xF0, 0x00, 0x00, 0x66, 0x17, 0x12])

virtual_midi = ctypes.WinDLL("teVirtualMIDI64.dll")
winmm = ctypes.WinDLL("winmm")

MIDI_DATA_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), W.DWORD, ctypes.c_void_p)
virtual_midi.virtualMIDICreatePortEx2.restype = ctypes.c_void_p
virtual_midi.virtualMIDICreatePortEx2.argtypes = [W.LPCWSTR, MIDI_DATA_CALLBACK, ctypes.c_void_p, W.DWORD, W.DWORD]
virtual_midi.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]


class MIDIOUTCAPS(ctypes.Structure):
    _fields_ = [("wMid", W.WORD), ("wPid", W.WORD), ("vDriverVersion", W.DWORD), ("szPname", W.WCHAR * 32),
                ("wTechnology", W.WORD), ("wVoices", W.WORD), ("wNotes", W.WORD), ("wChannelMask", W.WORD),
                ("dwSupport", W.DWORD)]


class MIDIHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", W.DWORD), ("dwBytesRecorded", W.DWORD),
                ("dwUser", ctypes.c_void_p), ("dwFlags", W.DWORD), ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_void_p), ("dwOffset", W.DWORD), ("dwReserved", ctypes.c_void_p * 8)]


def open_output(name):
    for index in range(winmm.midiOutGetNumDevs()):
        caps = MIDIOUTCAPS()
        winmm.midiOutGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(caps))
        if caps.szPname == name:
            handle = W.HANDLE()
            result = winmm.midiOutOpen(ctypes.byref(handle), index, 0, 0, 0)
            if result != 0:
                raise RuntimeError(f"No se pudo abrir '{name}' (error {result})")
            return handle
    raise RuntimeError(f"No se encontro la salida MIDI '{name}'")


def send(handle, message):
    if message[0] == 0xF0:
        buffer = ctypes.create_string_buffer(message, len(message))
        header = MIDIHDR()
        header.lpData = ctypes.cast(buffer, ctypes.c_void_p)
        header.dwBufferLength = len(message)
        winmm.midiOutPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header))
        winmm.midiOutLongMsg(handle, ctypes.byref(header), ctypes.sizeof(header))
        # The buffer must stay alive until the driver is done with it
        deadline = time.time() + 1.0
        while not header.dwFlags & MHDR_DONE and time.time() < deadline:
            time.sleep(0.0005)
        winmm.midiOutUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header))
    elif len(message) <= 3:
        packed = 0
        for shift, byte in enumerate(message):
            packed |= byte << (8 * shift)
        winmm.midiOutShortMsg(handle, packed)


def describe(message):
    if message.startswith(MCU_DISPLAY_HEADER) and len(message) > 8:
        position = message[6]
        text = message[7:-1].decode("ascii", "replace")
        return f"PANTALLA linea {position // 28} col {position % 28:2d}: [{text}]"
    return message.hex(" ")


def main():
    messages = queue.Queue()

    def on_data(port, data, length, instance):
        if data and length:
            messages.put(bytes(data[:length]))

    callback = MIDI_DATA_CALLBACK(on_data)
    port = virtual_midi.virtualMIDICreatePortEx2(VIRTUAL_PORT_NAME, callback, None, 0x1FFFE,
                                                 TE_VM_FLAGS_PARSE_RX | TE_VM_FLAGS_INSTANTIATE_RX_ONLY)
    if not port:
        sys.exit(f"No se pudo crear el puerto virtual '{VIRTUAL_PORT_NAME}' (falta teVirtualMIDI?)")
    output = open_output(MASCHINE_OUT_NAME)
    print(f"Puente activo: '{VIRTUAL_PORT_NAME}' -> '{MASCHINE_OUT_NAME}'. Log: {LOG_PATH}")

    stop = threading.Event()

    def forward():
        with open(LOG_PATH, "a", encoding="utf-8") as log:
            log.write(f"\n=== inicio {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            while not stop.is_set():
                try:
                    message = messages.get(timeout=0.2)
                except queue.Empty:
                    continue
                send(output, message)
                log.write(f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d} {describe(message)}\n")
                log.flush()

    worker = threading.Thread(target=forward, daemon=True)
    worker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        worker.join(timeout=1)
        virtual_midi.virtualMIDIClosePort(port)
        winmm.midiOutClose(output)


if __name__ == "__main__":
    main()
