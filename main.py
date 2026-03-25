import sys
import tty
import termios

from enum import Enum

def is_vowel(c):
    return c in "AaIiYyUuEeOo"

def can_iotate(c):
    return c in "AaIiUuEe"

def is_iota(c):
    return c in "Jj"

def is_consonant(c, include_iota=False):
    return c in "BbCcDdFfGgHhKkLlMmNnPpQqRrSsTtVvWwXxZz" or include_iota and is_iota(c)

conversion_table = {
    "a": "а","b": "б","c": "ц","d": "д","e": "е","f": "ф","g": "ж","h": "г","i": "і","j": "й","k": "к","l": "л","m": "м",
    "n": "н","o": "о","p": "п","q": "ч","r": "р","s": "с","t": "т","u": "у","v": "в","w": "ш","x": "х","y": "и","z": "з",
}

for k, v in list(conversion_table.items()):
    conversion_table[k.upper()] = v.upper()

class State(Enum):
    S0 = 0 # initial
    SC = 1 # after hard consonant
    SloJ0 = 2 # after lowercase j
    SupJ0 = 3 # after uppwercase j
    SloJC = 4 # after lowercase j after hard consonant
    SupJC = 5 # after uppercase j after hard consonant
    SA = 6 # after apostrophe after hard consonant
    SloJA = 7 # after lowercase j after apostrophe
    SupJA = 8 # after uppercase j after apostrophe
    
# TODO: x -> кс, ch -> х, wq -> щ, ww -> ш

class Transliterator:

    def __init__(self):
        self.state = State.S0
        self.composition_preview = ""

    def next(self, c: str) -> tuple[State, str]:
        match (self.state, c):
            case (State.S0, "j"): return (State.SloJ0, "")
            case (State.S0, "J"): return (State.SupJ0, "")
            
            case (State.SC, "j"): return (State.SloJC, "")
            case (State.SC, "J"): return (State.SupJC, "")
            case (State.SC, "'"): return (State.SA, "")
            
            case (State.SA, "j"): return (State.SloJA, "")
            case (State.SA, "J"): return (State.SupJA, "")
            case (State.SA, "'"): return (State.S0, "'")

            case (State.S0 | State.SC | State.SA, ch) if is_consonant(ch):
                return (State.SC, conversion_table.get(ch, ch))
            case (State.S0 | State.SC | State.SA, ch):
                return (State.S0, conversion_table.get(ch, ch))
            
            case (State.SloJ0 | State.SloJA, ch) if is_consonant(ch):
                return (State.SC, "й" + conversion_table.get(ch, ch))
            case (State.SupJ0 | State.SupJA, ch) if is_consonant(ch):
                return (State.SC, "Й" + conversion_table.get(ch, ch))
            
            case (State.SloJC, ch) if is_consonant(ch):
                return (State.SC, "ь" + conversion_table.get(ch, ch))
            case (State.SupJC, ch) if is_consonant(ch):
                return (State.SC, "Ь" + conversion_table.get(ch, ch))
            
            case (State.SloJ0, "j" | "J"): return (State.S0, "й")
            case (State.SupJ0, "j" | "J"): return (State.S0, "Й")
            
            case (State.SloJC, "j" | "J"): return (State.S0, "ь")
            case (State.SupJC, "j" | "J"): return (State.S0, "Ь")
            
            case (State.SloJA, "j" | "J"): return (State.S0, "'й")
            case (State.SupJA, "j" | "J"): return (State.S0, "'Й")

            case (State.SloJ0 | State.SloJC, "a" | "A"): return (State.S0, "я")
            case (State.SupJ0 | State.SupJC, "a" | "A"): return (State.S0, "Я")
            case (State.SloJA, "a" | "A"): return (State.S0, "'я")
            case (State.SupJA, "a" | "A"): return (State.S0, "'Я")
            
            case (State.SloJ0, "i" | "I"): return (State.S0, "ї")
            case (State.SupJ0, "i" | "I"): return (State.S0, "Ї")
            case (State.SloJC | State.SloJA, "i" | "I"): return (State.S0, "'ї")
            case (State.SupJC | State.SupJA, "i" | "I"): return (State.S0, "'Ї")
            
            case (State.SloJ0 | State.SloJC, "u" | "U"): return (State.S0, "ю")
            case (State.SupJ0 | State.SupJC, "u" | "U"): return (State.S0, "Ю")
            case (State.SloJA, "u" | "U"): return (State.S0, "'ю")
            case (State.SupJA, "u" | "U"): return (State.S0, "'Ю")
            
            case (State.SloJ0 | State.SloJC, "e" | "E"): return (State.S0, "є")
            case (State.SupJ0 | State.SupJC, "e" | "E"): return (State.S0, "Є")
            case (State.SloJA, "e" | "E"): return (State.S0, "'є")
            case (State.SupJA, "e" | "E"): return (State.S0, "'Є")

            case (State.SloJA, "o"): return (State.S0, "йо")
            case (State.SloJA, "O"): return (State.S0, "йО")
            case (State.SupJA, "o"): return (State.S0, "Йо")
            case (State.SupJA, "O"): return (State.S0, "ЙО")

            case (State.SloJ0 | State.SloJA, ch):
                return (State.S0, "й" + conversion_table.get(ch, ch))
            case (State.SupJ0 | State.SupJA, ch):
                return (State.S0, "Й" + conversion_table.get(ch, ch))
            case (State.SloJC, ch):
                return (State.S0, "ь" + conversion_table.get(ch, ch))
            case (State.SupJC, ch):
                return (State.S0, "Ь" + conversion_table.get(ch, ch))

    def _composition_preview_for(self, state: State) -> str:
        match state:
            case State.SloJ0 | State.SloJC: return "ј"
            case State.SupJ0 | State.SupJC: return "Ј"
            case State.SA: return "'"
            case State.SloJA: return "'ј"
            case State.SupJA: return "'Ј"
            case _: return ""

    def feed(self, c: str) -> str:
        state, out = self.next(c)
        
        erase = "\b \b" * len(self.composition_preview)
        self.composition_preview = self._composition_preview_for(state)
        
        self.state = state
        return erase + out + "\x1B[4m" + self.composition_preview + "\x1B[0m"

    def next_on_flush(self):
        match self.state:
            case State.SloJ0: return (State.S0, "й")
            case State.SloJC: return (State.S0, "ь")
            case State.SA:  return (State.S0, "'")
            case State.SloJA: return (State.S0, "'й")
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
