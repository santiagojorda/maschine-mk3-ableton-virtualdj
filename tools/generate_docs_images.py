"""Genera imágenes dual-screen de las vistas de Ableton para la documentación."""

import os
import sys
import types

# Mock maschine_display para evitar dependencia de libusb en la generación de imágenes
sys.modules['maschine_display'] = types.SimpleNamespace(WIDTH=480, HEIGHT=272)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Pantallas', 'prototipo')))

from PIL import Image, ImageDraw, ImageFont
import ableton_ui

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'images'))
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH = 480
HEIGHT = 272
GAP = 20
PADDING = 14
FRAME_BG = (22, 22, 24)
BEZEL_COLOR = (12, 12, 12)
BORDER_COLOR = (42, 42, 45)


def frame_displays(left_img, right_img, title=""):
    """Une las dos pantallas (480x272 c/u) con marco y terminación prolija tipo hardware."""
    total_w = PADDING * 2 + WIDTH * 2 + GAP
    total_h = PADDING * 2 + HEIGHT + (24 if title else 0)

    canvas = Image.new("RGB", (total_w, total_h), FRAME_BG)
    draw = ImageDraw.Draw(canvas)

    # Borde exterior suave del panel
    draw.rounded_rectangle((1, 1, total_w - 2, total_h - 2), radius=10, outline=BORDER_COLOR, width=2)

    top_offset = PADDING
    if title:
        try:
            font = ImageFont.truetype("arialbd.ttf", 13)
        except OSError:
            font = ImageFont.load_default()
        draw.text((PADDING + 4, 7), title.upper(), fill=(180, 180, 185), font=font)
        top_offset += 16

    # Pantalla izquierda
    x_left = PADDING
    draw.rectangle((x_left - 2, top_offset - 2, x_left + WIDTH + 1, top_offset + HEIGHT + 1), fill=BEZEL_COLOR, outline=(30, 30, 32))
    canvas.paste(left_img, (x_left, top_offset))

    # Pantalla derecha
    x_right = PADDING + WIDTH + GAP
    draw.rectangle((x_right - 2, top_offset - 2, x_right + WIDTH + 1, top_offset + HEIGHT + 1), fill=BEZEL_COLOR, outline=(30, 30, 32))
    canvas.paste(right_img, (x_right, top_offset))

    return canvas


def make_session_state():
    tracks = [
        {
            "name": "Kick & Snare",
            "color": 0xFF5722,  # Naranja
            "target": True,
            "slots": [
                {"name": "909 Groove", "color": 0xFF7043, "playing": True},
                {"name": "Break 01", "color": 0xFF7043},
                {"name": "Build 16th", "color": 0xFF7043},
                {"empty": True, "stop": True},
            ]
        },
        {
            "name": "HiHats",
            "color": 0xFF9800,  # Ambar
            "slots": [
                {"name": "Hats 8th", "color": 0xFFB74D, "playing": True},
                {"name": "Offbeat", "color": 0xFFB74D},
                {"name": "Rolls", "color": 0xFFB74D},
                {"empty": True, "stop": True},
            ]
        },
        {
            "name": "Bassline",
            "color": 0x2196F3,  # Azul
            "slots": [
                {"name": "Sub 01", "color": 0x64B5F6, "playing": True, "selected": True},
                {"name": "Acid 303", "color": 0x64B5F6},
                {"empty": True, "stop": True},
                {"name": "Drop Bass", "color": 0x64B5F6},
            ]
        },
        {
            "name": "Chords",
            "color": 0x9C27B0,  # Violeta
            "slots": [
                {"name": "Minor 7th", "color": 0xBA68C8, "playing": True},
                {"name": "Stab High", "color": 0xBA68C8},
                {"empty": True, "stop": True},
                {"name": "Pad Float", "color": 0xBA68C8},
            ]
        },
        {
            "name": "Main Lead",
            "color": 0x4CAF50,  # Verde
            "slots": [
                {"empty": True, "stop": True},
                {"name": "Hook A", "color": 0x81C784},
                {"name": "Hook B", "color": 0x81C784},
                {"name": "Solo Riff", "color": 0x81C784},
            ]
        },
        {
            "name": "Vocals",
            "color": 0xE91E63,  # Rosa
            "slots": [
                {"empty": True, "stop": True},
                {"name": "Phrase 01", "color": 0xF06292},
                {"name": "Chorus Top", "color": 0xF06292},
                {"empty": True, "stop": True},
            ]
        },
        {
            "name": "Percussion",
            "color": 0x00BCD4,  # Cyan
            "slots": [
                {"name": "Congas", "color": 0x4DD0E1, "playing": True},
                {"name": "Shaker", "color": 0x4DD0E1},
                {"empty": True, "stop": True},
                {"name": "Fill 8b", "color": 0x4DD0E1},
            ]
        },
        {
            "name": "FX / Riser",
            "color": 0x9E9E9E,  # Gris
            "slots": [
                {"empty": True, "stop": True},
                {"name": "Downsweep", "color": 0xBDBDBD},
                {"name": "Uplifter 8", "color": 0xBDBDBD},
                {"empty": True, "stop": True},
            ]
        },
    ]

    return {
        "session_view": True,
        "session": {
            "track_offset": 0,
            "page_offset": 0,
            "ring_column": 0,
            "scene_offset": 0,
            "ring_tracks": 4,
            "knob_page": "volume",
            "scenes": ["Intro", "Verse 1", "Chorus", "Outro"],
            "tracks": tracks,
        }
    }


def make_mixer_state():
    tracks_info = [
        ("Kick & Snare", 0xFF5722, "-2.5 dB", 0.85, 0.78),
        ("HiHats", 0xFF9800, "-4.0 dB", 0.80, 0.62),
        ("Bassline", 0x2196F3, "-3.2 dB", 0.82, 0.75),
        ("Chords", 0x9C27B0, "-6.0 dB", 0.75, 0.58),
        ("Main Lead", 0x4CAF50, "-5.1 dB", 0.77, 0.0),
        ("Vocals", 0xE91E63, "-2.0 dB", 0.86, 0.0),
        ("Percussion", 0x00BCD4, "-7.5 dB", 0.72, 0.50),
        ("FX / Riser", 0x9E9E9E, "-9.0 dB", 0.68, 0.0),
    ]

    knobs = []
    for idx, (name, color, text_val, val, meter) in enumerate(tracks_info):
        knobs.append({
            "name": "Volume",
            "track": f"{idx + 1} {name}",
            "color": color,
            "text": text_val,
            "value": val,
            "meter": meter,
        })

    return {
        "view": ableton_ui.MIXER_VIEW,
        "mixer_parameter": "VOLUMEN",
        "grid_frame": {"ring_column": 0, "ring_tracks": 4},
        "knobs": knobs,
        "touched": 0,
    }


def make_device_state():
    params = [
        ("Frequency", "1.82 kHz", 0.65),
        ("Resonance", "38 %", 0.38),
        ("Drive", "+3.5 dB", 0.35),
        ("Morph", "Lowpass", 0.15),
        ("LFO Amount", "60 %", 0.60),
        ("LFO Rate", "1/4", 0.45),
        ("Env Depth", "45 %", 0.45),
        ("Dry/Wet", "85 %", 0.85),
    ]

    knobs = []
    for name, text_val, val in params:
        knobs.append({
            "name": name,
            "text": text_val,
            "value": val,
        })

    return {
        "view": ableton_ui.DEVICE_VIEW,
        "device": "Auto Filter",
        "device_color": 0x2196F3,
        "track": "3 Bassline",
        "track_color": 0x2196F3,
        "locked": False,
        "knobs": knobs,
        "touched": 1,
    }


def make_browser_state():
    session_st = make_session_state()
    tracks = session_st["session"]["tracks"]

    return {
        "view": ableton_ui.BROWSER_VIEW,
        "browser": {
            "path": ["User Library", "Drums", "Acoustic Kits"],
            "list": {
                "count": 7,
                "selected": 2,
                "first": 0,
                "items": [
                    {"name": "707 Vintage Kit.adg", "folder": False},
                    {"name": "808 Sub Boom Kit.adg", "folder": False},
                    {"name": "909 Studio Punch.adg", "folder": False},
                    {"name": "Funk Soul Drums", "folder": True},
                    {"name": "Jazz Brushes Kit", "folder": True},
                    {"name": "Lofi Warmth Kit.adg", "folder": False},
                    {"name": "Techno Warehouse.adg", "folder": False},
                ]
            }
        },
        "browser_grid": {
            "ring_column": 0,
            "ring_tracks": 4,
            "page_offset": 0,
            "scene_offset": 0,
            "tracks": tracks,
        }
    }


def main():
    # 1. Vista Session
    st_session = make_session_state()
    left_session = ableton_ui.render_screen(st_session, 0)
    right_session = ableton_ui.render_screen(st_session, 1)
    img_session = frame_displays(left_session, right_session, "Vista Session (ARRANGER) - Grilla de 8 tracks x 4 escenas")
    img_session.save(os.path.join(OUT_DIR, "ableton-session-view.png"))
    print("Generada: ableton-session-view.png")

    # 2. Vista Mixer
    st_mixer = make_mixer_state()
    left_mixer = ableton_ui.render_screen(st_mixer, 0)
    right_mixer = ableton_ui.render_screen(st_mixer, 1)
    img_mixer = frame_displays(left_mixer, right_mixer, "Vista Mixer (MIXER) - Faders de volumen, vúmetros y niveles")
    img_mixer.save(os.path.join(OUT_DIR, "ableton-mixer-view.png"))
    print("Generada: ableton-mixer-view.png")

    # 3. Vista Dispositivo / Plugins
    st_device = make_device_state()
    left_device = ableton_ui.render_screen(st_device, 0)
    right_device = ableton_ui.render_screen(st_device, 1)
    img_device = frame_displays(left_device, right_device, "Vista Dispositivo (PLUGIN) - Perillas y parámetros de FX/Instrumentos")
    img_device.save(os.path.join(OUT_DIR, "ableton-device-view.png"))
    print("Generada: ableton-device-view.png")

    # 4. Vista Browser
    st_browser = make_browser_state()
    left_browser = ableton_ui.render_screen(st_browser, 0)
    right_browser = ableton_ui.render_screen(st_browser, 1)
    img_browser = frame_displays(left_browser, right_browser, "Vista Browser (BROWSER) - Grilla a la izquierda, navegador a la derecha")
    # 5. Vista Standby / Splash
    left_splash = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw_sl = ImageDraw.Draw(left_splash)
    from dj_screens import _centered_text
    _centered_text(draw_sl, "Maschine mk3", 68, 52, (255, 255, 255))
    _centered_text(draw_sl, "as Push", 132, 44, (255, 210, 0))

    right_splash = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw_sr = ImageDraw.Draw(right_splash)
    _centered_text(draw_sr, "by", 60, 24, (140, 140, 140))
    _centered_text(draw_sr, "@santiagojorda", 96, 40, (255, 255, 255))
    _centered_text(draw_sr, "Maicol", 156, 32, (255, 150, 30))

    img_splash = frame_displays(left_splash, right_splash)
    img_splash.save(os.path.join(OUT_DIR, "maschine-mk3-as-push-standby.png"))
    print("Generada: maschine-mk3-as-push-standby.png")


if __name__ == "__main__":
    main()
