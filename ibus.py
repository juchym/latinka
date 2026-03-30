import gi
gi.require_version("IBus", "1.0")
from gi.repository import IBus, GLib

from typing import override

from main import Transliterator

class UkrainianEngine(IBus.Engine):
    
    def __init__(self):
        super(UkrainianEngine, self).__init__()
        self._t = Transliterator()
        
    @override
    def do_process_key_event(self, keyval: int, keycode: int, state: int) -> bool:
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        
        if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK):
            self._commit_pending()
            return False
        
        if keyval in (
            IBus.KEY_Return, IBus.KEY_KP_Enter,
            IBus.KEY_Escape,
            IBus.KEY_Left, IBus.KEY_Right, IBus.KEY_Up, IBus.KEY_Down,
            IBus.KEY_Home, IBus.KEY_End,
            IBus.KEY_Page_Up, IBus.KEY_Page_Down,
            IBus.KEY_Tab,
            ):
            self._commit_pending()
            return False
        
        if keyval in (IBus.KEY_Shift_L, IBus.KEY_Shift_R,
                  IBus.KEY_Control_L, IBus.KEY_Control_R,
                  IBus.KEY_Alt_L, IBus.KEY_Alt_R,
                  IBus.KEY_Caps_Lock, IBus.KEY_Super_L, IBus.KEY_Super_R):
            return False
        
        if keyval == IBus.KEY_BackSpace:
            if self._t.composition_preview:
                _ = self._t.flush()
                self._update_preedit()
                return True
            else:
                return False
        
        ch = IBus.keyval_to_unicode(keyval)
        if not ch:
            return False
        
        if not ch.isprintable():
            self._commit_pending()
            return False
        
        out = self._t.feed(ch)
        if out:
            self._commit_text(out)
        self._update_preedit()
        return True
    
    @override
    def do_focus_out(self) -> None:
        self._commit_pending()
    
    @override
    def do_reset(self) -> None:
        self._commit_pending()
    
    def _commit_text(self, text: str) -> None:
        self.commit_text(IBus.Text.new_from_string(text))
        
    def _commit_pending(self) -> None:
        if not self._t.composition_preview:
            return
        out = self._t.flush()
        if out:
            self._commit_text(out)
        self._update_preedit()
        pass
        
    def _update_preedit(self) -> None:
        preview = self._t.composition_preview
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
        pass


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
    GLib.MainLoop().run()
    


if __name__ == "__main__":
    main()