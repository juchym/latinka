import sys
import tty
import termios

from enum import Enum

def is_vowel(c):
    return c in "aiyueo"

def can_iotate(c):
    return c in "aiue"

def is_iota(c):
    return c == "j"

def is_consonant(c, include_iota=False):
    return c in "bcdfghklmnpqrstvwxz" or include_iota and is_iota(c)

conversion_table = {
    "a": "а","b": "б","c": "ц","d": "д","e": "е","f": "ф","g": "ж","h": "г","i": "і","j": "й","k": "к","l": "л","m": "м",
    "n": "н","o": "о","p": "п","q": "ч","r": "р","s": "с","t": "т","u": "у","v": "в","w": "ш","x": "х","y": "и","z": "з",
}

for k, v in list(conversion_table.items()):
    conversion_table[k.upper()] = v.upper()

class State(Enum):
    S0 = 0 # initial
    SC = 1 # after hard consonant
    SJ0 = 2 # after j
    SJC = 3 # after j after hard consonant
    SA = 4 # after apostrophe
    SJA = 5 # after j after apostrophe

class Transliterator:

    def __init__(self):
        self.state = State.S0
        self.composition_preview = ""

    def next(self, c: str) -> tuple[State, str]:
        match (self.state, c):
            case (State.S0, "j"): return (State.SJ0, "")
            case (State.SC, "'"): return (State.SA, "")
            case (State.SC, "j"): return (State.SJC, "")
            case (State.SA, "j"): return (State.SJA, "")
            
            case (State.SA, "'"): return (State.S0, "'")

            case (State.S0 | State.SC | State.SA, ch) if is_consonant(ch):
                return (State.SC, conversion_table.get(ch, ch))
            case (State.S0 | State.SC | State.SA, ch):
                return (State.S0, conversion_table.get(ch, ch))
            
            case (State.SJ0 | State.SJA, ch) if is_consonant(ch):
                return (State.SC, "й" + conversion_table.get(ch, ch))
            case (State.SJC, ch) if is_consonant(ch):
                return (State.SC, "ь" + conversion_table.get(ch, ch))
            
            case (State.SJ0, "j"): return (State.S0, "й")
            case (State.SJC, "j"): return (State.S0, "ь")
            case (State.SJA, "j"): return (State.S0, "'й")

            case (State.SJ0 | State.SJC, "a"): return (State.S0, "я")
            case (State.SJA, "a"): return (State.S0, "'я")
            
            case (State.SJ0, "i"): return (State.S0, "ї")
            case (State.SJC | State.SJA, "i"): return (State.S0, "'ї")
            
            case (State.SJ0 | State.SJC, "u"): return (State.S0, "ю")
            case (State.SJA, "u"): return (State.S0, "'ю")
            
            case (State.SJ0 | State.SJC, "e"): return (State.S0, "є")
            case (State.SJA, "e"): return (State.S0, "'є")

            case (State.SJA, "o"): return (State.S0, "йо")

            case (State.SJ0 | State.SJA, ch):
                return (State.S0, "й" + conversion_table.get(ch, ch))
            case (State.SJC, ch):
                return (State.S0, "ь" + conversion_table.get(ch, ch))

    def _composition_preview_for(self, state: State) -> str:
        match state:
            case State.SJ0 | State.SJC: return "ј"
            case State.SA: return "'"
            case State.SJA: return "'ј"
            case _: return ""

    def feed(self, c: str) -> str:
        state, out = self.next(c)
        
        erase = "\b \b" * len(self.composition_preview)
        self.composition_preview = self._composition_preview_for(state)
        
        self.state = state
        return erase + out + "\x1B[4m" + self.composition_preview + "\x1B[0m"

    def next_on_flush(self):
        match self.state:
            case State.SJ0: return (State.S0, "й")
            case State.SJC: return (State.S0, "ь")
            case State.SA:  return (State.S0, "'")
            case State.SJA: return (State.S0, "'й")
            case _: return (State.S0, "")
            
    def flush(self) -> str:
        state, out = self.next_on_flush() # State should always be S0
        
        erase = "\b \b" * len(self.composition_preview)
        self.composition_preview = self._composition_preview_for(state) # should always return "" 
        
        self.state = state
        return erase + out + "\x1B[4m" + self.composition_preview + "\x1B[0m"

def main():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    translit = Transliterator()

    try:
        tty.setraw(fd)
        print("Type: \r")

        while True:
            ch = sys.stdin.read(1)

            if ch == "\x03":
                break

            if ch == "\r":
                sys.stdout.write(translit.flush() + "\r\n")
                sys.stdout.flush()
                continue

            if ch == "\x7F":
                sys.stdout.write("\b \b")
                sys.stdout.flush()
                continue

            out = translit.feed(ch)

            sys.stdout.write(out)
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
