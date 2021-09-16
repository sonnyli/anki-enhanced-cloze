# -*- coding: utf-8 -*-
# License: GNU GPL, version 3 or later; http://www.gnu.org/licenses/gpl.html
# Copyright: Ankitects Pty Ltd and contributors
#            2017- LuZhe610
#            2019 Arthur Milchior
#            2019 Hyun Woo Park (phu54321@naver.com)
#            2021 Jakub Fidler
#            (for the included js see the top of these files)


import json
import os
import re
from shutil import copy
import aqt
from anki import notes
from anki import version as anki_version  # type: ignore
from anki.hooks import addHook, wrap
from aqt import Qt, gui_hooks, mw
from aqt.editor import Editor
from aqt.utils import tr
from PyQt5.QtGui import QKeySequence

from .model import enhancedModel
from .utils import add_compatibility_alias


def gc(arg, fail=False):
    conf = mw.addonManager.getConfig(__name__)
    if conf:
        return conf.get(arg, fail)
    return fail


MODEL_NAME = "Enhanced Cloze 2.1 v2"
CONTENT_FIELD_NAME = "Content"


def generate_enhanced_cloze(note):
    src_content = note[CONTENT_FIELD_NAME]

    note["data"] = prepareData(src_content)

    in_use_clozes_numbers = in_use_clozes(src_content)
    if not in_use_clozes_numbers:
        # if no clozes are found, fill Cloze1 and empty Cloze2 ~ Cloze50
        note["Cloze1"] = '{{c1::.}}'

        for i_cloze_field_number in range(2, 51):
            dest_field_name = "Cloze%s" % i_cloze_field_number
            note[dest_field_name] = ""
    else:
        # Fill in content in in-use cloze fields and empty content in not-in-use fields
        for current_cloze_field_number in range(1, 51):
            dest_field_name = "Cloze%s" % current_cloze_field_number

            if not current_cloze_field_number in in_use_clozes_numbers:
                note[dest_field_name] = ''
                continue

            note[dest_field_name] = f'<span show-state="hint" cloze-id="c{current_cloze_field_number}">{{{{c{current_cloze_field_number}::text}}}}</span>'


def in_use_clozes(content):
    cloze_start_regex = r"\{\{c\d+::"
    cloze_start_matches = re.findall(cloze_start_regex, content)
    return sorted([int(re.sub(r"\D", "", x)) for x in set(cloze_start_matches)])


def prepareData(content):
    # create a string that contains data that will be passed to a card

    # (string, clozeId) tuples so that adding class names inbetween
    # the strings produces the html for the enhanced clozes
    parts = []

    answers = []
    hints = []

    cloze_regex = r"\{\{c\d+::[\s\S]*?\}\}"
    part = ''
    prev_m = None
    for i, m in enumerate(re.finditer(cloze_regex, content)):
        cloze_string = m.group()  # eg. {{c1::aa[::bbb]}}
        index_of_answer = cloze_string.find("::") + 2
        index_of_hint = cloze_string.rfind("::") + 2
        cloze_id = cloze_string[2: index_of_answer - 2]  # like: c1 or c11
        cloze_length = len(cloze_string)

        if index_of_answer == index_of_hint:  # actually no hint at all
            answer = cloze_string[index_of_answer: cloze_length - 2]
            hint = ""
        else:
            answer = cloze_string[index_of_answer: index_of_hint - 2]
            hint = cloze_string[index_of_hint: cloze_length - 2]

        # add text between clozes to parts
        prev_end_idx = prev_m.end() if prev_m is not None else 0
        part += content[prev_end_idx: m.start()]
        prev_m = m

        part += f'<span class="'
        parts.append((part, int(cloze_id[1:])))

        part = f'" index="{i}" show-state="hint" cloze-id="{cloze_id}"></span>'

        answers.append(answer)
        hints.append(hint)

    # add text after last cloze to parts
    prev_end_idx = prev_m.end() if prev_m is not None else 0
    part += content[prev_end_idx:]

    # without this images (and probably other media) don't work
    # because they get partially url encoded somewhere down the line
    src_re = r'(?:src *= *)"(.+?)"'
    part = re.sub(src_re, r"src='\1'", part)
        
    parts.append((part, None))

    return "<script type='text/javascript'>data=" + json.dumps({
        'parts': parts,
        'answers': answers,
        'hints': hints,
    }).replace('<', '\u003c').replace('-->', '--\>') + "</script>"


# menu entry for updating clozes in browser
def update_all_enhanced_clozes_in_browser(self, evt=None):
    browser = self
    mw = browser.mw

    mw.checkpoint("Update Enhanced Clozes")
    mw.progress.start()
    browser.model.beginReset()

    update_all_enhanced_cloze(self)

    browser.model.endReset()
    mw.requireReset()
    mw.progress.finish()
    mw.reset()


def update_all_enhanced_cloze(self):
    mw = self.mw
    nids = mw.col.findNotes(f"\"note:{MODEL_NAME}\"")
    for nid in nids:
        note = mw.col.getNote(nid)
        if not check_model(note.note_type()):
            continue
        generate_enhanced_cloze(note)
        note.flush()


def setup_menu(self):
    browser = self
    menu = browser.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('Update Enhanced Clozes v2')
    a.setShortcut(QKeySequence(gc("update enhanced cloze v2 shortcut")))
    a.triggered.connect(
        lambda _, b=browser: update_all_enhanced_clozes_in_browser(b))


addHook("browser.setupMenus", setup_menu)


ANKI_VERSION_TUPLE = tuple(int(i) for i in anki_version.split("."))

# hook the processing of the note
if ANKI_VERSION_TUPLE < (2, 1, 21):
    # copied from "Cloze (Hide All)" by phu54321 from
    # https://ankiweb.net/shared/info/1709973686
    def ec_beforeSaveNow(self, callback, keepFocus=False, *, _old):
        def newCallback():
            # self.note may be None when editor isn't yet initialized.
            # ex: entering browser
            if self.note and self.note.note_type()["name"] == MODEL_NAME:
                generate_enhanced_cloze(self.note)
                if not self.addMode:
                    self.note.flush()
                    self.mw.requireReset()
            callback()
        return _old(self, newCallback, keepFocus)
    Editor.saveNow = wrap(Editor.saveNow, ec_beforeSaveNow, "around")
else:
    from anki import hooks

    def maybe_generate_enhanced_cloze(note):
        if note and note.note_type()["name"] == MODEL_NAME:
            generate_enhanced_cloze(note)
    hooks.note_will_flush.append(maybe_generate_enhanced_cloze)


# prevent warnings about clozes
if ANKI_VERSION_TUPLE == (2, 1, 26):
    from anki.models import ModelManager
    original_availableClozeOrds = ModelManager._availClozeOrds

    def new_availClozeOrds(self, m, flds: str, allowEmpty: bool = True):
        if m['name'] == MODEL_NAME:
            # the exact value is not important, it has to be an non-empty array
            return [0]
    ModelManager._availClozeOrds = new_availClozeOrds
elif ANKI_VERSION_TUPLE < (2, 1, 45):
    from anki.notes import Note
    original_cloze_numbers_in_fields = Note.cloze_numbers_in_fields

    def new_cloze_numbers_in_fields(self):
        if self.note_type()['name'] == MODEL_NAME:
            # the exact value is not important, it has to be an non-empty array
            return [0]
        return original_cloze_numbers_in_fields(self)
    Note.cloze_numbers_in_fields = new_cloze_numbers_in_fields
else:
    from anki.notes import NoteFieldsCheckResult

    original_update_duplicate_display = Editor._update_duplicate_display

    def _update_duplicate_display_ignore_cloze_problems_for_enh_clozes(self, result) -> None:
        if self.note.note_type()['name'] == MODEL_NAME:
            if result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
            if result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
        original_update_duplicate_display(self, result)
    Editor._update_duplicate_display = _update_duplicate_display_ignore_cloze_problems_for_enh_clozes

    def ignore_some_cloze_problems_for_enh_clozes(problem, note):
        if note.note_type()['name'] == MODEL_NAME:
            if problem == tr.adding_cloze_outside_cloze_notetype():
                return None
            elif problem == tr.adding_cloze_outside_cloze_field():
                return None
            return problem
    gui_hooks.add_cards_will_add_note.append(
        ignore_some_cloze_problems_for_enh_clozes)

    # the warning about no clozes in the field will still show up in version lower 2.1.45
    original_fields_check = notes.Note.fields_check

    def new_fields_check(self):
        if mw.col.models.get(self.mid)['name'] != MODEL_NAME:
            return

        result = original_fields_check(self)
        if result == NoteFieldsCheckResult.MISSING_CLOZE:
            return None
        return result
    notes.Note.fields_check = new_fields_check


def check_model(model):
    """Whether this model is Enhanced cloze version 2.1"""
    return re.search(MODEL_NAME, model["name"])


def add_or_update_model():
    addon_path = os.path.dirname(__file__)
    front_path = os.path.join(addon_path, "Enhanced_Cloze_Front_Side.html")
    css_path = os.path.join(addon_path, "Enhanced_Cloze_CSS.css")
    back_path = os.path.join(addon_path, "Enhanced_Cloze_Back_Side.html")

    mm = mw.col.models
    model = mm.by_name(MODEL_NAME)
    if not model:
        with open(front_path) as f:
            enhancedModel["tmpls"][0]["qfmt"] = f.read()
        with open(css_path) as f:
            enhancedModel["css"] = f.read()
        with open(back_path) as f:
            enhancedModel["tmpls"][0]["afmt"] = f.read()

        jsToCopy = ["_Autolinker.min.js",
                    "_jquery.hotkeys.js",
                    "_jquery.visible.min.js",
                    ]
        for file in jsToCopy:
            currentfile = os.path.abspath(__file__)
            folder = os.path.basename(os.path.dirname(currentfile))
            file = os.path.join(mw.pm.addonFolder(), folder, file)
            copy(file, mw.col.media.dir())

        mm.add(enhancedModel)
    else:

        # add more fields without overwriting changes made by user
        if "Cloze50" not in mm.fieldNames(model):
            for i in range(21, 51):
                mm.add_field(model, mm.new_field(f"Cloze{i}"))

        # front template:
        # ... replace the script part
        # this way changes made by the user to the styling are not overwritten
        # note that there other script tags in the template but they dont match the regex
        # because they have a src attribute
        # everything below the jquery import gets replaced
        cur_front = model["tmpls"][0]["qfmt"]

        script_re = '<!-- Do not change this part of the template! Changes will be overwritten by the add-on -->[\w\W]+$'
        with open(front_path) as f:
            front = f.read()
        script = re.search(script_re, front).group(0)
        cur_front = re.sub(script_re, script, cur_front)
        
        # remove old imports if they exist
        import_re = '<script\s*src=".+"\s*></script> *'
        import_before_script_re = f'{import_re}\n(?={script_re})'
        while re.search(import_before_script_re, cur_front):
            cur_front = re.sub(import_before_script_re, '', cur_front)

        model["tmpls"][0]["qfmt"] = cur_front

        # insert extra "{{cloze:ClozeXX}}" lines to back and front template if
        # they are in their pre-cloze-per-note-limit-increase-state
        if "{{cloze:Cloze50}}" not in cur_front:

            # front template
            extra_cloze_lines = '\n'.join(
                f'            {{{{cloze:Cloze{idx}}}}}' for idx in range(21, 51)) + '\n'
            extra_cloze_insertion_position_re = "{{cloze:Cloze20}}.*?\n"
            m = re.search(extra_cloze_insertion_position_re, cur_front)
            cur_front = cur_front[:m.end()] + \
                extra_cloze_lines + cur_front[m.end():]

            model["tmpls"][0]["qfmt"] = cur_front

            # back template:
            cur_back = model["tmpls"][0]["afmt"]
            extra_cloze_lines = '\n'.join(
                f'    {{{{cloze:Cloze{idx}}}}}' for idx in range(21, 51)) + '\n'
            m = re.search(extra_cloze_insertion_position_re, cur_back)
            cur_back = cur_back[:m.end()] + \
                extra_cloze_lines + cur_back[m.end():]
            model["tmpls"][0]["afmt"] = cur_back

        mm.update(model)


addHook("profileLoaded", add_or_update_model)


original_onCloze = Editor.onCloze


def make_cloze_shortcut_start_at_cloze1(shortcuts, editor):

    # code adapted from original onCloze and _onCloze
    def myOnCloze(self):
        if self.note.note_type()['name'] == MODEL_NAME:
            self.call_after_note_saved(
                lambda: _myOnCloze(editor), keepFocus=True)
        else:
            original_onCloze(self)

    def _myOnCloze(self):
        # find the highest existing cloze
        highest = 0
        val = self.note['Content']
        m = re.findall(r"\{\{c(\d+)::", val)
        if m:
            highest = max(highest, sorted([int(x) for x in m])[-1])
        # reuse last?
        if not self.mw.app.keyboardModifiers() & Qt.AltModifier:
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


gui_hooks.editor_did_init_shortcuts.append(
    make_cloze_shortcut_start_at_cloze1)


def add_compatibilty_aliases():
    add_compatibility_alias(notes.Note, "note_type", "model",)
    add_compatibility_alias(aqt.mw.col.models, "by_name", "byName")
    add_compatibility_alias(aqt.editor.Editor, "call_after_note_saved", "saveNow")


gui_hooks.profile_did_open.append(add_compatibilty_aliases)
