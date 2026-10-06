# ==================================================
#
# This file is part of CustomMaschineMK3.
# CustomMaschineMK3 is free software licensed under GPL-3.0.
# For more details, see "LICENSE" file.
#
# ==================================================

import json
from functools import partial

import Live # type: ignore
from ableton.v3.control_surface.component import Component
from ableton.v3.control_surface.controls import ButtonControl, control_list
from ableton.v3.live import liveobj_valid

from .Logger import logger

SLOT_COUNT = 8
SLOT_NAMES = "ABCDEFGH"
# Assignments are saved with the Live Set
DATA_KEY = "CustomMaschineMK3_perform_buttons"
MIXER_KEYS = ("volume", "panning", "track_activator")


# PERFORM + group buttons A-H: user-assignable toggles.
# SHIFT + PERFORM + A-H assigns the last clicked parameter in Live (song.view.selected_parameter) to that button;
# PERFORM + A-H then switches it between its minimum and maximum (device on/off, dry/wet, send...).
# While PERFORM is held, A-H show which assigned parameters are on, the others stay dark.
class PerformButtonsComponent(Component):
    buttons = control_list(ButtonControl, control_count = SLOT_COUNT, color = "PerformButtons.Off", on_color = "PerformButtons.On")
    shift_button = ButtonControl(color = None)

    def __init__(self, name = "Perform_Buttons", *a, **k):
        super().__init__(name, *a, **k)
        self._paths = [None] * SLOT_COUNT
        self._parameters = [None] * SLOT_COUNT
        self._value_slots = [self.register_slot(None, partial(self._on_value_changed, index), "value") for index in range(SLOT_COUNT)]
        self._load()

    @buttons.pressed
    def _on_button_pressed(self, button):
        index = button.index
        if self.shift_button.is_pressed:
            self._learn(index)
        else:
            self._toggle(index)

    def _learn(self, index):
        parameter = self.song.view.selected_parameter
        path = self._path_of(parameter) if liveobj_valid(parameter) else None
        if path is None:
            self.notify(self.notifications.PerformButtons.no_parameter, SLOT_NAMES[index])
            return
        self._paths[index] = path
        self._set_parameter(index, parameter)
        self._save()
        self.notify(self.notifications.PerformButtons.assigned, SLOT_NAMES[index], parameter.name)

    def _toggle(self, index):
        parameter = self._parameter(index)
        if parameter is None:
            self.notify(self.notifications.PerformButtons.empty, SLOT_NAMES[index])
            return
        if not parameter.is_enabled:
            return
        parameter.value = parameter.max if parameter.value == parameter.min else parameter.min

    def _parameter(self, index):
        # Tracks or devices may have moved since the assignment: look it up again from its saved path
        if not liveobj_valid(self._parameters[index]) and self._paths[index] is not None:
            self._set_parameter(index, self._resolve(self._paths[index]))
        return self._parameters[index] if liveobj_valid(self._parameters[index]) else None

    def _set_parameter(self, index, parameter):
        self._parameters[index] = parameter
        self._value_slots[index].subject = parameter if liveobj_valid(parameter) else None
        self._update_led(index)

    def _on_value_changed(self, index):
        self._update_led(index)

    def _update_led(self, index):
        parameter = self._parameters[index]
        self.buttons[index].is_on = liveobj_valid(parameter) and parameter.value != parameter.min

    def update(self):
        super().update()
        for index in range(SLOT_COUNT):
            self._parameter(index)
            self._update_led(index)

    # --- saving with the Live Set ---

    def _load(self):
        try:
            paths = json.loads(self.song.get_data(DATA_KEY, "[]"))
        except Exception as error:
            logger.info(f"Perform buttons: could not load assignments ({error!r})")
            paths = []
        for index in range(SLOT_COUNT):
            self._paths[index] = paths[index] if index < len(paths) else None
            self._set_parameter(index, None)

    def _save(self):
        try:
            self.song.set_data(DATA_KEY, json.dumps(self._paths))
        except Exception as error:
            logger.info(f"Perform buttons: could not save assignments ({error!r})")

    # --- parameter <-> path ---

    def _track_ref(self, track):
        for kind, tracks in (("track", self.song.tracks), ("return", self.song.return_tracks)):
            for index, other in enumerate(tracks):
                if other == track:
                    return [kind, index]
        if track == self.song.master_track:
            return ["master", 0]
        return None

    def _path_of(self, parameter):
        owner = parameter.canonical_parent
        if isinstance(owner, Live.MixerDevice.MixerDevice):
            key = next((name for name in MIXER_KEYS if getattr(owner, name, None) == parameter), None)
            if key is None:
                key = next((f"send{index}" for index, send in enumerate(owner.sends) if send == parameter), None)
            track = self._track_ref(owner.canonical_parent)
            return None if key is None or track is None else {"track": track, "steps": [], "mixer": key}

        if not isinstance(owner, Live.Device.Device):
            return None
        parameter_index = list(owner.parameters).index(parameter)
        steps = []
        device = owner
        while True:
            container = device.canonical_parent
            steps.insert(0, ["d", list(container.devices).index(device)])
            if isinstance(container, Live.Chain.Chain):
                rack = container.canonical_parent
                chains = list(rack.chains)
                if container not in chains:
                    return None  # return chains of racks are not supported
                steps.insert(0, ["c", chains.index(container)])
                device = rack
            else:
                track = self._track_ref(container)
                return None if track is None else {"track": track, "steps": steps, "parameter": parameter_index}

    def _resolve(self, path):
        try:
            kind, index = path["track"]
            song = self.song
            obj = song.master_track if kind == "master" else (song.tracks if kind == "track" else song.return_tracks)[index]
            if "mixer" in path:
                mixer = obj.mixer_device
                key = path["mixer"]
                return mixer.sends[int(key[4:])] if key.startswith("send") else getattr(mixer, key)
            for step, step_index in path["steps"]:
                obj = obj.devices[step_index] if step == "d" else obj.chains[step_index]
            return obj.parameters[path["parameter"]]
        except Exception:
            return None
