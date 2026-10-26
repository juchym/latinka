import os
import sys

from composer import Composer, is_hush_key, is_word_char


def getch() -> str:
    if os.name == "nt":
        import msvcrt
        return msvcrt.getwch()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else "uk"
    c = Composer(lang)
    shown = ""  # preedit currently on screen
    last = ""   # last committed character, the context for the next word

    def show(text: str) -> None:
        nonlocal shown
        sys.stdout.write("\b \b" * len(shown) + "\x1B[4m" + text + "\x1B[0m")
        sys.stdout.flush()
        shown = text

    def commit(text: str) -> None:
        nonlocal last
        show("")
        sys.stdout.write(text)
        if text:
            last = text[-1]
        c.commit(text)

    print(f"Type ({lang}, Ctrl+C to quit): ")

    while True:
        ch = getch()

        if ch == "\x03":
            break

        if ch in ("\x7F", "\x08"): # \x7F on POSIX, \0x08 on NT
            if c.raw():
                c.pop()
                show(c.candidates()[0] if c.raw() else "")
            else:
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue

        if is_hush_key(ch) and c.raw() and c.can_hush():
            c.hush()
            show(c.candidates()[0])
            continue

        if is_word_char(ch):
            if not c.raw():
                c.set_context(last)
            c.push(ch)
            show(c.candidates()[0])
            continue

        commit(c.candidates()[0] if c.raw() else "")
        sys.stdout.write("\r\n" if ch == "\r" else ch)
        last = ch
        sys.stdout.flush()


if __name__ == "__main__":
    main()
