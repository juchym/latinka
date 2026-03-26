import sys
import tty
import termios

from enum import Enum

def is_vowel(c: str):
    return c in "AaIiYyUuEeOo"

def can_iotate(c: str):
    return c in "AaIiUuEe"

def is_iota(c: str):
    return c in "Jj"

def is_consonant(c: str, include_iota=False):
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
    SloW = 9 # after lowercase w
    SupW = 10 # after uppercase w
    SloC = 11 # after lowercase c
    SupC = 12 # after uppercase c
    
# TODO: x -> кс

class Input:
    FLUSH = "\x00"

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
            
            case (State.S0 | State.SC | State.SA, "w"): return (State.SloW, "")
            case (State.S0 | State.SC | State.SA, "W"): return (State.SupW, "")
            case (State.S0 | State.SC | State.SA, "c"): return (State.SloC, "")
            case (State.S0 | State.SC | State.SA, "C"): return (State.SupC, "")
            case (State.S0 | State.SC | State.SA, ch) if is_consonant(ch):
                return (State.SC, conversion_table.get(ch, ch))
            case (State.SA, Input.FLUSH):  return (State.S0, "'")
            case (State.S0 | State.SC | State.SA, ch):
                return (State.S0, conversion_table.get(ch, ch))
            
            case (State.SloJ0, "w"): return (State.SloW, "й")
            case (State.SloJ0, "W"): return (State.SupW, "й")
            case (State.SloJA, "w"): return (State.SloW, "'й")
            case (State.SloJA, "W"): return (State.SupW, "'й")
            case (State.SloJ0, "c"): return (State.SloC, "й")
            case (State.SloJ0, "C"): return (State.SupC, "й")
            case (State.SloJA, "c"): return (State.SloC, "'й")
            case (State.SloJA, "C"): return (State.SupC, "'й")
            case (State.SloJ0 | State.SloJA, ch) if is_consonant(ch):
                return (State.SC, "й" + conversion_table.get(ch, ch))
            
            case (State.SupJ0, "w"): return (State.SloW, "Й")
            case (State.SupJ0, "W"): return (State.SupW, "Й")
            case (State.SupJA, "w"): return (State.SloW, "'Й")
            case (State.SupJA, "W"): return (State.SupW, "'Й")
            case (State.SupJ0, "c"): return (State.SloC, "Й")
            case (State.SupJ0, "C"): return (State.SupC, "Й")
            case (State.SupJA, "c"): return (State.SloC, "'Й")
            case (State.SupJA, "C"): return (State.SupC, "'Й")
            case (State.SupJ0 | State.SupJA, ch) if is_consonant(ch):
                return (State.SC, "Й" + conversion_table.get(ch, ch))
            
            
            case (State.SloJC, "w"): return (State.SloW, "ь")
            case (State.SloJC, "W"): return (State.SupW, "ь")
            case (State.SloJC, "c"): return (State.SloC, "ь")
            case (State.SloJC, "C"): return (State.SupC, "ь")
            case (State.SloJC, ch) if is_consonant(ch):
                return (State.SC, "ь" + conversion_table.get(ch, ch))
            
            case (State.SupJC, "w"): return (State.SloW, "Ь")
            case (State.SupJC, "W"): return (State.SupW, "Ь")
            case (State.SupJC, "c"): return (State.SloC, "Ь")
            case (State.SupJC, "C"): return (State.SupC, "Ь")
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
            
            case (State.SloJA, "w"): return (State.SloW, "'й")
            case (State.SloJA, "W"): return (State.SupW, "'й")
            case (State.SupJA, "w"): return (State.SloW, "'Й")
            case (State.SupJA, "W"): return (State.SupW, "'Й")
            case (State.SloJA, "c"): return (State.SloC, "'й")
            case (State.SloJA, "C"): return (State.SupC, "'й")
            case (State.SupJA, "c"): return (State.SloC, "'Й")
            case (State.SupJA, "C"): return (State.SupC, "'Й")
            
            case (State.SloW, "q" | "Q"): return (State.SC, "щ")
            case (State.SloW, "w" | "W"): return (State.SC, "ш")
            case (State.SloW, "j"): return (State.SloJC, "ш")
            case (State.SloW, "J"): return (State.SupJC, "ш")
            case (State.SloW, "'"): return (State.SA, "ш")
            case (State.SloW, Input.FLUSH): return (State.S0, "ш")
            case (State.SloW, ch):
                return (State.SC, "ш" + conversion_table.get(ch, ch))
            
            case (State.SupW, "q" | "Q"): return (State.SC, "Щ")
            case (State.SupW, "w" | "W"): return (State.SC, "Ш")
            case (State.SupW, "j"): return (State.SloJC, "Ш")
            case (State.SupW, "J"): return (State.SupJC, "Ш")
            case (State.SupW, "'"): return (State.SA, "Ш")
            case (State.SupW, Input.FLUSH): return (State.S0, "Ш")
            case (State.SupW, ch):
                return (State.SC, "Ш" + conversion_table.get(ch, ch))
            
            case (State.SloC, "h" | "H"): return (State.SC, "х")
            case (State.SloC, "c" | "C"): return (State.SC, "ц")
            case (State.SloC, "j"): return (State.SloJC, "ц")
            case (State.SloC, "J"): return (State.SupJC, "ц")
            case (State.SloC, "'"): return (State.SA, "ц")
            case (State.SloC, Input.FLUSH): return (State.S0, "ц")
            case (State.SloC, ch):
                return (State.SC, "ц" + conversion_table.get(ch, ch))
            
            case (State.SupC, "h" | "H"): return (State.SC, "Х")
            case (State.SupC, "C" | "C"): return (State.SC, "Ц")
            case (State.SupC, "j"): return (State.SloJC, "Ц")
            case (State.SupC, "J"): return (State.SupJC, "Ц")
            case (State.SupC, "'"): return (State.SA, "Ц")
            case (State.SupC, Input.FLUSH): return (State.S0, "Ц")
            case (State.SupC, ch):
                return (State.SC, "Ц" + conversion_table.get(ch, ch))

            case (State.SloJ0, Input.FLUSH): return (State.S0, "й")
            case (State.SloJA, Input.FLUSH): return (State.S0, "'й")
            case (State.SloJ0 | State.SloJA, ch):
                return (State.S0, "й" + conversion_table.get(ch, ch))
            case (State.SupJ0 | State.SupJA, ch):
                return (State.S0, "Й" + conversion_table.get(ch, ch))
            case (State.SloJC, Input.FLUSH): return (State.S0, "ь")
            case (State.SloJC, ch):
                return (State.S0, "ь" + conversion_table.get(ch, ch))
            case (State.SupJC, ch):
                return (State.S0, "Ь" + conversion_table.get(ch, ch))

            case (_, Input.FLUSH): return (State.S0, "")
            

    def _composition_preview_for(self, state: State) -> str:
        match state:
            case State.SloJ0 | State.SloJC: return "ј"
            case State.SupJ0 | State.SupJC: return "Ј"
            case State.SA: return "'"
            case State.SloJA: return "'ј"
            case State.SupJA: return "'Ј"
            case State.SloW: return "ш"
            case State.SupW: return "Ш"
            case State.SloC: return "ц"
            case State.SupC: return "Ц"
            case _: return ""

    def feed(self, c: str) -> str:
        state, out = self.next(c)
        
        erase = "\b \b" * len(self.composition_preview)
        self.composition_preview = self._composition_preview_for(state)
        
        self.state = state
        return erase + out + "\x1B[4m" + self.composition_preview + "\x1B[0m"
            
    def flush(self) -> str:
        return self.feed(Input.FLUSH)

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
