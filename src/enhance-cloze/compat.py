import aqt
from anki import notes


def add_compatibilty_aliases():
    add_compatibility_alias(
        notes.Note,
        "note_type",
        "model",
    )
    add_compatibility_alias(aqt.mw.col.models, "by_name", "byName")
    add_compatibility_alias(aqt.mw.col.models, "field_names", "fieldNames")
    add_compatibility_alias(aqt.mw.col.models, "field_map", "fieldMap")
    add_compatibility_alias(aqt.editor.Editor, "call_after_note_saved", "saveNow")
    add_compatibility_alias(aqt.mw.col, "get_note", "getNote")
    add_compatibility_alias(aqt.mw.col, "find_notes", "findNotes")


def add_compatibility_alias(namespace, new_name, old_name):
    if new_name not in list(namespace.__dict__.keys()):
        setattr(namespace, new_name, getattr(namespace, old_name))
        return True

    return False
