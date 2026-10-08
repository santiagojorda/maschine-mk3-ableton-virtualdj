# ==================================================
#
# This file is part of CustomMaschineMK3.
# CustomMaschineMK3 is free software licensed under GPL-3.0.
# For more details, see "LICENSE" file.
# 
# Copyright (C) 2024-2025 chiaki
#
# ==================================================

from functools import partial
from itertools import product
from time import perf_counter, sleep
import json
import socket

import Live # type: ignore
from Live.Base import Timer # type: ignore

from ableton.v3.base import lazy_attribute, const, listens
from ableton.v3.live import liveobj_name, liveobj_valid, parameter_owner, scene_index
from ableton.v3.control_surface import (
    ControlSurface,
    ControlSurfaceSpecification,
    IdentificationComponent
)

from ableton.v3.control_surface.component import (
    Component
)

from ableton.v3.control_surface.display import DisplaySpecification

from ableton.v3.control_surface.components import (
    SessionRingComponent,
    PlayableComponent,
    NoteEditorComponent,
    NoteEditorPaginator,
    StepSequenceComponent,
    SequencerClip,
    GridResolutionComponent,
    SessionComponent,
    TargetTrackComponent,
    DEFAULT_SIMPLER_TRANSLATION_CHANNEL,
    DEFAULT_DRUM_TRANSLATION_CHANNEL
)

from ableton.v3.control_surface.components.grid_resolution import GridResolution
from Live.Clip import GridQuantization # type: ignore

from ableton.v3.control_surface.elements import SimpleColor, RgbColor, create_rgb_color

from .ControlElements import ControlElements
from .Mappings import create_mappings
from .ColorSkin import MaschineSkin
from .DisplayDefinitions import (
    MaschineDisplay,
    TOUCH_STATES,
    get_display_value,
    make_mcu_display_header,
    make_display_sysex_message
)
from .GroovePoolComponent import GroovePoolComponent
from .MasterVolumeComponent import MasterVolumeComponent, CueVolumeComponent
from .MaschinePlayableComponent import MaschinePlayableComponent, DEFAULT_NOTE_TRANSLATION_CHANNEL
from .CustomDrumGroupComponent import CustomDrumGroupComponent
from .MiscControlComponent import MiscControlComponent
from .CustomDeviceComponent import (
    CUSTOM_BANK_DEFINITIONS,
    CustomDeviceDecoratorFactory,
    CustomDeviceComponent
)
from .CustomDeviceNavigationComponent import CustomDeviceNavigationComponent
from .SessionVolumeComponent import SessionVolumeComponent
from .CustomMixerComponent import CustomMixerComponent
from .MaschineMixerComponent import MaschineMixerComponent
from .CustomClipActionsComponent import CustomClipActionsComponent
from .CustomSlicedSimplerComponent import CustomSlicedSimplerComponent
from .NoteRepeatComponent import NoteRepeatComponent
from .VelocityLevelsComponent import VelocityLevelsComponent
from .ScaleSystemComponent import ScaleSystemComponent
from .SelectedParameterControlComponent import SelectedParameterControlComponent
from .CustomNoteEditorComponent import CustomNoteEditorComponent, CustomStepSequenceComponent
from .CustomLoopSelectorComponent import CustomLoopSelectorComponent
from .ClipEditorComponent import ClipEditorComponent
from .BrowserComponent import BrowserComponent
from .RecordingMethod import FixedLengthRecordingMethod, CustomViewBasedRecordingComponent
from .EncoderModeControlComponent import EncoderModeControlComponent
from .GroupButtonModeControlComponent import GroupButtonModeControlComponent
from .CustomTransportComponent import CustomTransportComponent
from .SettingsComponent import SettingsRepository, SettingsComponent
from .CustomClipSlotComponent import LEDBlinker, CustomClipSlotComponent
from .PageableBackgroundComponent import PageableBackgroundComponent

from .Logger import logger
from . import Config

# VirtualDJ mode: "SAMPLING" hands the Maschine over to VirtualDJ, "PLUGIN" or "MIXER" brings it back.
# (status byte, CC number) of each button, all of them on MIDI channel 2
VDJ_ENTER_BUTTON = (0xB1, 39)
# Standby: SHIFT + CHANNEL puts the Maschine to rest (everything off, welcome on the screens); CHANNEL wakes it,
# and so do the mode buttons (SAMPLING also enters VirtualDJ mode, MIXER and PLUGIN select their view)
STANDBY_BUTTON = (0xB1, 34)
SHIFT_BUTTON = (0xB1, 119)
STANDBY_WAKE_BUTTONS = ((0xB1, 34), (0xB1, 35), (0xB1, 37))
# Only the controllers that are LEDs: sending a value to all 128 also hits MIDI's special messages
# (CC 120-127 channel mode, RPN / NRPN, bank select...) and can leave the Maschine in an odd state
STANDBY_LED_CCS = (34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 47, 48, 49, 52, 53, 55, 56, 57, 58, 59, 80, 81, 82, 83, 84, 87, 88, 100, 101, 102, 103, 104, 105, 106, 107, 110, 111)
STANDBY_LED_NOTES = range(4)  # buttons 1-4 above the screens (channel 2)
VDJ_EXIT_BUTTONS = ((0xB1, 35), (0xB1, 37))
# Buttons that keep controlling Ableton even in VirtualDJ mode: PLAY, STOP, TAP (messages and their LEDs).
# SHIFT (sysex from the MK3 / Plus) also gets through, so SHIFT + STOP and SHIFT + TAP (metronome) work too.
ABLETON_ALWAYS_BUTTONS = ((0xB1, 57), (0xB1, 59), (0xB1, 55))
SHIFT_SYSEX_PREFIX = (0xF0, 0x00, 0x21, 0x09)
# VOLUME / SWING / TEMPO (encoder = master / cue volume / tempo) are shared with VirtualDJ: in VirtualDJ mode Ableton still follows
# their presses (without LEDs) so the encoder mode stays the same in both programs
SHARED_ENCODER_MODE_BUTTONS = ((0xB1, 44), (0xB1, 45), (0xB1, 47))  # VOLUME, SWING, TEMPO (mutually exclusive)
# "FOLLOW" toggles Ableton's Link in Ableton (replaces its record quantize function).
# In VirtualDJ mode it belongs to VirtualDJ (its Ableton Link effect) and its LED too.
LINK_BUTTON = (0xB1, 56)
PAD_LOCK_MODE = "vdj_locked"
# Ticks (about 100ms each) to wait before the full LEDs and display refresh after leaving VirtualDJ mode,
# so VirtualDJ's last messages don't overwrite Ableton's state. The display itself is redrawn immediately too.
VDJ_REFRESH_DELAY = 1
# "LOCK" pressed in VirtualDJ mode keeps the pads with VirtualDJ after going back to Ableton ("pad lock").
# Pressing "LOCK" in Ableton releases them. VirtualDJ's mapping mirrors the same logic.
PAD_LOCK_BUTTON = (0xB1, 48)
PAD_NOTES = range(60, 76)
# Screen bridge: the Pantallas program drives the Maschine's screens (NI's software can't), so every display line
# the script sends also goes to it over UDP on localhost. The last lines are resent every second,
# so the bridge gets the text even when it starts after Live.
# About 30 times per second (a Live.Base.Timer: schedule_message ticks are ~100ms, too slow for smooth knobs)
# it also gets a JSON state (view, the 8 knob parameters, their tracks' meters, touched knob)
# so it can draw faders and knobs instead of text.
MCU_DISPLAY_HEADER = (0xF0, 0x00, 0x00, 0x66, 0x17, 0x12)
SCREEN_BRIDGE_ADDRESS = ("127.0.0.1", Config.SCREEN_BRIDGE_PORT)
SCREEN_BRIDGE_INTERVAL_MS = 33
SCREEN_BRIDGE_STALL_SECONDS = 0.3
SCREEN_BRIDGE_RESEND_TICKS = 30  # display lines are resent about once per second
KNOB_COUNT = 8
# Knob touch (CC 10-17, MIDI channel 2). MUTE + touching a knob in the mixer sends its parameter to zero
# (pan to center); doing it again restores the previous value
KNOB_TOUCH_CCS = tuple((0xB1, 10 + index) for index in range(KNOB_COUNT))
# RESTART + touching a knob sets it to its default value; RESTART alone still toggles the loop, on release
RESTART_BUTTON = (0xB1, 53)
STEP_BUTTON = (0xB1, 84)  # RESTART + STEP: every volume in the mixer back to its default
ERASE_DOUBLE_TOUCH_SECONDS = 0.4
MIXER_DISPLAY_MODE = "default"
# ARRANGER shows Live's Session view and the clip grid on the Maschine's screens (both screens: 4 tracks each);
# it stays on until another view button (VIEW_BUTTONS) is pressed. Its LED shows it.
SESSION_VIEW_BUTTON = (0xB1, 36)
SESSION_DISPLAY_MODE = "session"
# VARIATION (NAVIGATE) deletes the clip of the locked (target) track: the one playing or recording, or else the one
# in the selected scene. For a bad take; Live's undo brings it back
DELETE_CLIP_BUTTON = (0xB1, 88)
# Session view, encoder in its default mode (like Push): turning or tilting up / down moves the selected clip slot
# one scene, tilting left / right one track, always inside the grid on the screens (it doesn't move);
# with SHIFT they move the grid instead; pushing fires the selected clip slot
SESSION_NAV_TURN = (0xB1, 7)
SESSION_NAV_PUSH = (0xB1, 8)
SESSION_NAV_TILTS = {(0xB1, 30): (0, -1), (0xB1, 31): (1, 0), (0xB1, 32): (0, 1), (0xB1, 33): (-1, 0)}  # (track, scene)
ENCODER_DEFAULT_MODE = "default"
SESSION_GRID_TRACKS = 8
SESSION_GRID_SCENES = 4
SESSION_GRID_STEP = 4  # the grid on the screens moves sideways in steps of 4 tracks
BROWSER_DISPLAY_MODE = "browser"
BROWSER_BRIDGE_ITEMS = 12  # items sent on each side of the selected one
TEMPO_SCREEN_RANGE = (60.0, 200.0)  # BPM range of the tempo bar on the screens
# PAD MODE, KEYBOARD, CHORDS and STEP select VirtualDJ's pad page, so they follow the pads while locked
PAD_PAGE_BUTTONS = ((0xB1, 81), (0xB1, 82), (0xB1, 83), (0xB1, 84))
# Buttons 1-4 above the screen (notes 0-3, channel 2) belong to VirtualDJ only (stems KICK / HATS of each deck):
# Ableton never uses them, in any mode, and never drives their LEDs
VDJ_ONLY_CHANNEL = 1
# CHANNEL, PLUGIN, ARRANGER, MIXER, BROWSER, SAMPLING, FILE, SETTINGS: any view button turns VOLUME / SWING / TEMPO
# off, in Ableton and in VirtualDJ mode (the VirtualDJ mapping does the same with its own encoder mode)
VIEW_BUTTONS = tuple((0xB1, cc) for cc in range(34, 42))
VDJ_ONLY_NOTES = range(0, 4)
# PITCH, MOD, PERFORM: NOTES (note repeat rate selector on the group buttons) turns off when one of them is pressed
TOUCHSTRIP_MODE_BUTTONS = ((0xB1, 49), (0xB1, 50), (0xB1, 51))

class CustomTargetTrackComponent(TargetTrackComponent):
        
    def _target_clip_from_session(self):
        slot_index = scene_index()
        if slot_index < len(self._target_track.clip_slots):
            clip_slot = self._target_track.clip_slots[slot_index]
        else:
            clip_slot = None

        self._on_clip_slot_state_changed.subject = clip_slot
        if clip_slot:
            if clip_slot.has_clip:
                return clip_slot.clip
    
    @listens("has_clip")
    def _on_clip_slot_state_changed(self):
        self._update_target_clip()


class Specification(ControlSurfaceSpecification):
    elements_type = ControlElements
    control_surface_skin = MaschineSkin
    display_specification = MaschineDisplay if Config.LCD_ENABLED else None
    num_scenes = 4
    num_tracks = 4
    include_returns = True
    include_master = True
    include_auto_arming = True
    target_track_component_type = CustomTargetTrackComponent
    continuous_parameter_sensitivity = 2.0
    quantized_parameter_sensitivity = 0.2
    identity_response_id_bytes = [0x00, 0x00, 0x00]
    create_mappings_function = create_mappings
    recording_method_type = FixedLengthRecordingMethod
    feedback_channels = [DEFAULT_NOTE_TRANSLATION_CHANNEL, DEFAULT_SIMPLER_TRANSLATION_CHANNEL, DEFAULT_DRUM_TRANSLATION_CHANNEL]
    component_map = {
        "Pageable_Background": PageableBackgroundComponent,
        "Settings": SettingsComponent,
        "Transport": CustomTransportComponent,
        "Session": partial(SessionComponent, clip_slot_component_type = CustomClipSlotComponent),
        "Encoder_Mode_Control": EncoderModeControlComponent,
        "Group_Button_Mode_Control": GroupButtonModeControlComponent,
        "View_Based_Recording": partial(CustomViewBasedRecordingComponent, recording_method_type = recording_method_type),
        "Browser": BrowserComponent,
        "Clip_Editor": ClipEditorComponent,
        "Selected_Parameter": SelectedParameterControlComponent,
        "Scale_System": ScaleSystemComponent,
        "Velocity_Levels": VelocityLevelsComponent,
        "Note_Repeat": NoteRepeatComponent,
        "Sliced_Simpler": CustomSlicedSimplerComponent,
        "Drum_Group": CustomDrumGroupComponent,
        "Clip_Actions": CustomClipActionsComponent,
        "Groove_Pool": GroovePoolComponent,
        "Master_Volume": MasterVolumeComponent,
        "Cue_Volume": CueVolumeComponent,
        "Maschine_Playable": MaschinePlayableComponent,
        "Misc_Control": MiscControlComponent,
        # Does nothing: the pad mode used while the pads are locked to VirtualDJ
        "Pad_Lock": Component,
        "Device_Navigation": CustomDeviceNavigationComponent,
        "Session_Volume": SessionVolumeComponent,
    }
    parameter_bank_definitions = CUSTOM_BANK_DEFINITIONS

class BypassIdentification(IdentificationComponent):
    def request_identity(self):
        logger.info("Request identity")
        self.is_identified = False
        sleep(0.01)
        self.is_identified = True

DEFAULT_MODE = "default"
KEYBOARD_MODE = "keyboard"
DRUMRACK_MODE = "drum_rack"
SIMPLER_MODE = "simpler"

CUSTOM_GRID_RESOLUTIONS = (
    GridResolution("1/4", 1.0, GridQuantization.g_quarter, False),
    GridResolution("1/4t", 0.6666666666666666, GridQuantization.g_quarter, True),
    GridResolution("1/8", 0.5, GridQuantization.g_eighth, False),
    GridResolution("1/8t", 0.3333333333333333, GridQuantization.g_eighth, True),
    GridResolution("1/16", 0.25, GridQuantization.g_sixteenth, False),
#    GridResolution("1/16t", 0.16666666666666666, GridQuantization.g_sixteenth, True),
#    GridResolution("1/32", 0.125, GridQuantization.g_thirtysecond, False),
#    GridResolution("1/32t", 0.08333333333333333, GridQuantization.g_thirtysecond, True),
)
GRID_DEFAULT_INDEX = 4

class CustomMaschineMK3(ControlSurface):
    _grid_resolution = None
    _sequencer_clip = None
    _pad_mode = None
    _step_sequencer = None
    _playable_mode_list = (KEYBOARD_MODE, DRUMRACK_MODE, SIMPLER_MODE)
    _provider_list = {
        KEYBOARD_MODE: "Maschine_Playable",
        DRUMRACK_MODE: "Drum_Group",
        SIMPLER_MODE: "Sliced_Simpler"
    }
    _current_drum_group = None
    _current_sliced_simpler = None
    _display_mode = None
    _settings = None
    _vdj_mode = False
    _standby = Config.START_IN_STANDBY
    _shift_down = False
    _pad_lock = False
    _swallow_lock_release = False
    _pad_mode_before_lock = None
    _screen_bridge = None
    _screen_bridge_lines = None
    _screen_bridge_ticks = 0
    _screen_bridge_timer = None
    _screen_bridge_last_tick = 0.0
    _screen_bridge_timer_ok = False
    _screen_bridge_timer_repeats = False
    _screen_bridge_stall_logged = False
    _zeroed_parameters = None
    _restart_held = False
    _restart_used = False
    _erase_touch = (None, 0.0)  # (knob index, time) of the last ERASE + knob touch
    _browser_bridge_key = None  # browser folder whose items are cached for the screens
    _browser_bridge_items = ()
    _browser_bridge_parent = None
    _session_block_start = 0  # first track of the session grid on the screens
    _ring_offsets_seen = None  # (track, scene) offsets of the session ring at the last tick
    _screen_bridge_error_logged = False

    def __init__(self, *a, **k):
        # Settings must be loaded before initialization
        self._settings = SettingsRepository()
        # The display is drawn during initialization, so the bridge must exist before it
        self._init_screen_bridge()
        self._init_specification()
        super().__init__(Specification, *a, **k)
        #logger.info(dir(self._c_instance))

        #self.register_slot(self.elements.variation, self._on_update_triggered, "is_pressed")
        self.register_slot(self.elements.keyboard, self._on_playable_mode_selected, "is_pressed")
        self.register_slot(self.component_map["Pad_Modes"], self._on_pad_mode_changed, "selected_mode")
        self.register_slot(self.component_map["Display_Modes"], self._on_display_mode_changed, "selected_mode")
    
    def _init_specification(self):
        Specification.component_map["Device"] = partial(
            CustomDeviceComponent,
            device_decorator_factory = CustomDeviceDecoratorFactory(),
            bank_definitions = Specification.parameter_bank_definitions,
            bank_size = Specification.parameter_bank_size,
            continuous_parameter_sensitivity = Specification.continuous_parameter_sensitivity,
            quantized_parameter_sensitivity = Specification.quantized_parameter_sensitivity)

        pad_row_notes = list(range(60, 76, 4))
        if self._settings.get_value("sequencer_style") == "Push":
            pad_row_notes = pad_row_notes[::-1]
        playhead_notes = [base_note + offset for base_note, offset in product(pad_row_notes, range(4))]
        triplet_playhead_notes = [base_note + offset for base_note, offset in product(pad_row_notes, range(3))]

        Specification.component_map["Step_Sequence"] = partial(
            CustomStepSequenceComponent,
            note_editor_component_type = CustomNoteEditorComponent,
            playhead_notes = tuple(playhead_notes),
            playhead_triplet_notes = tuple(triplet_playhead_notes),
            playhead_channels = [1])
        
        mixer_mode = self._settings.get_value("mixer_mode")
        if mixer_mode == "4Track":
            mixer_component = CustomMixerComponent
        elif mixer_mode == "8Track":
            mixer_component = MaschineMixerComponent

        Specification.component_map["Mixer"] = mixer_component

    # Sometimes pad leds couldn't update correctly
    # I don't know why this happens now, push "CHANNEL" button for refresh state
    def _on_update_triggered(self):
        if self.elements.variation.is_pressed:
            logger.info("Display update triggered")
            self.refresh_state()

    def _do_send_midi(self, midi_event_bytes):
        # Standby: nothing reaches the Maschine's LEDs or display (_blank_hardware writes its own zeros)
        if self._standby:
            return True
        # FOLLOW's LED shows Ableton Link (sent by _update_link_led only)
        if tuple(midi_event_bytes[:2]) == LINK_BUTTON:
            return True
        # VirtualDJ owns LEDs and display while VirtualDJ mode is active, except Ableton's own transport buttons
        if self._vdj_mode and tuple(midi_event_bytes[:2]) not in ABLETON_ALWAYS_BUTTONS:
            return True
        if self._is_vdj_only(midi_event_bytes):
            return True
        # Pads locked to VirtualDJ keep VirtualDJ's colors, page button LEDs and the lit LOCK button
        if self._pad_lock and self._is_pad_section(midi_event_bytes, include_lock = True):
            return True
        logger.debug(f"_do_send_midi {midi_event_bytes}")
        super()._do_send_midi(midi_event_bytes)
        self._copy_to_screen_bridge(midi_event_bytes)
        # Insert super short wait between each send to make sure LED feedback correctly.
        # During development, I encountered problem some pads / buttons LEDs not change to current mode value.
        # After several investigations, I found a wait inserted on old Maschine Ableton script.
        # Maybe 500us or more wait prevent issue.
        # This wait doesn't affect response speed, unless if you can play pads at 999 BPM...
        sleep(0.0005)

    # Live may deliver incoming MIDI one message at a time or in chunks, so filter both entry points
    def receive_midi(self, midi_bytes):
        if self._accept_midi(midi_bytes):
            super().receive_midi(midi_bytes)

    def receive_midi_chunk(self, midi_chunk):
        accepted = tuple(midi_bytes for midi_bytes in midi_chunk if self._accept_midi(midi_bytes))
        if accepted:
            super().receive_midi_chunk(accepted)

    def _accept_midi(self, midi_bytes):
        midi_bytes = tuple(midi_bytes)
        if self._is_vdj_only(midi_bytes):
            return False
        is_cc = len(midi_bytes) == 3
        # SHIFT's state, tracked here as well: SHIFT + CHANNEL must not depend on the framework having seen it
        if midi_bytes[:4] == SHIFT_SYSEX_PREFIX and len(midi_bytes) > 12:
            self._shift_down = midi_bytes[-2] > 0
        elif is_cc and midi_bytes[:2] == SHIFT_BUTTON:
            self._shift_down = midi_bytes[2] > 0
        if is_cc and midi_bytes[:2] == STANDBY_BUTTON and midi_bytes[2] > 0:
            self._c_instance.log_message(
                f"CustomMaschineMK3: CHANNEL pressed (shift = {self._shift_down or self.elements.shift.is_pressed}, "
                f"standby = {self._standby})")
        if self._standby:
            # Everything is ignored, except SHIFT's state and the buttons that wake the Maschine
            if midi_bytes[:4] == SHIFT_SYSEX_PREFIX:
                return True
            if is_cc and midi_bytes[2] > 0:
                key = midi_bytes[:2]
                if key == VDJ_ENTER_BUTTON:
                    self._set_standby(False)
                    self._set_vdj_mode(True)
                elif key in STANDBY_WAKE_BUTTONS:
                    self._set_standby(False)
                    return key != STANDBY_BUTTON  # MIXER / PLUGIN also go on to select their view
            return False
        if (is_cc and midi_bytes[:2] == STANDBY_BUTTON and midi_bytes[2] > 0
                and (self._shift_down or self.elements.shift.is_pressed)):
            self._set_standby(True)
            return False
        # "SAMPLING" never reaches Ableton, it's reserved for entering VirtualDJ mode
        if is_cc and midi_bytes[:2] == VDJ_ENTER_BUTTON:
            if midi_bytes[2] > 0:
                # A view button too: VOLUME / SWING / TEMPO off
                with self.component_guard():
                    self.component_map["Encoder_Mode_Control"].reset_selected_mode()
                if not self._vdj_mode:
                    self._set_vdj_mode(True)
            return False

        if is_cc and midi_bytes[:2] == LINK_BUTTON and not self._vdj_mode:
            if midi_bytes[2] > 0:
                self.song.is_ableton_link_enabled = not self.song.is_ableton_link_enabled
                self._c_instance.log_message(f"CustomMaschineMK3: Ableton Link = {self.song.is_ableton_link_enabled}")
                self._update_link_led()
            return False

        if is_cc and midi_bytes[:2] == PAD_LOCK_BUTTON:
            if midi_bytes[2] > 0:
                if self._vdj_mode:
                    self._pad_lock = not self._pad_lock
                    self._c_instance.log_message(f"CustomMaschineMK3: pad lock = {self._pad_lock}")
                    return False
                if self._pad_lock:
                    # In Ableton, LOCK only releases the pads; the press (and its release) never reach Ableton
                    self._set_pad_lock(False)
                    self._swallow_lock_release = True
                    return False
            elif self._swallow_lock_release:
                self._swallow_lock_release = False
                return False

        # RESTART is also a modifier: its loop on / off happens on release, only if no knob was touched meanwhile
        if is_cc and midi_bytes[:2] == RESTART_BUTTON and not self._vdj_mode:
            if midi_bytes[2] > 0:
                self._restart_held, self._restart_used = True, False
            else:
                if self._restart_held and not self._restart_used:
                    self.song.loop = not self.song.loop
                self._restart_held = False
            return False

        if is_cc and midi_bytes[:2] == STEP_BUTTON and midi_bytes[2] > 0 and self._restart_held and not self._vdj_mode:
            self._restart_used = True  # so letting go of RESTART doesn't toggle the loop
            self._reset_all_volumes()
            return False  # STEP's own function (the pad page) is not used with RESTART

        if is_cc and midi_bytes[:2] in KNOB_TOUCH_CCS and midi_bytes[2] > 0 and not self._vdj_mode:
            index = KNOB_TOUCH_CCS.index(midi_bytes[:2])
            volume_view = self.component_map["Display_Modes"].selected_mode in (MIXER_DISPLAY_MODE, SESSION_DISPLAY_MODE)
            if self._restart_held:
                # RESTART + knob: default value (device parameter's default, mixer volume to 0 dB...)
                self._restart_used = True
                self._set_knob_parameter(index, default = True)
            elif self.elements.erase.is_pressed and volume_view:
                # ERASE + double touch on a knob in the mixer / session view: to zero (volume to -inf, pan to
                # center). Double, so it can't happen by accident
                now = perf_counter()
                last_index, last_time = self._erase_touch
                if last_index == index and now - last_time <= ERASE_DOUBLE_TOUCH_SECONDS:
                    self._set_knob_parameter(index, default = False)
                    self._erase_touch = (None, 0.0)
                else:
                    self._erase_touch = (index, now)
            elif self.elements.mute.is_pressed and volume_view:
                self._toggle_knob_parameter_zero(index)

        if (is_cc and not self._vdj_mode and self._session_view
                and (midi_bytes[:2] in (SESSION_NAV_TURN, SESSION_NAV_PUSH) or midi_bytes[:2] in SESSION_NAV_TILTS)
                and self.component_map["Encoder_Modes"].selected_mode == ENCODER_DEFAULT_MODE):
            self._handle_session_navigation(midi_bytes)
            return False

        if is_cc and midi_bytes[:2] == DELETE_CLIP_BUTTON and not self._vdj_mode:
            if midi_bytes[2] > 0:
                self._delete_target_clip()
            return False

        if is_cc and (midi_bytes[:2] in VIEW_BUTTONS or midi_bytes[:2] in PAD_PAGE_BUTTONS) and midi_bytes[2] > 0:
            # Also when the view doesn't change (e.g. MIXER while already in the mixer); the pad pages
            # (KEYBOARD, PAD MODE, CHORDS, STEP) too, like in the VirtualDJ mapping
            with self.component_guard():
                self.component_map["Encoder_Mode_Control"].reset_selected_mode()

        # ARRANGER enters the session view; the other view buttons leave it (they select their own display mode)
        if is_cc and midi_bytes[:2] == SESSION_VIEW_BUTTON and not self._vdj_mode:
            if midi_bytes[2] > 0:
                self._show_session_view()
            return False

        if is_cc and midi_bytes[:2] in TOUCHSTRIP_MODE_BUTTONS and midi_bytes[2] > 0 and not self._vdj_mode:
            notes = self.component_map["Group_Button_Mode_Control"]
            if notes.get_note_repeat_selector_state():
                with self.component_guard():
                    notes.set_note_repeat_selector_state(False)

        if self._vdj_mode:
            if is_cc and midi_bytes[:2] in VDJ_EXIT_BUTTONS and midi_bytes[2] > 0:
                # Leave VirtualDJ mode and let the press through, so it selects mixer / device mode as usual
                self._set_vdj_mode(False)
                return True
            # PLAY / STOP (and SHIFT, for SHIFT + STOP) keep driving Ableton's transport
            if midi_bytes[:4] == SHIFT_SYSEX_PREFIX:
                return True
            return is_cc and (midi_bytes[:2] in ABLETON_ALWAYS_BUTTONS or midi_bytes[:2] in SHARED_ENCODER_MODE_BUTTONS)

        if self._pad_lock and self._is_pad_section(midi_bytes):
            return False

        return True

    @staticmethod
    def _is_vdj_only(midi_bytes):
        # Note on / off / poly pressure of the VirtualDJ-only buttons
        midi_bytes = tuple(midi_bytes)
        return (len(midi_bytes) == 3 and midi_bytes[0] & 0xF0 in (0x80, 0x90, 0xA0)
                and midi_bytes[0] & 0x0F == VDJ_ONLY_CHANNEL and midi_bytes[1] in VDJ_ONLY_NOTES)

    @staticmethod
    def _is_pad_section(midi_bytes, include_lock = False):
        # The 16 pads (note on / off / poly pressure on any channel) and the pad page buttons
        midi_bytes = tuple(midi_bytes)
        if len(midi_bytes) != 3:
            return False
        if midi_bytes[0] & 0xF0 in (0x80, 0x90, 0xA0) and midi_bytes[1] in PAD_NOTES:
            return True
        return midi_bytes[:2] in PAD_PAGE_BUTTONS or (include_lock and midi_bytes[:2] == PAD_LOCK_BUTTON)

    def build_midi_map(self, midi_map_handle):
        script_handle = self._c_instance.handle()
        if not (self._vdj_mode or self._standby):
            super().build_midi_map(midi_map_handle)
            if self._pad_lock:
                # Pads locked to VirtualDJ: forward their notes and page buttons to the script so receive_midi
                # drops them, instead of Live playing the notes on an armed track
                for note in PAD_NOTES:
                    Live.MidiMap.forward_midi_note(script_handle, midi_map_handle, 0, note)
                for _, cc in PAD_PAGE_BUTTONS:
                    Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, 1, cc)
            return

        # Knobs and touch strip are normally mapped by Live directly to parameters, bypassing receive_midi.
        # In VirtualDJ mode, forward every message on Maschine's channels to the script instead,
        # so receive_midi can drop them and nothing reaches Live (not even armed tracks).
        for channel in (0, 1):
            Live.MidiMap.forward_midi_pitchbend(script_handle, midi_map_handle, channel)
            for identifier in range(128):
                Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, channel, identifier)
                Live.MidiMap.forward_midi_note(script_handle, midi_map_handle, channel, identifier)

    def _set_standby(self, enabled):
        if enabled == self._standby:
            return
        self._c_instance.log_message(f"CustomMaschineMK3: standby = {enabled}")
        if enabled:
            # VirtualDJ's mapping also leaves its mode with SHIFT + CHANNEL
            self._vdj_mode = False
            self._pad_lock = False
            self._sync_pad_lock_mode()
            self._standby = True
            self.request_rebuild_midi_map()
            self._blank_hardware()
        else:
            self._standby = False
            self.request_rebuild_midi_map()
            self._redisplay()
            self.schedule_message(VDJ_REFRESH_DELAY, self._refresh_after_vdj_mode)

    def _blank_hardware(self):
        # Pads, buttons, the touch strip and the display lines off (written past the standby filter)
        for note in PAD_NOTES:
            self._send_blank((0x90, note, 0))
        for note in STANDBY_LED_NOTES:
            self._send_blank((0x91, note, 0))
        for cc in STANDBY_LED_CCS:
            self._send_blank((0xB1, cc, 0))
        self._send_blank((0xE0, 0x00, 0x00))
        for line in range(4):
            self._send_blank(make_display_sysex_message(line, (ord(" "),) * 28))

    def _send_blank(self, midi_event_bytes):
        try:
            super()._do_send_midi(midi_event_bytes)
            sleep(0.0005)
        except Exception as error:
            logger.debug(f"blank failed: {error!r}")

    def _set_vdj_mode(self, enabled):
        # Always written to Live's Log.txt, regardless of Config.LOGGING
        self._c_instance.log_message(f"CustomMaschineMK3: VirtualDJ mode = {enabled}")
        self._vdj_mode = enabled
        self._sync_pad_lock_mode()
        self.request_rebuild_midi_map()
        if not enabled:
            self._redisplay()
            self.schedule_message(VDJ_REFRESH_DELAY, self._refresh_after_vdj_mode)

    def _set_pad_lock(self, enabled):
        self._c_instance.log_message(f"CustomMaschineMK3: pad lock = {enabled}")
        self._pad_lock = enabled
        self._sync_pad_lock_mode()
        self.request_rebuild_midi_map()
        if not enabled:
            # Pads are Ableton's again: redraw their LEDs
            self.schedule_message(VDJ_REFRESH_DELAY, self._refresh_after_vdj_mode)

    def _sync_pad_lock_mode(self):
        # While the pads are locked to VirtualDJ in Ableton, no pad mode (session, keyboard, chords, step...) uses them
        pad_modes = self.component_map["Pad_Modes"]
        locked = self._pad_lock and not self._vdj_mode
        with self.component_guard():
            if locked and pad_modes.selected_mode != PAD_LOCK_MODE:
                self._pad_mode_before_lock = pad_modes.selected_mode
                pad_modes.selected_mode = PAD_LOCK_MODE
            elif not locked and pad_modes.selected_mode == PAD_LOCK_MODE:
                pad_modes.selected_mode = self._pad_mode_before_lock or DEFAULT_MODE

    def _update_link_led(self):
        if self._vdj_mode or self._standby:
            return
        value = 127 if self.song.is_ableton_link_enabled else 0
        super()._do_send_midi((LINK_BUTTON[0], LINK_BUTTON[1], value))

    def _handle_session_navigation(self, midi_bytes):
        key, value = midi_bytes[:2], midi_bytes[2]
        if key == SESSION_NAV_PUSH:
            if value > 0:
                slot = self.song.view.highlighted_clip_slot
                if liveobj_valid(slot):
                    slot.fire()
            return
        if key == SESSION_NAV_TURN:
            step = value if value < 64 else value - 128  # two's complement
            if step == 0:
                return
            delta = (1 if step > 0 else -1, 0)  # turning moves sideways, between tracks
        else:
            if value == 0:  # tilt released
                return
            delta = SESSION_NAV_TILTS[key]
        with self.component_guard():
            if self.elements.shift.is_pressed:
                self._move_session_ring(*delta)
            else:
                self._move_session_selection(*delta)

    def _session_tracks_and_scenes(self):
        ring = self._session_ring
        tracks_to_use = getattr(ring, "tracks_to_use", None)
        tracks = list(tracks_to_use()) if callable(tracks_to_use) else list(self.song.visible_tracks)
        return ring, tracks, list(self.song.scenes)

    def _session_block(self, ring):
        # First track of the SESSION_GRID_TRACKS-track block shown on the screens. It moves in steps of
        # SESSION_GRID_STEP, only when the pads (the session ring) or the selected slot leave it
        start = self._session_block_start
        first, last = ring.track_offset, ring.track_offset + ring.num_tracks
        while first < start:
            start -= SESSION_GRID_STEP
        while last > start + SESSION_GRID_TRACKS:
            start += SESSION_GRID_STEP
        self._session_block_start = max(0, start)
        return self._session_block_start

    def _move_session_selection(self, track_delta, scene_delta, follow = True):
        # Moves Live's selected clip slot. Leaving the pads moves them SESSION_GRID_STEP tracks sideways (and
        # the grid on the screens, when the pads leave it) or one scene up / down. follow = False keeps the
        # selection inside the grid instead (after SHIFT moved the grid itself)
        ring, tracks, scenes = self._session_tracks_and_scenes()
        if not tracks or not scenes:
            return
        view = self.song.view
        start = self._session_block(ring)
        scene_offset = ring.scene_offset
        track_index = tracks.index(view.selected_track) if view.selected_track in tracks else start
        scene_index = scenes.index(view.selected_scene) if view.selected_scene in scenes else scene_offset
        track_index = min(max(track_index + track_delta, 0), len(tracks) - 1)
        scene_index = min(max(scene_index + scene_delta, 0), len(scenes) - 1)
        if follow:
            # The pads (the session ring) follow the selected slot, SESSION_GRID_STEP tracks at a time
            # (e.g. moving onto the right screen moves them there); the block on the screens follows the pads
            track_offset = ring.track_offset
            while track_index < track_offset:
                track_offset -= SESSION_GRID_STEP
            while track_index >= track_offset + ring.num_tracks:
                track_offset += SESSION_GRID_STEP
            track_offset = min(max(track_offset, 0), max(len(tracks) - 1, 0))
            if scene_index < scene_offset:
                scene_offset = scene_index
            elif scene_index >= scene_offset + SESSION_GRID_SCENES:
                scene_offset = scene_index - SESSION_GRID_SCENES + 1
            if track_offset != ring.track_offset or scene_offset != ring.scene_offset:
                ring.set_offsets(track_offset, scene_offset)
                self._ring_offsets_seen = (ring.track_offset, ring.scene_offset)
                self._session_block(ring)
        else:
            track_index = min(max(track_index, start), min(start + SESSION_GRID_TRACKS, len(tracks)) - 1)
            scene_index = min(max(scene_index, scene_offset),
                              min(scene_offset + SESSION_GRID_SCENES, len(scenes)) - 1)
        if view.selected_track != tracks[track_index]:
            view.selected_track = tracks[track_index]
        if view.selected_scene != scenes[scene_index]:
            view.selected_scene = scenes[scene_index]

    def _move_session_ring(self, track_delta, scene_delta):
        ring, tracks, scenes = self._session_tracks_and_scenes()
        track_offset = min(max(ring.track_offset + track_delta, 0), max(len(tracks) - 1, 0))
        scene_offset = min(max(ring.scene_offset + scene_delta, 0), max(len(scenes) - 1, 0))
        ring.set_offsets(track_offset, scene_offset)
        self._ring_offsets_seen = (ring.track_offset, ring.scene_offset)
        # The selected clip slot stays visible
        self._move_session_selection(0, 0, follow = False)

    def _delete_target_clip(self):
        target = self.component_map["Target_Track"]
        track = target.target_track
        if not liveobj_valid(track) or not hasattr(track, "clip_slots"):
            return
        slot = None
        # playing_slot_index also covers the slot that is recording
        if track.playing_slot_index >= 0:
            slot = track.clip_slots[track.playing_slot_index]
        else:
            clip = target.target_clip
            if liveobj_valid(clip):
                slot = clip.canonical_parent
        if slot is None or not slot.has_clip:
            self._c_instance.show_message(f"No clip to delete on {track.name}")
            return
        name = slot.clip.name
        slot.delete_clip()
        self._c_instance.show_message(f"Clip deleted: {name} ({track.name}) - Ctrl+Z to undo")
        self._c_instance.log_message(f"CustomMaschineMK3: deleted clip '{name}' on '{track.name}'")

    @property
    def _session_view(self):
        return self.component_map["Display_Modes"].selected_mode == SESSION_DISPLAY_MODE

    def _show_session_view(self):
        with self.component_guard():
            self.component_map["Display_Modes"].selected_mode = SESSION_DISPLAY_MODE
        self.application.view.show_view("Session")

    def _update_session_view_led(self):
        # Through _do_send_midi: in VirtualDJ mode the LEDs belong to VirtualDJ
        self._do_send_midi((SESSION_VIEW_BUTTON[0], SESSION_VIEW_BUTTON[1], 127 if self._session_view else 0))

    def _carry_selection_with_ring(self):
        # In the browser and session views the grid on the screens is the pads' grid: when something else moves the
        # session ring (A-H in the session pad mode jump between grids), the selected clip slot goes along, to the
        # same place of the new grid, instead of the grid snapping back to the selection
        ring = getattr(self, "_session_ring", None)
        if ring is None or self._standby:
            return
        offsets = (ring.track_offset, ring.scene_offset)
        last, self._ring_offsets_seen = self._ring_offsets_seen, offsets
        if last is None or offsets == last:
            return
        if self.component_map["Display_Modes"].selected_mode not in (BROWSER_DISPLAY_MODE, SESSION_DISPLAY_MODE):
            return
        _, tracks, scenes = self._session_tracks_and_scenes()
        view = self.song.view
        if not tracks or not scenes or view.selected_track not in tracks or view.selected_scene not in scenes:
            return
        track_index = min(max(tracks.index(view.selected_track) + offsets[0] - last[0], 0), len(tracks) - 1)
        scene_index = min(max(scenes.index(view.selected_scene) + offsets[1] - last[1], 0), len(scenes) - 1)
        view.selected_track = tracks[track_index]
        view.selected_scene = scenes[scene_index]

    def _screen_bridge_session(self):
        # Clip grid for the session pad mode: SESSION_GRID_TRACKS tracks x SESSION_GRID_SCENES scenes from the
        # session ring's position (its first num_tracks columns are the ones on the pads)
        ring = getattr(self, "_session_ring", None)
        if ring is None:
            return None
        # The knobs follow the 8-track block when the ring moves
        session_volume = self.component_map["Session_Volume"]
        session_volume.block_start = self._session_block(ring)
        session_volume.refresh()
        tracks_to_use = getattr(ring, "tracks_to_use", None)
        tracks = list(tracks_to_use()) if callable(tracks_to_use) else list(self.song.visible_tracks)
        scenes = list(self.song.scenes)
        track_offset, scene_offset = ring.track_offset, ring.scene_offset
        # The screens show a block of SESSION_GRID_TRACKS tracks: moving the ring inside it only moves the
        # highlighted columns (the ones on the pads); leaving it moves the block SESSION_GRID_STEP tracks
        page_offset = self._session_block(ring)
        columns = self._grid_columns(tracks, page_offset, SESSION_GRID_TRACKS, scene_offset, SESSION_GRID_SCENES)
        return {
            "track_offset": track_offset,
            "page_offset": page_offset,
            "ring_column": track_offset - page_offset,
            "scene_offset": scene_offset,
            "ring_tracks": ring.num_tracks,
            # What the knobs control in the session view: "volume" (left arrow) or "fx" (right arrow)
            "knob_page": self.component_map["Session_Volume"].page,
            "scenes": [scenes[index].name if index < len(scenes) else "" for index in
                       range(scene_offset, scene_offset + SESSION_GRID_SCENES)],
            "tracks": columns,
        }

    def _grid_columns(self, tracks, track_start, track_count, scene_start, scene_count):
        # Clip slots of a block of tracks x scenes, for the screens
        # The clip slot selected in Live (selected track x selected scene), marked on the screens
        highlighted = self.song.view.highlighted_clip_slot
        # The selected or locked track (the one the pads play), drawn in white on the screens
        target = self.component_map["Target_Track"].target_track
        columns = []
        for track_index in range(track_start, track_start + track_count):
            if track_index >= len(tracks):
                columns.append(None)
                continue
            track = tracks[track_index]
            slots = []
            for scene_index in range(scene_start, scene_start + scene_count):
                if scene_index >= len(track.clip_slots):
                    slots.append(None)
                    continue
                slot = track.clip_slots[scene_index]
                if slot.has_clip:
                    clip = slot.clip
                    info = {"name": clip.name, "color": clip.color, "playing": clip.is_playing,
                            "triggered": clip.is_triggered, "recording": clip.is_recording}
                else:
                    info = {"empty": True, "stop": slot.has_stop_button, "triggered": slot.is_triggered}
                if liveobj_valid(highlighted) and slot == highlighted:
                    info["selected"] = True
                slots.append(info)
            columns.append({"name": track.name, "color": track.color, "slots": slots,
                            "target": liveobj_valid(target) and track == target})
        return columns

    def _screen_bridge_browser_grid(self):
        # Browser view: the session grid as it is (the pads' 4 tracks), to see where a loaded item will land.
        # If the selected slot leaves the pads, they move 4 tracks / 1 scene, like in the session view
        self._move_session_selection(0, 0)
        return self._screen_bridge_session()

    def _reset_all_volumes(self):
        # Every track and return back to its volume's default (0 dB); the master volume is left alone
        count = 0
        for track in list(self.song.tracks) + list(self.song.return_tracks):
            volume = track.mixer_device.volume
            volume.value = volume.default_value
            count += 1
        self._c_instance.show_message(f"Volumes reset to default ({count} tracks)")
        self._c_instance.log_message(f"CustomMaschineMK3: {count} volumes reset to default")

    def _set_knob_parameter(self, index, default):
        parameter = self._get_knob_mapped_parameter(index)
        if not liveobj_valid(parameter):
            return
        if default:
            value = getattr(parameter, "default_value", parameter.min)
        else:
            value = 0.0 if parameter.min < 0 < parameter.max else parameter.min
        parameter.value = min(max(value, parameter.min), parameter.max)

    def _toggle_knob_parameter_zero(self, index):
        parameter = self._get_knob_mapped_parameter(index)
        if not liveobj_valid(parameter) or parameter.is_quantized:
            return
        if self._zeroed_parameters is None:
            self._zeroed_parameters = []
        zero = 0.0 if parameter.min < 0 < parameter.max else parameter.min
        # Live objects aren't reliable dict keys, so the saved values are (parameter, value) pairs
        saved = next((pair for pair in self._zeroed_parameters if pair[0] == parameter), None)
        if saved is not None and parameter.value == zero:
            parameter.value = min(max(saved[1], parameter.min), parameter.max)
            self._zeroed_parameters.remove(saved)
        else:
            if saved is not None:
                self._zeroed_parameters.remove(saved)
            self._zeroed_parameters.append((parameter, parameter.value))
            parameter.value = zero

    def _init_screen_bridge(self):
        self._screen_bridge_lines = {}
        if Config.SCREEN_BRIDGE_PORT is None:
            return
        try:
            self._screen_bridge = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._screen_bridge.setblocking(False)
        except OSError as error:
            # Runs before the control surface exists, so it can't use Live's log yet
            logger.info(f"Screen bridge disabled: {error}")
            self._screen_bridge = None

    def _copy_to_screen_bridge(self, midi_event_bytes):
        if self._screen_bridge is None or tuple(midi_event_bytes[:6]) != MCU_DISPLAY_HEADER:
            return
        message = bytes(midi_event_bytes)
        self._screen_bridge_lines[midi_event_bytes[6]] = message
        self._send_to_screen_bridge(message)

    def _send_to_screen_bridge(self, message):
        try:
            self._screen_bridge.sendto(message, SCREEN_BRIDGE_ADDRESS)
        except OSError:
            # Nobody listening or the send buffer is full: the next resend catches up
            pass

    def _screen_bridge_timer_tick(self):
        # Fast timer (~30 per second). The ~100ms watchdog below covers for it if it stops firing
        try:
            if not self._screen_bridge_timer_ok:
                self._screen_bridge_timer_ok = True
                self._c_instance.log_message(f"CustomMaschineMK3: screen bridge timer running (repeat = {self._screen_bridge_timer_repeats})")
            self._screen_bridge_tick()
        finally:
            # A repeating timer re-arms itself; restart() from inside its own callback doesn't re-arm it in Live
            if self._screen_bridge_timer is not None and not self._screen_bridge_timer_repeats:
                self._screen_bridge_timer.restart()

    def _screen_bridge_watchdog(self):
        if self._screen_bridge is None:
            return
        try:
            if perf_counter() - self._screen_bridge_last_tick > SCREEN_BRIDGE_STALL_SECONDS:
                if not self._screen_bridge_stall_logged:
                    self._screen_bridge_stall_logged = True
                    self._c_instance.log_message("CustomMaschineMK3: screen bridge timer not firing, using ~100ms ticks")
                self._screen_bridge_tick()
                if self._screen_bridge_timer is not None:
                    self._screen_bridge_timer.restart()
        finally:
            self.schedule_message(1, self._screen_bridge_watchdog)

    def _screen_bridge_tick(self):
        if self._screen_bridge is None:
            return
        self._screen_bridge_last_tick = perf_counter()
        # In VirtualDJ mode the display belongs to VirtualDJ: the bridge only learns the mode, so it can
        # pick it up when it starts while VirtualDJ mode is on
        if self._vdj_mode:
            self._send_to_screen_bridge(b'{"type":"mode","vdj":true}')
        else:
            self._carry_selection_with_ring()
            self._send_screen_bridge_state()
            self._screen_bridge_ticks += 1
            if self._screen_bridge_ticks >= SCREEN_BRIDGE_RESEND_TICKS:
                self._screen_bridge_ticks = 0
                for message in self._screen_bridge_lines.values():
                    self._send_to_screen_bridge(message)

    def _start_screen_bridge(self):
        if self._screen_bridge is None:
            return
        try:
            try:
                self._screen_bridge_timer = Timer(callback = self._screen_bridge_timer_tick,
                                                  interval = SCREEN_BRIDGE_INTERVAL_MS, repeat = True, start = True)
                self._screen_bridge_timer_repeats = True
            except TypeError:
                # No repeat option: re-armed by restart() in the callback
                self._screen_bridge_timer = Timer(callback = self._screen_bridge_timer_tick,
                                                  interval = SCREEN_BRIDGE_INTERVAL_MS, start = True)
                self._screen_bridge_timer_repeats = False
        except Exception as error:
            self._c_instance.log_message(f"CustomMaschineMK3: screen bridge timer failed ({error!r}), using ~100ms ticks")
            self._screen_bridge_timer = None
        # Always running: sends the state itself whenever the fast timer isn't firing
        self.schedule_message(1, self._screen_bridge_watchdog)

    def _send_screen_bridge_state(self):
        try:
            state = self._screen_bridge_state()
        except Exception as error:
            # Never let the bridge break the controller: log once and keep the text-only display
            if not self._screen_bridge_error_logged:
                self._screen_bridge_error_logged = True
                self._c_instance.log_message(f"CustomMaschineMK3: screen bridge state failed ({error!r})")
            return
        self._send_to_screen_bridge(json.dumps(state, separators=(",", ":")).encode("utf-8"))

    def _screen_bridge_state(self):
        if self._standby:
            return {"type": "state", "standby": True}
        knobs = []
        for index in range(KNOB_COUNT):
            parameter = self._get_knob_mapped_parameter(index)
            if not liveobj_valid(parameter):
                knobs.append(None)
                continue
            span = parameter.max - parameter.min
            knob = {
                "name": parameter.name,
                "value": (parameter.value - parameter.min) / span if span else 0.0,
                "text": get_display_value(parameter),
                "bipolar": parameter.min < 0 < parameter.max,
            }
            owner = parameter_owner(parameter)
            if isinstance(owner, Live.Track.Track):
                knob["track"] = owner.name
                knob["color"] = owner.color
                if owner.has_audio_output:
                    knob["meter"] = max(owner.output_meter_left, owner.output_meter_right)
            knobs.append(knob)

        device = getattr(self.component_map["Device"], "device", None)
        if callable(device):
            device = device()
        target_track = self.component_map["Target_Track"].target_track
        view = self.component_map["Display_Modes"].selected_mode
        encoder_mode = self.component_map["Encoder_Modes"].selected_mode
        return {
            "encoder": self._screen_bridge_encoder(encoder_mode),
            "browser": self._screen_bridge_browser() if view == BROWSER_DISPLAY_MODE else None,
            "browser_grid": self._screen_bridge_browser_grid() if view == BROWSER_DISPLAY_MODE else None,
            "session_view": self._session_view,
            "session": self._screen_bridge_session() if self._session_view else None,
            "type": "state",
            "view": view,
            "encoder_mode": encoder_mode,
            "mixer_parameter": getattr(self.component_map["Mixer"], "parameter_name", None),
            "device": liveobj_name(device) if liveobj_valid(device) else None,
            "device_color": self._device_color(device),
            "track": liveobj_name(target_track) if liveobj_valid(target_track) else None,
            "track_color": target_track.color if liveobj_valid(target_track) else None,
            "locked": self.component_map["Target_Track"].is_locked_to_track,
            "touched": TOUCH_STATES.active_index,
            "knobs": knobs,
        }

    @staticmethod
    def _device_color(device):
        # Live has no color per device (as of 12.4): a device inside a rack takes its chain's color,
        # one on the track takes the track's
        if not liveobj_valid(device):
            return None
        color = getattr(device, "color", None)
        if color is not None:
            return color
        # canonical_parent: the rack chain (or drum pad chain) holding it, or the track itself
        parent = getattr(device, "canonical_parent", None)
        return getattr(parent, "color", None)

    def _screen_bridge_encoder(self, encoder_mode):
        # VOLUME = master volume, SWING = headphones (cue) volume: drawn like VirtualDJ's VOLUME / SWING.
        # TEMPO the same way: the bar spans TEMPO_SCREEN_RANGE, the text is the exact tempo
        master = self.song.master_track
        if encoder_mode == "tempo":
            low, high = TEMPO_SCREEN_RANGE
            tempo = self.song.tempo
            return {
                "mode": encoder_mode,
                "value": min(max((tempo - low) / (high - low), 0.0), 1.0),
                "text": f"{tempo:.2f} BPM",
                "meter": None,
            }
        if encoder_mode == "volume":
            parameter = master.mixer_device.volume
        elif encoder_mode == "swing":
            parameter = master.mixer_device.cue_volume
        else:
            return None
        span = parameter.max - parameter.min
        return {
            "mode": encoder_mode,
            "value": (parameter.value - parameter.min) / span if span else 0.0,
            "text": parameter.str_for_value(parameter.value),
            "meter": max(master.output_meter_left, master.output_meter_right) if encoder_mode == "volume" else None,
        }

    def _browser_level(self, folder):
        # Names of a browser folder's children, read once per folder: .children is slow on big folders
        items = []
        for item in folder.children:
            items.append({"name": item.name, "uri": getattr(item, "uri", None),
                          "folder": bool(item.is_folder or not item.is_loadable)})
        return items

    def _screen_bridge_browser(self):
        # The Browser component's own tree (encoder, push = load / enter, left / right = leave / enter folder)
        browser = self.component_map["Browser"]
        explorer = getattr(browser, "_explorer", None)
        if explorer is None:
            return None
        stack = explorer._tree_stack
        key = tuple(getattr(item, "uri", None) or item.name for item in stack)
        if key != self._browser_bridge_key:
            self._browser_bridge_key = key
            self._browser_bridge_items = self._browser_level(stack[-1])
            parent = None
            if len(stack) > 1:
                parent_items = self._browser_level(stack[-2])
                current = key[-1]
                index = next((i for i, item in enumerate(parent_items)
                              if (item["uri"] or item["name"]) == current), 0)
                parent = {"name": stack[-2].name, "items": parent_items, "selected": index}
            self._browser_bridge_parent = parent

        def window(items, selected):
            first = max(0, selected - BROWSER_BRIDGE_ITEMS)
            return {"first": first, "selected": selected, "count": len(items),
                    "items": [{"name": item["name"], "folder": item["folder"]}
                              for item in items[first:selected + BROWSER_BRIDGE_ITEMS + 1]]}

        parent = self._browser_bridge_parent
        return {
            "path": [item.name for item in stack[1:]],
            "folder": stack[-1].name,
            "list": window(self._browser_bridge_items, explorer.selected_item_index),
            "parent": dict(window(parent["items"], parent["selected"]), name=parent["name"]) if parent else None,
            "preview": browser.preview_enabled,
        }

    def _redisplay(self):
        # Clearing the send cache makes each display line re-send its last content right away (only 4 sysex messages)
        for line in range(4):
            display_line = getattr(self.elements, f"display_line_{line}", None)
            if display_line is not None:
                display_line.clear_send_cache()

    def _refresh_after_vdj_mode(self):
        if not self._vdj_mode:
            with self.component_guard():
                self.refresh_state()
            self._update_link_led()
            self._update_session_view_led()

    # Session ring highlight is enabled only if hardware is identified by identity request
    # But maschine didn't respond to this message, so bypass identification process
    def _create_identification(self, specification):
        #return super()._create_identification(specification)
        identification = BypassIdentification(
            identity_request = specification.identity_request,
            identity_request_delay = specification.identity_request_delay,
            identity_response_id_bytes = specification.identity_response_id_bytes,
            custom_identity_response = specification.custom_identity_response)
        self._ControlSurface__on_is_identified_changed.subject = identification

        return identification

    @lazy_attribute
    def _create_grid_resolution(self):
        self._grid_resolution = GridResolutionComponent(resolutions = CUSTOM_GRID_RESOLUTIONS, default_index = GRID_DEFAULT_INDEX)
        self._grid_resolution.resolution_buttons.control_count = len(CUSTOM_GRID_RESOLUTIONS)
        return self._grid_resolution

    @lazy_attribute
    def _create_sequencer_clip(self):
        self._sequencer_clip = SequencerClip()
        return self._sequencer_clip
        
    @lazy_attribute
    def _create_blinker(self):
        self._blinker = LEDBlinker()
        return self._blinker
    
    def _get_knob_mapped_parameter(self, index):
        if index >= 0 and index < len(self.elements.knobs_raw):
            return self.elements.knobs_raw[index].mapped_parameter()

    def _get_additional_dependencies(self):
        # Register objects to DI container
        # Dict key name came from @depends decorator of each component classes
        # Registered components pass to appropriate components on demand
        inject_dict = {
            "grid_resolution": lambda: self._create_grid_resolution,
            "sequencer_clip": lambda: self._create_sequencer_clip,
            "note_repeat": const(self._c_instance.note_repeat),
            "velocity_levels": const(self._c_instance.velocity_levels),
            "get_knob_mapped_parameter": const(self._get_knob_mapped_parameter),
            "settings": const(self._settings),
            "blinker": lambda: self._create_blinker,
        }
        
        return inject_dict

    def setup(self):
        super().setup()
        self.set_can_update_controlled_track(True)
        self.set_can_auto_arm(True)
        with self.component_guard():
            self.component_map["Pad_Modes"].selected_mode = DEFAULT_MODE
            self.component_map["Maschine_Playable"].set_scale_system(self.component_map["Scale_System"])
            self.component_map["Step_Sequence"]._note_editor.set_velocity_levels(self.component_map["Velocity_Levels"])
            self.component_map["Clip_Editor"].set_step_sequence(self.component_map["Step_Sequence"])
            self.component_map["Session_Volume"].set_device_component(self.component_map["Device"])
            encoder_mode_control = self.component_map["Encoder_Mode_Control"]
            encoder_mode_control.set_encoder_modes(self.component_map["Encoder_Modes"])
            display_mode = self.component_map["Display_Modes"]
            encoder_mode_control.set_display_modes(display_mode)
            self.component_map["Browser"].set_display_modes(display_mode)
            group_button_control = self.component_map["Group_Button_Mode_Control"]
            group_button_control.set_pad_modes(self.component_map["Pad_Modes"])
            group_button_control.set_group_button_modes(self.component_map["Group_Button_Modes"])
            self.component_map["Note_Repeat"].set_group_button_control(group_button_control)
        self._start_screen_bridge()
        if self._standby:
            self.request_rebuild_midi_map()
            self._blank_hardware()

    def disconnect(self):
        super().disconnect()

        # Save settings
        self._settings.save()

        # Clear display
        for line in range(4):
            message = make_display_sysex_message(line, (ord(" "),) * 28)
            self._send_midi(message)
        
        # Clear touchstrip
        self._send_midi((0xE0, 0x00, 0x00))
        # Pads and buttons off too: with Ableton closed the Maschine rests instead of keeping its last lights
        self._standby = True
        self._blank_hardware()

        if self._screen_bridge_timer is not None:
            self._screen_bridge_timer.stop()
            self._screen_bridge_timer = None
        if self._screen_bridge is not None:
            self._screen_bridge.close()
            self._screen_bridge = None

    def _on_playable_mode_selected(self):
        logger.info(f"keyboard button state = {self.elements.keyboard.is_pressed}")
        if self.elements.keyboard.is_pressed:
            with self.component_guard():
                if liveobj_valid(self._current_drum_group):
                    self._select_playable_mode(DRUMRACK_MODE)
                elif liveobj_valid(self._current_sliced_simpler):
                    self._select_playable_mode(SIMPLER_MODE)
                else:
                    self._select_playable_mode(KEYBOARD_MODE)

    def _on_pad_mode_changed(self, component):
        is_playable_enabled = self.get_pad_mode() in self._playable_mode_list
        state = "On" if is_playable_enabled else "Off"
        self.elements.keyboard.send_value(MaschineSkin[f"DefaultButton.{state}"].midi_value)

    def _on_display_mode_changed(self, component):
        mode = self.component_map["Display_Modes"].selected_mode
        self._update_session_view_led()
        if self._display_mode == "custom":
            self._refresh_track_buttons_state(mode)
            # self._refresh_task = self._tasks.add(task.sequence(task.wait(0.1), task.run(lambda: self._refresh_upper_button_state(mode))))
        self._display_mode = mode
        if mode == "default":
            return
        elif mode == "device":
            target_view = "Detail/DeviceChain"
        elif mode == "clip":
            target_view = "Detail/Clip"
        else:
            return
        
        if not self.application.view.is_view_visible(target_view):
            self.application.view.show_view(target_view)

        self.application.view.focus_view(target_view)

    def _refresh_track_buttons_state(self, mode):
        # LED state sync failure happens when the display mode switches to another mode from the custom(MIDI mapping) mode
        # Triggering update manually to sync LED state
        # The easiest solution is just calling update(), but it refreshes all components and controls state.
        # I confine the targets to objects that affect this issue to reduce unnecessary processes.
        logger.info("Trigger upper button state update")

        with self.component_guard():
            for button in self.elements.track_buttons_raw:
                button.clear_send_cache()

            if mode == "default":
                self.component_map["Mixer"].update()
            elif mode == "device":
                self.component_map["Device_Navigation"].update()
            elif mode == "clip":
                self.component_map["Clip_Editor"].update()
            elif mode == "browser":
                self.component_map["Browser"].update()
            elif mode == "settings":
                self.component_map["Settings"].update()

    def drum_group_changed(self, drum_group):
        logger.info(f"Drum Group = {drum_group}")
        self._current_drum_group = drum_group

        with self.component_guard():
            update_mode = self.get_pad_mode() in self._playable_mode_list
            if liveobj_valid(drum_group):
                self._select_playable_mode(DRUMRACK_MODE, update_mode)
            elif not liveobj_valid(self._current_sliced_simpler):
                self._select_playable_mode(KEYBOARD_MODE, update_mode)

    def sliced_simpler_changed(self, sliced_simpler):
        logger.info(f"Simpler = {sliced_simpler}")
        self._current_sliced_simpler = sliced_simpler
        
        with self.component_guard():
            update_mode = self.get_pad_mode() in self._playable_mode_list
            if liveobj_valid(sliced_simpler):
                self._select_playable_mode(SIMPLER_MODE, update_mode)
            elif not liveobj_valid(self._current_drum_group):
                self._select_playable_mode(KEYBOARD_MODE, update_mode)
    
    def get_pad_mode(self):
        return self.component_map["Pad_Modes"].selected_mode

    def _select_playable_mode(self, mode, update_mode = True):
        if update_mode:
            self.component_map["Pad_Modes"].selected_mode = mode
        self.component_map["Step_Sequence"].set_pitch_provider(self.component_map[self._provider_list[mode]])
        self.component_map["Velocity_Levels"].set_pitch_provider(self.component_map[self._provider_list[mode]])

    def refresh_state(self):
        logger.info("Refresh state")
        super().refresh_state()
