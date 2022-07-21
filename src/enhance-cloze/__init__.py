from .editor import setup_editor
from .menu import setup_enhanced_cloze_menu
from .model import setup_maybe_update_model_on_startup
from .patches import setup_prevent_warnings_about_clozes
from .compat import add_compatibility_aliases
from aqt.gui_hooks import profile_did_open

profile_did_open.append(add_compatibility_aliases)

setup_maybe_update_model_on_startup()
setup_editor()
setup_enhanced_cloze_menu()
setup_prevent_warnings_about_clozes()
