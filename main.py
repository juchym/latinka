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
    SA = 4 # afther apostrophe
    SJA = 5 # afther j after apostrophe

class Transliterator:

    def __init__(self):
        self.state = State.S0

    def next(self, c):
        match (self.state, c):
            case (State.S0, "j"): return (State.SJ0, "ј")
            case (State.SC, "'"): return (State.SA, "'")
            case (State.SC, "j"): return (State.SJC, "ј")
            case (State.SA, "j"): return (State.SJA, "ј")

            case (State.S0 | State.SC | State.SA, ch) if is_consonant(ch):
                return (State.SC, conversion_table.get(ch, ch))
            case (State.S0 | State.SC | State.SA, ch):
                return (State.S0, conversion_table.get(ch, ch))
            
            case (State.SJ0 | State.SJA, ch) if is_consonant(ch):
                return (State.SC, f"\bй{conversion_table.get(ch, ch)}")
            case (State.SJC, ch) if is_consonant(ch):
                return f"\bь{ch}"
            
            case (State.SJ0, "j"): return (State.S0, "\bй")
            case (State.SJC, "j"): return (State.S0, "\bь")

            case (State.SJ0 | State.SJC | State.SJA, "a"):
                return (State.S0, "\bя")
            case (State.SJ0 | State.SJC | State.SJA, "u"):
                return (State.S0, "\bю")
            case (State.SJ0 | State.SJC | State.SJA, "e"):
                return (State.S0, "\bє")
            
            case (State.SJ0 | State.SJA, "i"): return (State.S0, "\bї")
            case (State.SJC, "i"): return (State.S0, "\b'ї")

            case (State.SJA, "o"): return (State.S0, "\b\bйо")

            case (State.SJ0 | State.SJA, ch):
                return (State.S0, f"\bй{conversion_table.get(ch, ch)}")
            case (State.SJC, ch):
                return (State.S0, f"\bь{conversion_table.get(ch, ch)}")

    def feed(self, c):
        self.state, out = self.next(c)
        return out

    def flush(self):
        match self.state:
            case State.SJ0:
                self.state = State.S0
                return "\bй"
            case State.SJC:
                self.state = State.S0
                return "\bь"
            case State.SA:
                self.state = State.S0
                return "\b'"
            case State.SJA:
                self.state = State.S0
                return "й"
            case _:
                return ""

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
