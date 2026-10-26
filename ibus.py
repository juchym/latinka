import sys

import gi

gi.require_version("IBus", "1.0")
from typing import override

from gi.repository import GLib, IBus

from composer import Composer, is_hush_key, is_word_char

LANG = sys.argv[1] if len(sys.argv) > 1 else "uk"


class UkrainianEngine(IBus.Engine):

    def __init__(self):
        super().__init__()
        self._c = Composer(LANG)
        self._last = ""

    @override
    def do_process_key_event(self, keyval: int, keycode: int, state: int) -> bool:
        if state & IBus.ModifierType.RELEASE_MASK:
            return False

        if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK):
            self._commit_pending()
            return False

        if keyval in (IBus.KEY_Shift_L, IBus.KEY_Shift_R,
                  IBus.KEY_Control_L, IBus.KEY_Control_R,
                  IBus.KEY_Alt_L, IBus.KEY_Alt_R,
                  IBus.KEY_Caps_Lock, IBus.KEY_Super_L, IBus.KEY_Super_R):
            return False

        if self._c.raw():
            if keyval == IBus.KEY_BackSpace:
                self._c.pop()
                self._update_preedit()
                return True
            if keyval in (IBus.KEY_Return, IBus.KEY_KP_Enter):
                self._commit_pending()  # commit the word only, no new line
                return True
            if keyval == IBus.KEY_Escape:
                self._commit_text(self._c.raw())
                return True

        ch = IBus.keyval_to_unicode(keyval)
        if is_hush_key(ch) and self._c.raw() and self._c.can_hush():
            self._c.hush()
            self._update_preedit()
            return True
        if is_word_char(ch):
            if not self._c.raw():
                self._c.set_context(self._last)
            self._c.push(ch)
            self._update_preedit()
            return True

        # A word boundary: commit, then let the key through.
        self._commit_pending()
        self._last = ch if ch and ch.isprintable() else ""
        return False

    @override
    def do_focus_out(self) -> None:
        self._commit_pending()

    @override
    def do_reset(self) -> None:
        self._commit_pending()

    def _commit_text(self, text: str) -> None:
        self._c.commit(text)
        self._update_preedit()
        if text:
            self.commit_text(IBus.Text.new_from_string(text))
            self._last = text[-1]

    def _commit_pending(self) -> None:
        if self._c.raw():
            self._commit_text(self._c.candidates()[0])

    def _update_preedit(self) -> None:
        preview = self._c.candidates()[0] if self._c.raw() else ""
        if preview:
            preview_length = len(preview)
            text = IBus.Text.new_from_string(preview)
            text.append_attribute(
                type=IBus.AttrType.UNDERLINE,
                value=IBus.AttrUnderline.SINGLE,
                start_index=0,
                end_index=preview_length
            )
            self.update_preedit_text(text, cursor_pos=preview_length, visible=True)
        else:
            self.hide_preedit_text()


def main():
    IBus.init()
    bus = IBus.Bus()

    if not bus.is_connected():
        raise SystemExit("Cannot connect to IBus daemon. Is ibus-daemon running?")

    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine("udnc", UkrainianEngine)

    component = IBus.Component.new_from_file("udnc.xml")
    bus.register_component(component)

    bus.set_global_engine_async("udnc", -1)
    GLib.MainLoop().run() # pyright: ignore[reportUnknownMemberType]



if __name__ == "__main__":
    main()
