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
from time import sleep

import Live # type: ignore

from ableton.v3.base import lazy_attribute, const, listens
from ableton.v3.live import liveobj_valid, scene_index
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
# PAD MODE, KEYBOARD, CHORDS and STEP select VirtualDJ's pad page, so they follow the pads while locked
PAD_PAGE_BUTTONS = ((0xB1, 81), (0xB1, 82), (0xB1, 83), (0xB1, 84))
# Buttons 1-4 above the screen (notes 0-3, channel 2) belong to VirtualDJ only (stems KICK / HATS of each deck):
# Ableton never uses them, in any mode, and never drives their LEDs
VDJ_ONLY_CHANNEL = 1
# CHANNEL, PLUGIN, MIXER, BROWSER, SETTINGS: moving through Ableton's views turns VOLUME / SWING / TEMPO off
VIEW_BUTTONS = ((0xB1, 34), (0xB1, 35), (0xB1, 37), (0xB1, 38), (0xB1, 41))
VDJ_ONLY_NOTES = range(0, 4)

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
    _pad_lock = False
    _swallow_lock_release = False
    _pad_mode_before_lock = None

    def __init__(self, *a, **k):
        # Settings must be loaded before initialization
        self._settings = SettingsRepository()
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
        # "SAMPLING" never reaches Ableton, it's reserved for entering VirtualDJ mode
        if is_cc and midi_bytes[:2] == VDJ_ENTER_BUTTON:
            if midi_bytes[2] > 0 and not self._vdj_mode:
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

        if is_cc and midi_bytes[:2] in VIEW_BUTTONS and midi_bytes[2] > 0 and (not self._vdj_mode or midi_bytes[:2] in VDJ_EXIT_BUTTONS):
            # Also when the view doesn't change (e.g. MIXER while already in the mixer)
            with self.component_guard():
                self.component_map["Encoder_Mode_Control"].reset_selected_mode()

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
        if not self._vdj_mode:
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
        if self._vdj_mode:
            return
        value = 127 if self.song.is_ableton_link_enabled else 0
        super()._do_send_midi((LINK_BUTTON[0], LINK_BUTTON[1], value))

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
            encoder_mode_control = self.component_map["Encoder_Mode_Control"]
            encoder_mode_control.set_encoder_modes(self.component_map["Encoder_Modes"])
            display_mode = self.component_map["Display_Modes"]
            encoder_mode_control.set_display_modes(display_mode)
            self.component_map["Browser"].set_display_modes(display_mode)
            group_button_control = self.component_map["Group_Button_Mode_Control"]
            group_button_control.set_pad_modes(self.component_map["Pad_Modes"])
            group_button_control.set_group_button_modes(self.component_map["Group_Button_Modes"])
            self.component_map["Note_Repeat"].set_group_button_control(group_button_control)

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
