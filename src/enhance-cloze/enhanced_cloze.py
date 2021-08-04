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

from anki import version as anki_version
from anki.hooks import addHook, wrap
from aqt import mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import showInfo, tr

from .model import enhancedModel


def gc(arg, fail=False):
    conf = mw.addonManager.getConfig(__name__)
    if conf:
        return conf.get(arg, fail)
    return fail


# constants
MODEL_NAME = "Enhanced Cloze 2.1"
CONTENT_FIELD_NAME = "Content"
OLD_CONTENT_FIELD_NAME = "# Content" # in a previous verion of the add-on the field was named that way
IN_USE_CLOZES_FIELD_NAME = "In-use Clozes"



def generate_enhanced_cloze(note):
    src_content = note[CONTENT_FIELD_NAME]

    # Get ids of in-use clozes
    cloze_start_regex = r"\{\{c\d+::"
    cloze_start_matches = re.findall(cloze_start_regex, src_content)

    note["data"] = prepareData(src_content)

    # if no clozes are found, empty Cloze1 ~ Cloze20 and fill in Cloze99
    if not cloze_start_matches:
        for i_cloze_field_number in range(1, 20 + 1):
            dest_field_name = "Cloze%s" % i_cloze_field_number
            note[dest_field_name] = ""

        note[IN_USE_CLOZES_FIELD_NAME] = "[0]"
        note["Cloze1"] = src_content
        return

    in_use_clozes_numbers = sorted([int(re.sub(r"\D", "", x)) for x in set(cloze_start_matches)])
    note[IN_USE_CLOZES_FIELD_NAME] = str(in_use_clozes_numbers)

    # Fill in content in in-use cloze fields and empty content in not-in-use fields
    for current_cloze_field_number in range(1, 20 + 1):
        dest_field_name = "Cloze%s" % current_cloze_field_number

        if not current_cloze_field_number in in_use_clozes_numbers:
            note[dest_field_name] = ''
            continue

        note[dest_field_name] = f'<span show-state="hint" cloze-id="c{current_cloze_field_number}">{{{{c{current_cloze_field_number}::text}}}}</span>'
    return


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
        part += content[prev_end_idx : m.start()]
        prev_m = m

        part += f'<span class="'
        parts.append((part, int(cloze_id[1:])))

        part = f'" index="{i}" show-state="hint" cloze-id="{cloze_id}">{{{{{cloze_id}::{answer}::{hint}}}}}</span>'

        answers.append(answer)
        hints.append(hint)

    # add text after last cloze to parts
    prev_end_idx = prev_m.end() if prev_m is not None else 0
    part += content[prev_end_idx :]
    parts.append((part, None))

    return "<script type='text/javascript'>data=" + json.dumps({
        'parts' : parts,
        'answers' : answers,
        'hints' : hints,
    }).replace('<', '\u003c').replace('-->', '--\>') + "</script>"


def check_model(model):
    """Whether this model is Enhanced cloze version 2.1"""
    return re.search(MODEL_NAME, model["name"])


def exists_model():
    "Whether the collection contains model Enhanced Cloze 2.1"
    for model in mw.col.models.all():
        if check_model(model):
            return True
    return False


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
    nids = mw.col.findNotes("*")
    for nid in nids:
        note = mw.col.getNote(nid)
        if not check_model(note.model()):
            continue
        generate_enhanced_cloze(note)
        note.flush()


def setup_menu(self):
    browser = self
    menu = browser.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('Update Enhanced Clozes')
    a.setShortcut(QKeySequence(gc("update enhanced cloze shortcut")))
    a.triggered.connect(
        lambda _, b=browser: update_all_enhanced_clozes_in_browser(b))
addHook("browser.setupMenus", setup_menu)


# copied from "Cloze (Hide All)" by phu54321 from
# https://ankiweb.net/shared/info/1709973686
def ec_beforeSaveNow(self, callback, keepFocus=False, *, _old):
    """Automatically generate overlapping clozes before adding cards"""
    def newCallback():
        # self.note may be None when editor isn't yet initialized.
        # ex: entering browser
        if self.note and self.note.model()["name"] == MODEL_NAME:
            generate_enhanced_cloze(self.note)
            if not self.addMode:
                self.note.flush()
                self.mw.requireReset()
        callback()
    return _old(self, newCallback, keepFocus)
Editor.saveNow = wrap(Editor.saveNow, ec_beforeSaveNow, "around")


ANKI_VERSION_TUPLE = tuple(int(i) for i in anki_version.split("."))
if ANKI_VERSION_TUPLE < (2, 1, 21):
    Editor.saveNow = wrap(Editor.saveNow, ec_beforeSaveNow, "around")
else:
    # downside: Anki will warn about missing clozes
    # from anki import hooks
    # def maybe_generate_enhanced_cloze(note):
    #     if note and note.model()["name"] == MODEL_NAME:
    #         generate_enhanced_cloze(note)
    # hooks.note_will_flush.append(maybe_generate_enhanced_cloze)
    from aqt import gui_hooks

    def maybe_generate_enhanced_cloze(changed, note, fieldindex):
        if note and note.model()["name"] == MODEL_NAME:
            generate_enhanced_cloze(note)
    gui_hooks.editor_did_unfocus_field.append(maybe_generate_enhanced_cloze)

if ANKI_VERSION_TUPLE >= (2, 1, 45):
    from anki.notes import NoteFieldsCheckResult

    original_update_duplicate_display = Editor._update_duplicate_display
    def _update_duplicate_display_ignore_cloze_problems_for_enh_clozes(self, result) -> None:
        if self.note._note_type['name'] == MODEL_NAME:
            if result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
            if result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
                result = NoteFieldsCheckResult.NORMAL
        original_update_duplicate_display(self, result)
    Editor._update_duplicate_display = _update_duplicate_display_ignore_cloze_problems_for_enh_clozes


    def ignore_some_cloze_problems_for_enh_clozes(problem, note):
        if note._note_type['name']  == MODEL_NAME:
            if problem == tr.adding_cloze_outside_cloze_notetype():
                return None
            elif problem == tr.adding_cloze_outside_cloze_field():
                return None
            return problem
    gui_hooks.add_cards_will_add_note.append(ignore_some_cloze_problems_for_enh_clozes)


def addModel():
    
    if exists_model():
        models = mw.col.models

        # update the fields of the model because they were previously different
        # cant just load the template on every launch because it doesn't work in Anki >= 2.1.45

        model = mw.col.models.byName(MODEL_NAME)
        if 'data' not in mw.col.models.fieldNames(model):
            mw.col.models.add_field(model, 'data')

        if OLD_CONTENT_FIELD_NAME in models.fieldNames(model):
            models.rename_field(model, OLD_CONTENT_FIELD_NAME, CONTENT_FIELD_NAME)

        return

    if ANKI_VERSION_TUPLE >= (2, 1, 45):
        showInfo(
            'Installing the Enhanced Cloze 2.1 add-on on\nAnki >= 2.1.45 requires some extra steps:\nhttps://ankiweb.net/shared/info/1990296174', 
            title="Enhanced Cloze 2.1",
        )
        return

    addon_path = os.path.dirname(__file__)
    front = os.path.join(addon_path, "Enhanced_Cloze_Front_Side.html")
    css = os.path.join(addon_path, "Enhanced_Cloze_CSS.css")
    back = os.path.join(addon_path, "Enhanced_Cloze_Back_Side.html")
    with open(front) as f:
        enhancedModel["tmpls"][0]["qfmt"] = f.read()
    with open(css) as f:
        enhancedModel["css"] = f.read()
    with open(back) as f:
        enhancedModel["tmpls"][0]["afmt"] = f.read()
    mw.col.models.add(enhancedModel)
    jsToCopy = ["_Autolinker.min.js",
                "_jquery-3.2.1.min.js",
                "_jquery.hotkeys.js",
                "_jquery.visible.min.js",
                ]
    for file in jsToCopy:
        currentfile = os.path.abspath(__file__)
        folder = os.path.basename(os.path.dirname(currentfile))
        file = os.path.join(mw.pm.addonFolder(), folder, file)
        copy(file, mw.col.media.dir())
addHook("profileLoaded", addModel)

