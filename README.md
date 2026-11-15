# UDNC

A Latin-script input method for Ukrainian and Russian. You type in Latin letters and get Cyrillic. Loanwords can be typed in their Latin spelling:

    Na photographiji text  →  На фотографії текст

Each word stays in the preedit (the Latin text, underlined) until a space or punctuation, and then the best reading is committed. In fcitx5, while a word is being composed:

- **Tab** / **↓**, **Shift+Tab** / **↑**: move through the readings in the candidate list.
- **Enter**: commit the selected reading only (no new line). **Escape**: commit the Latin text as typed.
- **←** / **→**, **Home** / **End**, **Backspace** / **Delete**: edit the word.
- **x** right after c, s, z or st, a tap of **AltGr**, or **AltGr** held with s/c/z: make the letter hushing (`sxkola`, `cxas`, `stxastja` → школа, час, щастя). Holding AltGr needs Right Alt set as the 3rd-level key in the keyboard options.

Committing the Latin text switches to **Latin mode**: following words offer Latin first, until you pick a Cyrillic reading again. Password fields get raw keys.

## How it works

- `data/<lang>.rules` holds the transliteration tables. Each row is `ctx latin cyrillic cost` (the format is described in `rules.py`).
  - Native rules have cost 0 and are applied with longest match. `x` is always `кс`; `х` is typed as `ch`. ш, ч, ж, щ are š, č, ž, šč/šť, typed with `x` right after the letter (`sx` → š, `stx` → šť) or a tap of AltGr; `w` is в, `q` is к and `g` is ґ, as in Czech (г is `h`).
  - Alternatives have cost 1 or more and only win when they make a real word: the Greco-Latin correspondences of international words (`ph→ф`, `th→т/ф`, `qu→кв`, `tia→ція`, …) and the etymological spellings (`i→и`, infinitives in `-ti`, syllabic `l`/`r`: `vlk` → вовк).
- `data/<lang>.loans` lists words from living languages in their source spelling (`bureau бюро`, `Tiananmen Тяньаньмень`). Entries also match inside longer words, so endings and compounds work (`chauffeurom` → шофером). A line can list several forms (`spaghetti спагеті спагетті`, offered in that order); a line starting with `+` only adds candidates after the usual first one (`+he хє`). Your own additions go in `~/.local/share/udnc/<lang>.loans`, which is read after the installed list and needs no restart.
- `rules.py` builds every reading of a word and keeps the ones the lexicon contains. A native reading that is a real word always comes first; alternatives are ranked by how many rules they bend against how frequent the word is. After the real words come readings offered even when they aren't known words: a guess with the strong rules (`phridon` → фрідон), the plain native reading, and the other ways to read each `j` + vowel after a consonant (`tjanjanjmenj` → тяняньмень, тян'яньмень, тяньаньмень…).
- `tools/check_examples.py` scores a file of example spellings (`latin<TAB>cyrillic<TAB>tags`, by default `examples/etymology.tsv`, which isn't part of the repository).
- `lexicon.py` looks words up in `data/<lang>.db`, an SQLite database of Cyrillic word forms and their frequencies. It's queried on disk, so it uses almost no memory and opens instantly.
- `composer.py` holds the word buffer that every front end uses.

## Dictionaries

Without a `data/<lang>.db` file only native readings are produced. To build one from word lists (one `word [count]` per line), for example a full form list plus a frequency list (counts from several sources are added up):

    python tools/build_lexicon.py uk vesum_forms.txt uk_freq.txt
    python tools/build_lexicon.py ru opencorpora_forms.txt ru_freq.txt

Possible sources, both offering full word-form lists (check their licences first):
- [FrequencyWords](https://github.com/hermitdave/FrequencyWords): frequency lists for uk and ru.
- [VESUM / dict_uk](https://github.com/brown-uk/dict_uk): a full Ukrainian word-form dictionary.

## fcitx5

    make -C fcitx5 && sudo make -C fcitx5 install
    pkill fcitx5    # on KDE Wayland, KWin starts it again; elsewhere: fcitx5 -r -d

Then add "Ukrainian (UDNC)" and/or "Russian (UDNC)" under System Settings → Input Method. On KDE Wayland, select "Fcitx 5 Wayland Launcher" under System Settings → Keyboard → Virtual Keyboard.

- **Updating:** after changing the code, rules or dictionaries, run `sudo make -C fcitx5 install` again and restart fcitx5. Your own `~/.local/share/udnc/<lang>.loans` needs no reinstall.
- **Development:** build with `make -C fcitx5 PYDIR=$PWD` so the addon loads the modules straight from the repo.

## Other front ends

    python main.py [uk|ru]    # terminal demo
    python ibus.py [uk|ru]    # IBus engine

## Tests

    python -m unittest

`tests/test_rules.py` checks the Ukrainian table against the original hand-written FSM (`tests/fsm_oracle.py`).
