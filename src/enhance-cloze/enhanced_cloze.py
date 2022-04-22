# -*- coding: utf-8 -*-
# License: GNU GPL, version 3 or later; http://www.gnu.org/licenses/gpl.html
# Copyright: Ankitects Pty Ltd and contributors
#            2017- LuZhe610
#            2019 Arthur Milchior
#            2019 Hyun Woo Park (phu54321@naver.com)
#            2021 Jakub Fidler
#            (for the included js see the top of these files)


import os
import re
from copy import deepcopy
from typing import Optional, Tuple

from anki import notes
from anki import version as anki_version  # type: ignore
from anki.hooks import note_will_flush
from aqt import Qt, mw
from aqt.editor import Editor
from aqt.gui_hooks import (
    add_cards_will_add_note,
    editor_did_init_shortcuts,
    main_window_did_init,
    profile_did_open,
    sync_did_finish,
)
from aqt.qt import *
from aqt.utils import askUser, tr

from .compat import add_compatibilty_aliases
from .model import enhancedModel

try:
    from anki.models import NotetypeDict  # type: ignore
except:
    pass


def gc(arg, fail=False):
    conf = mw.addonManager.getConfig(__name__)
    if conf:
        return conf.get(arg, fail)
    return fail


MODEL_NAME = "Enhanced Cloze 2.1 v2"
ANKI_VERSION_TUPLE = tuple(int(i) for i in anki_version.split("."))

UPDATE_MSG = f"""\
Do you want to update the <b>{MODEL_NAME}</b> note type?<br><br>\
The changes include:
<ul>
<li>Adding and editing notes on mobile works now (except for adding notes without clozes)</li>
<li>New shortcuts for reavaling clozes (configurable):
<ul>
<li>J           - Reveal Next Genuine Cloze</li>
<li>Shift+J     - Toggle All Genuine Clozes</li>
<li>N           - Reveal Next Pseudo Cloze</li>
<li>Shift+N     - Toggle All Pseudo Clozes</li>
</ul>
<li>A new option to disable scrolling to a cloze when it is revealed</li>
<li>All Cloze1, Cloze2, ... fields except for Cloze99 are not longer necessary and were removed (also the data field)</li>
<li>Some fixes</li>
</ul>

This will require a full sync to AnkiWeb (if you use synchronization).<br><br>

If you have made changes to the note type and don\'t want to loose them you can duplicate the note type first (Tools->Manage Note Types->Add).
<br><br>
If you don't want to update you can get the previous version of the add-on from <a href="https://github.com/RisingOrange/anki-enhanced-cloze/releases/tag/1.1.4">here</a>.
<br><br>
<b>Note:</b> If you choose "No" this notice will show up the next time you open Anki."""


# this is needed so the no-cloze mode works
def maybe_fill_in_or_remove_cloze99(note):
    def in_use_clozes():
        cloze_start_regex = r"{{c\d+::"
        cloze_start_matches = re.findall(cloze_start_regex, note["Content"])
        return [int(re.sub(r"\D", "", x)) for x in set(cloze_start_matches)]

    if note and note.note_type()["name"] == MODEL_NAME:
        if in_use_clozes():
            note["Cloze99"] = ""
        else:
            note["Cloze99"] = "{{c1::.}}"


note_will_flush.append(maybe_fill_in_or_remove_cloze99)


def on_profile_did_open():
    add_compatibilty_aliases()

    if not mw.can_auto_sync():
        add_or_update_model()
    else:
        # add the function to the sync_did_finish hook
        # and remove it from the hook after sync
        # so it only gets called on the auto sync on opening Anki
        def fn():
            add_or_update_model()
            sync_did_finish.remove(fn)

        sync_did_finish.append(fn)


profile_did_open.append(on_profile_did_open)


def add_reset_notetype_action_to_menu():
    menu: QMenu = mw.form.menuTools
    action = menu.addAction("Reset Enhanced Cloze note type to default")

    def on_triggered():

        if not askUser(
            "This will reset the Enhanced Cloze note type to its default version.\n\nNote: After doing this the next you time you synchronize Anki will require a full sync to AnkiWeb.\n\nDo you want to continue?",
        ):
            return

        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        default_model = enhanced_cloze()
        default_model["id"] = current_model["id"]
        default_model["usn"] = -1  # triggers full sync
        mw.col.models.update(default_model)

    action.triggered.connect(on_triggered)


main_window_did_init.append(add_reset_notetype_action_to_menu)


def add_reset_css_action_to_menu():
    menu: QMenu = mw.form.menuTools
    action = menu.addAction("Reset Enhanced Cloze css to default")

    def on_triggered():
        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        current_model["css"] = enhanced_cloze()["css"]
        mw.col.models.update(current_model)

    action.triggered.connect(on_triggered)


main_window_did_init.append(add_reset_css_action_to_menu)


# prevent warnings about clozes
if ANKI_VERSION_TUPLE == (2, 1, 26):
    from anki.models import ModelManager

    original_availableClozeOrds = ModelManager._availClozeOrds

    def new_availClozeOrds(self, m, flds: str, allowEmpty: bool = True):
        if m["name"] == MODEL_NAME:
            # the exact value is not important, it has to be an non-empty array
            return [0]

    ModelManager._availClozeOrds = new_availClozeOrds
elif ANKI_VERSION_TUPLE < (2, 1, 45):
    from anki.notes import Note

    original_cloze_numbers_in_fields = Note.cloze_numbers_in_fields

    def new_cloze_numbers_in_fields(self):
        if self.note_type()["name"] == MODEL_NAME:
            # the exact value is not important, it has to be an non-empty array
            return [0]
        return original_cloze_numbers_in_fields(self)

    Note.cloze_numbers_in_fields = new_cloze_numbers_in_fields
else:
    from anki.notes import NoteFieldsCheckResult

    original_update_duplicate_display = Editor._update_duplicate_display

    def _update_duplicate_display_ignore_cloze_problems_for_enh_clozes(
        self, result
    ) -> None:
        if self.note.note_type()["name"] == MODEL_NAME:
            if result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
            if result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
        original_update_duplicate_display(self, result)

    Editor._update_duplicate_display = (
        _update_duplicate_display_ignore_cloze_problems_for_enh_clozes
    )

    def ignore_some_cloze_problems_for_enh_clozes(problem, note):
        if note.note_type()["name"] == MODEL_NAME:
            if problem == tr.adding_cloze_outside_cloze_notetype():
                return None
            elif problem == tr.adding_cloze_outside_cloze_field():
                return None
            return problem

    add_cards_will_add_note.append(ignore_some_cloze_problems_for_enh_clozes)

    # the warning about no clozes in the field will still show up in version lower 2.1.45
    original_fields_check = notes.Note.fields_check

    def new_fields_check(self):
        result = original_fields_check(self)

        if mw.col.models.get(self.mid)["name"] != MODEL_NAME:
            return result

        if result == NoteFieldsCheckResult.MISSING_CLOZE:
            return None
        return result

    notes.Note.fields_check = new_fields_check


def check_note_type(note_type: "NotetypeDict") -> bool:
    """Whether this model is Enhanced cloze version 2.1"""
    return bool(re.search(MODEL_NAME, note_type["name"]))


def new_version_available():
    return current_version() is None or current_version() < incoming_version()


def current_version() -> Optional[Tuple[int]]:
    return version(mw.col.models.by_name(MODEL_NAME))


def incoming_version() -> Optional[Tuple[int]]:
    return version(enhanced_cloze())


def version(note_type: "NotetypeDict") -> Optional[Tuple[int]]:
    front = note_type["tmpls"][0]["qfmt"]
    m = re.match("<!-- VERSION (.+?) -->", front)
    if not m:
        return None

    return tuple(map(int, m.group(1).split(".")))


def set_version(front: str, version: Tuple[int]) -> str:
    return re.sub(
        "<!-- VERSION (.+?) -->",
        f"<!-- VERSION {'.'.join(map(str, version))} -->",
        front,
    )


def add_or_update_model():
    model = mw.col.models.by_name(MODEL_NAME)
    if not model:
        mw.col.models.add(enhanced_cloze())
    else:

        if not new_version_available():
            return

        if current_version() is None:
            update_from_unnamed_version()
            return

        # update the code part, the version number and the config on the front template, keep the rest as it is
        # so that users can customize the other parts of the template
        seperator = "<!-- ENHANCED_CLOZE -->"
        cur_front = model["tmpls"][0]["qfmt"]
        incoming_front = enhanced_cloze()["tmpls"][0]["qfmt"]

        cur_sep_m = re.search(seperator, cur_front)
        incoming_sep_m = re.search(seperator, incoming_front)
        if not cur_sep_m:
            print("Could not find seperator comment, replacing whole front template")
            model["tmpls"][0]["qfmt"] = incoming_front
        else:
            cur_before_sep = cur_front[: cur_sep_m.start()]
            incoming_after_sep = incoming_front[incoming_sep_m.end() :]
            new_front = f"{cur_before_sep}{seperator}{incoming_after_sep}"
            new_front = set_version(new_front, incoming_version())
            new_front = maybe_add_config_option(
                new_front,
                "animateScroll",
                "var animateScroll = true",
                "scrollToClozeOnToggle",
            )
            new_front = maybe_add_config_option(
                new_front,
                "showHintsForPseudoClozes",
                "var showHintsForPseudoClozes = true",
                "animateScroll",
            )
            new_front = maybe_add_config_option(
                new_front,
                "underlineRevealedPseudoClozes",
                "var underlineRevealedPseudoClozes = true",
                "showHintsForPseudoClozes",
            )
            new_front = maybe_add_config_option(
                new_front,
                "underlineRevealedGenuineClozes",
                "var underlineRevealedGenuineClozes = true",
                "underlineRevealedPseudoClozes",
            )
            model["tmpls"][0]["qfmt"] = new_front

        mw.col.models.update(model)


def maybe_add_config_option(
    front: str, option_name: str, line_to_be_added: str, previous_option_name: str
) -> str:
    # hacky way to add options to the CONFIG, the CONFIG being the section of the front template
    # before the <!-- CONFIG END --> comment
    # the text in to be added will be added after previous_option where previous_option
    # is the name of a configuration variable

    assert option_name in line_to_be_added

    config_m = re.search("([\w\W]*?)<!-- CONFIG END -->", front)
    config_str = config_m.group(1)

    if option_name in config_str:
        return front

    new_config_str = re.sub(
        f"(?<=\n)(.*)(var +{previous_option_name}.+)\n",
        rf"\1\2\n\1{line_to_be_added}\n",
        config_str,
    )
    result = f"{new_config_str}{front[len(config_str) :]}"
    return result


def update_from_unnamed_version():
    if not askUser(
        title="Enhanced Cloze",
        text=UPDATE_MSG,
        defaultno=True,
    ):
        return

    mm = mw.col.models
    model = mm.by_name(MODEL_NAME)

    def remove_field_if_exists(field_name, model):
        if field_name in mm.field_names(model):
            mm.remove_field(model, mm.field_map(model)[field_name][1])

    fields_to_remove = [f"Cloze{i}" for i in range(1, 51)]
    fields_to_remove.extend(
        [
            "data",
            "In-use Clozes",
        ]
    )

    for field in fields_to_remove:
        remove_field_if_exists(field, model)

    load_enhanced_cloze(model)
    mm.update(model)


def enhanced_cloze() -> "NotetypeDict":
    result = deepcopy(enhancedModel)
    load_enhanced_cloze(result)
    return result


def load_enhanced_cloze(note_type: "NotetypeDict"):
    addon_path = os.path.dirname(__file__)
    front_path = os.path.join(addon_path, "Enhanced_Cloze_Front_Side.html")
    css_path = os.path.join(addon_path, "Enhanced_Cloze_CSS.css")
    back_path = os.path.join(addon_path, "Enhanced_Cloze_Back_Side.html")

    with open(front_path) as f:
        front = f.read()
    with open(back_path) as f:
        back = f.read()
    with open(css_path) as f:
        styling = f.read()

    note_type["tmpls"][0]["qfmt"] = front
    note_type["tmpls"][0]["afmt"] = back
    note_type["css"] = styling


def make_cloze_shortcut_start_at_cloze1(shortcuts, editor):

    original_onCloze = Editor.onCloze

    # code adapted from original onCloze and _onCloze
    def myOnCloze(self):
        if self.note.note_type()["name"] == MODEL_NAME:
            self.call_after_note_saved(lambda: _myOnCloze(editor), keepFocus=True)
        else:
            original_onCloze(self)

    def _myOnCloze(self):
        # find the highest existing cloze
        highest = 0
        val = self.note["Content"]
        m = re.findall(r"\{\{c(\d+)::", val)
        if m:
            highest = max(highest, sorted([int(x) for x in m])[-1])
        # reuse last?
        if not self.mw.app.keyboardModifiers() & Qt.KeyboardModifier.AltModifier:
            highest += 1
        # must start at 1
        highest = max(1, highest)
        self.web.eval("wrap('{{c%d::', '}}');" % highest)

    replace_shortcut(shortcuts, "Ctrl+Shift+C", lambda: myOnCloze(editor))
    replace_shortcut(shortcuts, "Ctrl+Shift+Alt+C", lambda: myOnCloze(editor))


def replace_shortcut(shortcuts, key_combination, func):
    existing = next((x for x in shortcuts if x[0] == key_combination), None)
    if existing is not None:
        shortcuts.remove(existing)
    shortcuts.append((key_combination, func))


if ANKI_VERSION_TUPLE < (2, 1, 50):
    editor_did_init_shortcuts.append(make_cloze_shortcut_start_at_cloze1)
