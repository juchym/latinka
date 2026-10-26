import tempfile
import unittest
from pathlib import Path
from unittest import mock

from composer import Composer, is_hush_key, transliterate
from lexicon import Lexicon

FIXTURES = Path(__file__).parent / "fixtures"


def type_keys(c: Composer, keys: str) -> None:
    """Type keys into a composer, with x after c, s, z or st as the hushing key (sx → š)."""
    for ch in keys:
        c.hush() if is_hush_key(ch) and c.can_hush() else c.push(ch)
UK = Lexicon.load(FIXTURES / "uk.words")
RU = Lexicon.load(FIXTURES / "ru.words")


class UkrainianTest(unittest.TestCase):

    def check(self, latin: str, cyrillic: str):
        self.assertEqual(transliterate(latin, "uk", UK), cyrillic)

    def test_loanwords(self):
        self.check("Na photographiji text", "На фотографії текст")
        self.check("Na photographii text", "На фотографії текст")
        self.check("muzyka", "музика")
        self.check("orthographija", "орфографія")
        self.check("theorija", "теорія")
        self.check("automobilj", "автомобіль")
        self.check("automobil", "автомобіль")
        self.check("film", "фільм")
        self.check("cultura", "культура")

    def test_latin_ia(self):
        for latin in ("theoria", "theorija"):
            self.check(latin, "теорія")
        for latin in ("orthographia", "orthographija"):
            self.check(latin, "орфографія")
        for latin in ("photographia", "photographija"):
            self.check(latin, "фотографія")
        self.check("dieta", "дієта")
        self.check("klient", "клієнт")
        self.check("client", "клієнт")
        self.check("dialog", "діалог")  # native іа is still a reading

    def test_apostrophe_after_labials(self):
        self.check("pjatj", "п'ять")
        self.check("mjaso", "м'ясо")
        self.check("simja", "сім'я")
        self.check("Kompjuter", "Комп'ютер")
        self.assertEqual(transliterate("pjatj", "uk", Lexicon()), "п'ять")  # native, no dictionary needed
        self.check("svjato", "свято")  # labial after a consonant: no apostrophe
        self.check("burja", "буря")
        self.check("burjan", "бур'ян")
        self.check("podvirja", "подвір'я")

    def test_apostrophe_from_lexicon(self):
        self.check("zjasuvaty", "з'ясувати")  # after a prefix
        self.check("vidjednaty", "від'єднати")
        self.check("kjanti", "к'янті")  # loanwords
        self.check("mysxjak", "миш'як")
        self.check("karjera", "кар'єра")
        self.check("bjudzxet", "бюджет")  # no apostrophe: softening; б'юджет is only a variant
        self.check("Vorobjov", "Воробйов")
        self.check("sjogodni", "сьогодні")

    def test_splits_without_escapes(self):
        self.check("najuljublenisxyj", "найулюбленіший")  # й + у, formerly najj
        self.check("Njuton", "Ньютон")  # ь + ю
        self.check("nachvardija", "нацгвардія")  # ц + г, formerly cch
        self.check("nacguardia", "нацгвардія")  # Romance gu: guardia
        self.check("batjusxcxyn", "батюшчин")  # ш + ч
        self.check("miljjon", "мільйон")  # j after a consonant is ь, then jo is йо

    def test_proper_nouns_need_a_capital(self):
        self.check("burjan", "бур'ян")  # the surname Бурян is ignored
        c = Composer("uk", UK)
        for ch in "Burjan":
            c.push(ch)
        self.assertEqual(c.candidates(), ["Бур'ян", "Бурян", "Burjan"])  # common words first

    def test_source_language_spellings(self):
        for latin, cyrillic in [("atelier", "ательє"), ("bureau", "бюро"), ("budget", "бюджет"),
                                ("blitzkrieg", "бліцкриг"), ("million", "мільйон"), ("cognac", "коньяк"),
                                ("restaurant", "ресторан"), ("football", "футбол"), ("Bordeaux", "Бордо"),
                                ("chauffeur", "шофер"), ("jockey", "жокей"), ("meeting", "мітинг")]:
            self.check(latin, cyrillic)

    def test_lowercase_names_come_after_native(self):
        c = Composer("uk", UK)
        for ch in "odesa":
            c.push(ch)
        self.assertEqual(c.candidates(), ["одеса", "Одеса", "odesa"])

    def test_etymological_infinitives(self):
        self.check("choditi", "ходити")
        self.check("siditi", "сидіти")
        self.check("biti", "бити")  # beats the native біті because бити is an infinitive
        self.check("choditisja", "ходитися")
        self.check("kimnati", "кімнаті")  # not an infinitive: the native reading stays

    def test_pinyin(self):
        self.check("Tiananmen, Xi Jinping, Mao Zedong, Guangzhou, Shenzhen, Shanghai",
                   "Тяньаньмень, Сі Цзіньпін, Мао Цзедун, Гуанчжоу, Шеньчжень, Шанхай")

    def test_loanword_list(self):
        self.check("bureau", "бюро")
        self.check("chauffeurom", "шофером")  # a list entry plus a native ending
        self.check("nacguardia", "нацгвардія")  # a list entry inside a compound
        self.check("Tiananmen", "Тяньаньмень")
        self.check("tiananmen", "Тяньаньмень")  # listed words win even in lowercase

    def test_user_loanword_list(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("composer.USER_DATA", Path(tmp)):
            (Path(tmp) / "uk.loans").write_text("bureau канцелярія\n", encoding="utf-8")
            self.check("bureau", "канцелярія")  # overrides the installed entry, no restart needed
        self.check("bureau", "бюро")

    def test_loanword_with_several_forms(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("composer.USER_DATA", Path(tmp)):
            (Path(tmp) / "uk.loans").write_text("spaghetti спагеті спагетті\n", encoding="utf-8")
            c = Composer("uk", UK)
            for ch in "spaghetti":
                c.push(ch)
            self.assertEqual(c.candidates()[:2], ["спагеті", "спагетті"])  # standard first, then non-standard

    def test_latin_tio(self):
        self.check("natia", "нація")
        self.check("revolutia", "революція")
        self.check("illustratia", "ілюстрація")
        self.check("partia", "партія")  # real -тія words stay

    def test_latin_eu(self):
        self.check("Europa", "Європа")
        self.check("neuron", "нейрон")
        self.check("pneumonia", "пневмонія")

    def test_case(self):
        self.check("TEXT", "ТЕКСТ")
        self.check("Text", "Текст")

    def test_native(self):
        self.check("kinj", "кінь")
        self.check("pidjizd", "під'їзд")
        self.check("pryvit, chlib!", "привіт, хліб!")
        self.check("milj'jon", "мільйон")

    def test_unknown_word_falls_back_to_native(self):
        self.check("xyz", "ксиз")
        self.check("text", "текст")
        self.assertEqual(transliterate("text", "uk", Lexicon()), "текст")
        self.assertEqual(transliterate("photo", "uk", Lexicon()), "пгото")

    def test_candidates_native_first(self):
        c = Composer("uk", UK)
        for ch in "gala":
            c.push(ch)
        self.assertEqual(c.candidates(), ["гала", "ґала", "gala"])  # native ґала isn't a word: гала, its ґ twin
        c.pop()
        self.assertEqual(c.candidates(), ["ґал", "gal"])  # nothing real: the native reading

    def test_editing_at_the_cursor(self):
        c = Composer("uk", UK)
        for ch in "pryvt":
            c.push(ch)
        c.move(-1)
        c.push("i")  # pryv|t -> pryvi|t
        self.assertEqual((c.raw(), c.cursor(), c.candidates()[0]), ("pryvit", 5, "привіт"))
        c.move_to(0)
        c.delete()  # |pryvit -> |ryvit
        c.move_to(-1)
        c.pop()  # ryvit| -> ryvi|
        self.assertEqual((c.raw(), c.cursor()), ("ryvi", 4))
        c.move(10)
        self.assertEqual(c.cursor(), 4)  # clamped to the end

    def test_syllabic_rules_need_a_following_consonant(self):
        self.check("vlk", "вовк")
        c = Composer("uk", UK)
        for ch in "dobre":
            c.push(ch)
        self.assertEqual(c.candidates(), ["добре", "dobre"])  # no добере: the r is followed by a vowel

    def test_upturned_g(self):
        c = Composer("uk", UK)
        c.push("g")
        self.assertEqual(c.candidates()[0], "ґ")  # g is ґ, as in Czech
        c.clear()
        for ch in "photographii":
            c.push(ch)
        self.assertEqual(c.candidates()[:2], ["фотографії", "фотоґрафії"])  # Latin g → г, and its ґ twin
        c.clear()
        for ch in "holova":
            c.push(ch)
        self.assertNotIn("ґолова", c.candidates())  # native h → г has no twin

    def test_hacek_key(self):
        c = Composer("uk", UK)
        type_keys(c, "sxkola")
        self.assertEqual((c.raw(), c.candidates()[0]), ("škola", "школа"))  # the preedit shows š
        c.clear()
        type_keys(c, "sxcxastja")
        self.assertEqual(c.candidates()[0], "щастя")  # šč is щ
        c.clear()
        type_keys(c, "stxastja")
        self.assertEqual((c.raw(), c.candidates()[0]), ("šťastja", "щастя"))  # stx marks both: šť is щ
        c.clear()
        type_keys(c, "tax")
        self.assertEqual(c.raw(), "tax")  # elsewhere x is a letter (кс)

    def test_latin_mode(self):
        c = Composer("uk", UK)
        type_keys(c, "pryvit")
        c.commit("pryvit")  # Escape: committed as Latin
        type_keys(c, "kinj")
        self.assertEqual(c.candidates()[:2], ["kinj", "кінь"])  # Latin mode: Latin first
        c.commit("kinj")  # Space: still Latin
        type_keys(c, "hlib")
        c.commit(c.candidates()[1])  # Tab to Cyrillic, back to Cyrillic mode
        type_keys(c, "kinj")
        self.assertEqual(c.candidates()[0], "кінь")

    def test_laughter(self):
        self.check("ahahahaha", "ахахахаха")
        self.check("Hahaha", "Хахаха")
        self.check("hihihi", "хіхіхі")
        self.check("ahah", "ахах")
        self.check("ahahhaha", "ахаххаха")
        c = Composer("uk", UK)
        for ch in "hehehe":
            c.push(ch)
        self.assertEqual(c.candidates()[:2], ["хехехе", "хєхєхє"])
        c.clear()
        for ch in "ehehe":
            c.push(ch)
        self.assertEqual(c.candidates()[:4], ["ехехе", "ехєхє", "єхєхє", "єхехе"])
        self.check("aha", "ага")  # a single h + vowel is a word, not laughter

    def test_extra_candidates(self):
        c = Composer("uk", UK)
        for ch in "he":
            c.push(ch)
        self.assertEqual(c.candidates()[1], "хє")  # `+he хє` in uk.loans: offered, not first

    def test_initial_j_offers_both_contexts(self):
        c = Composer("uk", UK)
        for ch in "jsja":
            c.push(ch)
        self.assertEqual(c.candidates()[:2], ["йся", "ься"])

    def test_single_j_offers_both_letters(self):
        c = Composer("uk", UK)
        c.push("j")
        self.assertEqual(c.candidates(), ["й", "ь", "j"])
        c.clear()
        c.set_context("н")
        c.push("J")
        self.assertEqual(c.candidates(), ["Ь", "Й", "J"])

    def test_context_from_surrounding_text(self):
        c = Composer("uk", UK)
        c.set_context("н")
        c.push("j")
        self.assertEqual(c.candidates(), ["ь", "й", "j"])


class RussianTest(unittest.TestCase):

    def check(self, latin: str, cyrillic: str):
        self.assertEqual(transliterate(latin, "ru", RU), cyrillic)

    def test_native(self):
        self.check("eto text", "это текст")
        self.check("poet", "поэт")
        self.check("jestj", "есть")
        self.check("n'ja", "нъя")
        self.check("pod'jezd", "подъезд")

    def test_lexicon_alternatives(self):
        self.check("statja", "статья")
        self.check("platje", "платье")
        self.check("hobbi", "хобби")
        self.check("system", "сыстем")  # not in the fixture: native reading
        self.check("systema", "система")
        self.check("orthographija", "орфография")
        self.check("automobilj", "автомобиль")
        self.check("automobil", "автомобиль")
        self.check("film", "фильм")
        self.check("cultura", "культура")
        self.check("theoria", "теория")
        self.check("dieta", "диета")
        self.check("dialog", "диалог")
        self.check("Europa", "Европа")
        self.check("neuron", "нейрон")

    def test_candidates_by_frequency(self):
        c = Composer("ru", RU)
        for ch in "mer":
            c.push(ch)
        self.assertEqual(c.candidates(), ["мер", "мэр", "mer"])


if __name__ == "__main__":
    unittest.main()
