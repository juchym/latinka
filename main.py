import os
import sys

from enum import Enum

def is_vowel(c: str):
    return c in "AaIiYyUuEeOo"

def can_iotate(c: str):
    return c in "AaIiUuEe"

def is_iota(c: str):
    return c in "Jj"

def is_consonant(c: str):
    return c in "BbCcDdFfGgHhJjKkLlMmNnPpQqRrSsTtVvWwXxZz"

ct = { # conversion table
    "a": "а","b": "б","c": "ц","d": "д","e": "е","f": "ф","g": "ж","h": "г","i": "і","j": "й","k": "к","l": "л","m": "м",
    "n": "н","o": "о","p": "п","q": "ч","r": "р","s": "с","t": "т","u": "у","v": "в","w": "ш","x": "х","y": "и","z": "з",
}

for k, v in list(ct.items()):
    ct[k.upper()] = v.upper()

class State(Enum):
    S0 = 0 # initial
    SC = 1 # after hard consonant
    SA = 2 # after apostrophe after hard consonant
    SloJ0 = 3 # after lowercase j
    SloJC = 4 # after lowercase j after hard consonant
    SloJA = 5 # after lowercase j after apostrophe
    SupJ0 = 6 # after uppwercase j
    SupJC = 7 # after uppercase j after hard consonant
    SupJA = 8 # after uppercase j after apostrophe
    SloW0 = 9 # after lowercase w
    SloWC = 10 # after lowercase w after hard consonant
    SupW0 = 11 # after uppercase w
    SupWC = 12 # after uppercase w after hard consonant
    SloC0 = 13 # after lowercase c
    SloCC = 14 # after lowercase c after hard consonant
    SupC0 = 15 # after uppercase c
    SupCC = 16 # after uppercase c after hard consonant
    
# TODO: x -> кс, й after a consonant

class Input:
    NUL = "<NUL>"
    DEL = "<DEL>"

class Transliterator:

    def __init__(self):
        self.state = State.S0
        self.composition_preview = ""

    def next(self, c: str) -> tuple[State, str]:
        # general order: (1) NUL, (2) DEL, (3) "j", (4) "'", (5) other special cases, (6) consonants, (7) everything else
        match (self.state, c):
            case (State.S0, Input.NUL): return (State.S0, "")
            case (State.S0, Input.DEL): return (State.S0, "")
            case (State.S0, "j"): return (State.SloJ0, "")
            case (State.S0, "J"): return (State.SupJ0, "")
            case (State.S0, "w"): return (State.SloW0, "")
            case (State.S0, "W"): return (State.SupW0, "")
            case (State.S0, "c"): return (State.SloC0, "")
            case (State.S0, "C"): return (State.SupC0, "")
            
            case (State.SC, Input.NUL): return (State.S0, "")
            case (State.SC, Input.DEL): return (State.SC, "")
            case (State.SC, "j"): return (State.SloJC, "")
            case (State.SC, "J"): return (State.SupJC, "")
            case (State.SC, "'"): return (State.SA, "")
            case (State.SC, "w"): return (State.SloWC, "")
            case (State.SC, "W"): return (State.SupWC, "")
            case (State.SC, "c"): return (State.SloCC, "")
            case (State.SC, "C"): return (State.SupCC, "")
            
            case (State.S0 | State.SC, ch) if is_consonant(ch):
                return (State.SC, ct.get(ch, ch))
            case (State.S0 | State.SC, ch):
                return (State.S0, ct.get(ch, ch))
            
            
            case (State.SA, Input.NUL):  return (State.S0, "'")
            case (State.SA, Input.DEL):  return (State.SC, "")
            case (State.SA, "j"): return (State.SloJA, "")
            case (State.SA, "J"): return (State.SupJA, "")
            case (State.SA, "'"): return (State.S0, "'")
            case (State.SA, "w"): return (State.SloW0, "'")
            case (State.SA, "W"): return (State.SupW0, "'")
            case (State.SA, "c"): return (State.SloC0, "'")
            case (State.SA, "C"): return (State.SupC0, "'")
            
            case (State.SA, ch) if is_consonant(ch):
                return (State.SC, "'" + ct.get(ch, ch))
            case (State.SA, ch):
                return (State.S0, "'" + ct.get(ch, ch))
            
            
            case (State.SloJ0, Input.NUL): return (State.S0, "й")
            case (State.SloJ0, Input.DEL): return (State.S0, "")
            case (State.SloJ0, "j" | "J"): return (State.S0, "й")
            case (State.SloJ0, "'"): return (State.SA, "й")
            case (State.SloJ0, "i" | "I"): return (State.S0, "ї")
            case (State.SloJ0, "w"): return (State.SloWC, "й")
            case (State.SloJ0, "W"): return (State.SupWC, "й")
            case (State.SloJ0, "c"): return (State.SloCC, "й")
            case (State.SloJ0, "C"): return (State.SupCC, "й")
            
            case (State.SloJC, Input.NUL): return (State.S0, "ь")
            case (State.SloJC, Input.DEL): return (State.SC, "")
            case (State.SloJC, "j" | "J"): return (State.S0, "ь")
            case (State.SloJC, "'"): return (State.SA, "ь")
            case (State.SloJC, "w"): return (State.SloW0, "ь")
            case (State.SloJC, "W"): return (State.SupW0, "ь")
            case (State.SloJC, "c"): return (State.SloC0, "ь")
            case (State.SloJC, "C"): return (State.SupC0, "ь")
            
            case (State.SloJ0 | State.SloJC, "a" | "A"): return (State.S0, "я")
            case (State.SloJ0 | State.SloJC, "u" | "U"): return (State.S0, "ю")
            case (State.SloJ0 | State.SloJC, "e" | "E"): return (State.S0, "є")
            
            case (State.SloJA, Input.NUL): return (State.S0, "'й")
            case (State.SloJA, Input.DEL): return (State.SA, "")
            case (State.SloJA, "j" | "J"): return (State.S0, "'й")
            case (State.SloJA, "'"): return (State.SA, "'й")
            case (State.SloJA, "a" | "A"): return (State.S0, "'я")
            case (State.SloJA, "u" | "U"): return (State.S0, "'ю")
            case (State.SloJA, "e" | "E"): return (State.S0, "'є")
            case (State.SloJA, "o"): return (State.S0, "йо")
            case (State.SloJA, "O"): return (State.S0, "йО")
            case (State.SloJA, "w"): return (State.SloWC, "'й")
            case (State.SloJA, "W"): return (State.SupWC, "'й")
            case (State.SloJA, "c"): return (State.SloCC, "'й")
            case (State.SloJA, "C"): return (State.SupCC, "'й")
            
            case (State.SloJC | State.SloJA, "i" | "I"): return (State.S0, "'ї")
            
            case (State.SloJC, ch) if is_consonant(ch):
                return (State.SC, "ь" + ct.get(ch, ch))
            case (State.SloJC, ch):
                return (State.S0, "ь" + ct.get(ch, ch))
            
            case (State.SloJ0 | State.SloJA, ch) if is_consonant(ch):
                return (State.SC, "й" + ct.get(ch, ch))
            case (State.SloJ0 | State.SloJA, ch):
                return (State.S0, "й" + ct.get(ch, ch))
            
            
            case (State.SupJ0, Input.NUL): return (State.S0, "Й")
            case (State.SupJ0, Input.DEL): return (State.S0, "")
            case (State.SupJ0, "j" | "J"): return (State.S0, "Й")
            case (State.SupJ0, "'"): return (State.SA, "Й")
            case (State.SupJ0, "i" | "I"): return (State.S0, "Ї")
            case (State.SupJ0, "w"): return (State.SloWC, "Й")
            case (State.SupJ0, "W"): return (State.SupWC, "Й")
            case (State.SupJ0, "c"): return (State.SloCC, "Й")
            case (State.SupJ0, "C"): return (State.SupCC, "Й")
            
            case (State.SupJC, Input.NUL): return (State.S0, "Ь")
            case (State.SupJC, Input.DEL): return (State.SC, "")
            case (State.SupJC, "j" | "J"): return (State.S0, "Ь")
            case (State.SupJC, "w"): return (State.SloW0, "Ь")
            case (State.SupJC, "W"): return (State.SupW0, "Ь")
            case (State.SupJC, "c"): return (State.SloC0, "Ь")
            case (State.SupJC, "C"): return (State.SupC0, "Ь")
            
            case (State.SupJ0 | State.SupJC, "a" | "A"): return (State.S0, "Я")
            case (State.SupJ0 | State.SupJC, "u" | "U"): return (State.S0, "Ю")
            case (State.SupJ0 | State.SupJC, "e" | "E"): return (State.S0, "Є")
            
            case (State.SupJA, Input.NUL): return (State.S0, "'Й")
            case (State.SupJA, Input.DEL): return (State.SA, "")
            case (State.SupJA, "j" | "J"): return (State.S0, "'Й")
            case (State.SupJA, "'"): return (State.SA, "'Й")
            case (State.SupJA, "a" | "A"): return (State.S0, "'Я")
            case (State.SupJA, "u" | "U"): return (State.S0, "'Ю")
            case (State.SupJA, "e" | "E"): return (State.S0, "'Є")
            case (State.SupJA, "o"): return (State.S0, "Йо")
            case (State.SupJA, "O"): return (State.S0, "ЙО")
            case (State.SupJA, "w"): return (State.SloWC, "'Й")
            case (State.SupJA, "W"): return (State.SupWC, "'Й")
            case (State.SupJA, "c"): return (State.SloCC, "'Й")
            case (State.SupJA, "C"): return (State.SupCC, "'Й")
            
            case (State.SupJC | State.SupJA, "i" | "I"): return (State.S0, "'Ї")
            
            case (State.SupJC, ch) if is_consonant(ch):
                return (State.SC, "Ь" + ct.get(ch, ch))
            case (State.SupJC, ch):
                return (State.S0, "Ь" + ct.get(ch, ch))
            
            case (State.SupJ0 | State.SupJA, ch) if is_consonant(ch):
                return (State.SC, "Й" + ct.get(ch, ch))
            case (State.SupJ0 | State.SupJA, ch):
                return (State.S0, "Й" + ct.get(ch, ch))
            
            
            case (State.SloW0 | State.SloWC, Input.NUL): return (State.S0, "ш")
            
            case (State.SloW0, Input.DEL): return (State.S0, "")
            case (State.SloWC, Input.DEL): return (State.SC, "")
            
            case (State.SloW0 | State.SloWC, "j"): return (State.SloJC, "ш")
            case (State.SloW0 | State.SloWC, "J"): return (State.SupJC, "ш")
            case (State.SloW0 | State.SloWC, "'"): return (State.SA, "ш")
            case (State.SloW0 | State.SloWC, "q" | "Q"): return (State.SC, "щ")
            case (State.SloW0 | State.SloWC, "w" | "W"): return (State.SC, "ш")
            
            case (State.SloW0 | State.SloWC, ch) if is_consonant(ch):
                return (State.SC, "ш" + ct.get(ch, ch))
            case (State.SloW0 | State.SloWC, ch):
                return (State.S0, "ш" + ct.get(ch, ch))
            
            
            case (State.SupW0 | State.SupWC, Input.NUL): return (State.S0, "Ш")
            
            case (State.SupW0, Input.DEL): return (State.S0, "")
            case (State.SupWC, Input.DEL): return (State.SC, "")
            
            case (State.SupW0 | State.SupWC, "j"): return (State.SloJC, "Ш")
            case (State.SupW0 | State.SupWC, "J"): return (State.SupJC, "Ш")
            case (State.SupW0 | State.SupWC, "'"): return (State.SA, "Ш")
            case (State.SupW0 | State.SupWC, "q" | "Q"): return (State.SC, "Щ")
            case (State.SupW0 | State.SupWC, "w" | "W"): return (State.SC, "Ш")
            case (State.SupW0 | State.SupWC, ch) if is_consonant(ch):
                return (State.SC, "Ш" + ct.get(ch, ch))
            case (State.SupW0 | State.SupWC, ch):
                return (State.S0, "Ш" + ct.get(ch, ch))
            
            
            case (State.SloC0 | State.SloCC, Input.NUL): return (State.S0, "ц")
            
            case (State.SloC0, Input.DEL): return (State.S0, "")
            case (State.SloCC, Input.DEL): return (State.SC, "")
            
            case (State.SloC0 | State.SloCC, "j"): return (State.SloJC, "ц")
            case (State.SloC0 | State.SloCC, "J"): return (State.SupJC, "ц")
            case (State.SloC0 | State.SloCC, "'"): return (State.SA, "ц")
            case (State.SloC0 | State.SloCC, "h" | "H"): return (State.SC, "х")
            case (State.SloC0 | State.SloCC, "c" | "C"): return (State.SC, "ц")
            
            case (State.SloC0 | State.SloCC, ch) if is_consonant(ch):
                return (State.SC, "ц" + ct.get(ch, ch))
            case (State.SloC0 | State.SloCC, ch):
                return (State.S0, "ц" + ct.get(ch, ch))
            
            
            case (State.SupC0 | State.SupCC, Input.NUL): return (State.S0, "Ц")
            
            case (State.SupC0, Input.DEL): return (State.S0, "")
            case (State.SupCC, Input.DEL): return (State.SC, "")
            
            case (State.SupC0 | State.SupCC, "j"): return (State.SloJC, "Ц")
            case (State.SupC0 | State.SupCC, "J"): return (State.SupJC, "Ц")
            case (State.SupC0 | State.SupCC, "'"): return (State.SA, "Ц")
            case (State.SupC0 | State.SupCC, "h" | "H"): return (State.SC, "Х")
            case (State.SupC0 | State.SupCC, "C" | "C"): return (State.SC, "Ц")
            
            case (State.SupC0 | State.SupCC, ch) if is_consonant(ch):
                return (State.SC, "Ц" + ct.get(ch, ch))
            case (State.SupC0 | State.SupCC, ch):
                return (State.S0, "Ц" + ct.get(ch, ch))
            

    def _composition_preview_for(self, state: State) -> str:
        match state:
            case State.SloJ0 | State.SloJC: return "ј"
            case State.SupJ0 | State.SupJC: return "Ј"
            case State.SA: return "'"
            case State.SloJA: return "'ј"
            case State.SupJA: return "'Ј"
            case State.SloW0 | State.SloWC: return "ш"
            case State.SupW0 | State.SupWC: return "Ш"
            case State.SloC0 | State.SloCC: return "ц"
            case State.SupC0 | State.SupCC: return "Ц"
            case _: return ""

    def feed(self, c: str) -> str:
        state, out = self.next(c)
        
        # erase = "\b \b" * len(self.composition_preview)
        self.composition_preview = self._composition_preview_for(state)
        
        self.state = state
        # return erase + out + "\x1B[4m" + self.composition_preview + "\x1B[0m"
        return out
            
    def flush(self) -> str:
        return self.feed(Input.NUL)
    
    def erase(self) -> str:
        return self.feed(Input.DEL)
    

def getch() -> str:
    if os.name == "nt":
        import msvcrt
        return msvcrt.getwch()
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def main():
    t = Transliterator()
    print("Type: ")

    while True:
        ch = getch()

        if ch == "\x03":
            break

        if ch == "\r":
            sys.stdout.write(t.flush() + "\r\n")
            sys.stdout.flush()
            continue

        if ch in ("\x7F", "\x08"): # \x7F on POSIX, \0x08 on NT
            t.erase()
            sys.stdout.write("\b \b")
            sys.stdout.flush()
            continue

        out = t.feed(ch)

        sys.stdout.write(out)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
