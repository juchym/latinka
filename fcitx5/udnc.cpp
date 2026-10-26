// fcitx5 engine that drives the Python Composer from composer.py.

#include <Python.h>
#include <dlfcn.h>

#include <algorithm>
#include <cctype>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include <fcitx-utils/i18n.h>
#include <fcitx-utils/key.h>
#include <fcitx-utils/log.h>
#include <fcitx-utils/utf8.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/candidatelist.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputcontextproperty.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/inputmethodentry.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/text.h>

#ifndef UDNC_PYTHON_DIR
#error "UDNC_PYTHON_DIR must point to the directory containing composer.py"
#endif

namespace {

FCITX_DEFINE_LOG_CATEGORY(udnc_log, "udnc");
#define UDNC_ERROR() FCITX_LOGC(udnc_log, Error)

// Owned reference to a Python object.
struct PyRef {
    PyObject *p = nullptr;
    PyRef() = default;
    explicit PyRef(PyObject *p) : p(p) {}
    PyRef(PyRef &&other) noexcept : p(other.p) { other.p = nullptr; }
    PyRef(const PyRef &) = delete;
    PyRef &operator=(const PyRef &) = delete;
    ~PyRef() { Py_XDECREF(p); }
    explicit operator bool() const { return p != nullptr; }
};

std::string toStr(PyObject *obj) {
    const char *s = obj ? PyUnicode_AsUTF8(obj) : nullptr;
    if (!s) {
        PyErr_Print();
        return {};
    }
    return s;
}

std::string callStr(PyObject *obj, const char *method) {
    PyRef r(PyObject_CallMethod(obj, method, nullptr));
    return toStr(r.p);
}

std::vector<std::string> callStrList(PyObject *obj, const char *method) {
    PyRef r(PyObject_CallMethod(obj, method, nullptr));
    std::vector<std::string> out;
    if (!r || !PyList_Check(r.p)) {
        PyErr_Print();
        return out;
    }
    for (Py_ssize_t i = 0; i < PyList_Size(r.p); i++) {
        out.push_back(toStr(PyList_GetItem(r.p, i)));
    }
    return out;
}

void callVoid(PyObject *obj, const char *method, const char *arg = nullptr) {
    PyRef r(arg ? PyObject_CallMethod(obj, method, "s", arg)
                : PyObject_CallMethod(obj, method, nullptr));
    if (!r) {
        PyErr_Print();
    }
}

void callVoid(PyObject *obj, const char *method, int arg) {
    PyRef r(PyObject_CallMethod(obj, method, "i", arg));
    if (!r) {
        PyErr_Print();
    }
}

long callLong(PyObject *obj, const char *method) {
    PyRef r(PyObject_CallMethod(obj, method, nullptr));
    long value = r ? PyLong_AsLong(r.p) : 0;
    if (!r || PyErr_Occurred()) {
        PyErr_Print();
        return 0;
    }
    return value;
}

// One word being composed in one language.
class Word {
public:
    Word(PyObject *cls, const std::string &lang)
        : c_(cls ? PyObject_CallFunction(cls, "s", lang.c_str()) : nullptr) {
        if (cls && !c_) {
            PyErr_Print();
        }
    }

    bool ok() const { return static_cast<bool>(c_); }
    bool empty() { return raw().empty(); }
    std::string raw() { return callStr(c_.p, "raw"); }
    void setContext(const std::string &prev) { callVoid(c_.p, "set_context", prev.c_str()); }
    void push(const std::string &ch) { callVoid(c_.p, "push", ch.c_str()); selected = 0; }
    void pop() { callVoid(c_.p, "pop"); selected = 0; }
    void del() { callVoid(c_.p, "delete"); selected = 0; }
    void move(int delta) { callVoid(c_.p, "move", delta); }
    void moveTo(int position) { callVoid(c_.p, "move_to", position); } // -1: the end
    bool canHush() { return callLong(c_.p, "can_hush") != 0; }
    void hush() { callVoid(c_.p, "hush"); selected = 0; } // c → č, s → š, z → ž, st → šť
    size_t cursor() { return static_cast<size_t>(callLong(c_.p, "cursor")); } // in characters
    void clear() { callVoid(c_.p, "clear"); selected = 0; }
    void commit(const std::string &text) { callVoid(c_.p, "commit", text.c_str()); selected = 0; } // and clear
    const std::vector<std::string> &candidates() {
        candidates_ = callStrList(c_.p, "candidates");
        return candidates_;
    }

    size_t selected = 0;

private:
    PyRef c_;
    std::vector<std::string> candidates_;
};

class UdncState : public fcitx::InputContextProperty {
public:
    explicit UdncState(PyObject *cls) : cls_(cls) {}

    Word &word(const std::string &lang) {
        auto it = words_.find(lang);
        if (it == words_.end()) {
            it = words_.emplace(lang, std::make_unique<Word>(cls_, lang)).first;
        }
        return *it->second;
    }

    Word *current = nullptr; // the word of the active input method
    std::string last;        // last character typed or committed, if known
    bool altGrTap = false;   // AltGr pressed while composing, with no other key since

private:
    PyObject *cls_;
    std::unordered_map<std::string, std::unique_ptr<Word>> words_;
};

class UdncEngine;

class UdncCandidate : public fcitx::CandidateWord {
public:
    UdncCandidate(UdncEngine *engine, size_t index, const std::string &text)
        : fcitx::CandidateWord(fcitx::Text(text)), engine_(engine), index_(index) {}
    void select(fcitx::InputContext *ic) const override;

private:
    UdncEngine *engine_;
    size_t index_;
};

class UdncEngine : public fcitx::InputMethodEngineV2 {
public:
    explicit UdncEngine(fcitx::Instance *instance)
        : instance_(instance),
          factory_([this](fcitx::InputContext &) { return new UdncState(cls_.p); }) {
        initPython();
        instance_->inputContextManager().registerProperty("udncState", &factory_);
    }

    void activate(const fcitx::InputMethodEntry &entry, fcitx::InputContextEvent &event) override {
        auto *state = event.inputContext()->propertyFor(&factory_);
        state->current = &state->word(language(entry));
    }

    void keyEvent(const fcitx::InputMethodEntry &entry, fcitx::KeyEvent &event) override {
        auto *ic = event.inputContext();
        // Password and other sensitive fields: type straight through, never show or convert.
        if (ic->capabilityFlags().testAny(fcitx::CapabilityFlags{fcitx::CapabilityFlag::PasswordOrSensitive})) {
            return;
        }
        // A tap of AltGr (or right Alt) after c, s, z or st works like the háček key: s + tap → š.
        bool altGr = event.key().sym() == FcitxKey_ISO_Level3_Shift || event.key().sym() == FcitxKey_Alt_R;
        if (event.isRelease()) {
            auto *state = ic->propertyFor(&factory_);
            if (altGr && state->altGrTap) {
                state->altGrTap = false;
                Word &word = state->word(language(entry));
                if (word.ok() && !word.empty() && word.canHush()) {
                    word.hush();
                    updateUI(ic, word);
                    event.filterAndAccept();
                }
            }
            return;
        }
        {
            auto *state = ic->propertyFor(&factory_);
            Word &word = state->word(language(entry));
            state->altGrTap = altGr && word.ok() && !word.empty() && word.canHush();
            if (state->altGrTap) {
                // Take the press too, so the app never sees a press without its release.
                event.filterAndAccept();
                return;
            }
        }
        auto *state = ic->propertyFor(&factory_);
        Word &word = state->word(language(entry));
        state->current = &word;
        if (!word.ok()) {
            return;
        }
        const auto key = event.key();

        // Modifiers, lock keys and AltGr don't touch the composition.
        if (key.isModifier() || key.check(FcitxKey_Caps_Lock) || key.check(FcitxKey_Num_Lock) ||
            key.check(FcitxKey_Scroll_Lock) || key.check(FcitxKey_Shift_Lock) ||
            key.sym() == FcitxKey_ISO_Level3_Shift || key.sym() == FcitxKey_ISO_Level5_Shift) {
            return;
        }

        if (key.states().testAny(fcitx::KeyStates{fcitx::KeyState::Ctrl, fcitx::KeyState::Alt,
                                                  fcitx::KeyState::Super})) {
            commitSelected(ic, word);
            state->last.clear();
            return;
        }

        if (!word.empty()) {
            // Down/Tab: next candidate, Up/Shift+Tab: previous, as in Mozc.
            bool next = key.check(FcitxKey_Down) || key.check(FcitxKey_Tab);
            bool previous = key.check(FcitxKey_Up) || key.check(FcitxKey_ISO_Left_Tab, fcitx::KeyState::Shift) ||
                            key.check(FcitxKey_Tab, fcitx::KeyState::Shift);
            if (next || previous) {
                size_t n = word.candidates().size();
                word.selected = next ? (word.selected + 1) % n : (word.selected + n - 1) % n;
                updateUI(ic, word);
                event.filterAndAccept();
                return;
            }
            if (key.check(FcitxKey_Return) || key.check(FcitxKey_KP_Enter)) {
                // Commit the word only, as in Mozc: no new line or message sent.
                commitSelected(ic, word);
                event.filterAndAccept();
                return;
            }
            if (key.check(FcitxKey_Escape)) {
                // Keep the Latin text as typed, e.g. for English words.
                commit(ic, word, word.raw());
                event.filterAndAccept();
                return;
            }
            // Editing inside the preedit, as in Mozc.
            if (key.check(FcitxKey_BackSpace) || key.check(FcitxKey_Delete) || key.check(FcitxKey_Left) ||
                key.check(FcitxKey_Right) || key.check(FcitxKey_Home) || key.check(FcitxKey_End)) {
                if (key.check(FcitxKey_BackSpace)) {
                    word.pop();
                } else if (key.check(FcitxKey_Delete)) {
                    word.del();
                } else if (key.check(FcitxKey_Left)) {
                    word.move(-1);
                } else if (key.check(FcitxKey_Right)) {
                    word.move(1);
                } else if (key.check(FcitxKey_Home)) {
                    word.moveTo(0);
                } else {
                    word.moveTo(-1);
                }
                updateUI(ic, word);
                event.filterAndAccept();
                return;
            }
        }

        uint32_t ucs = fcitx::Key::keySymToUnicode(key.sym());
        // Latin letters, with or without diacritics (č, š, ž, …), and the apostrophe.
        bool latinLetter = (ucs < 0x80 && std::isalpha(static_cast<int>(ucs))) ||
                           (ucs >= 0xC0 && ucs <= 0x24F && ucs != 0xD7 && ucs != 0xF7);
        bool wordChar = latinLetter || ucs == '\'';
        // While composing, x right after c, s, z or st makes them hushing: cx → č, sx → š, stx → šť.
        // Anywhere else x is an ordinary letter (кс).
        if ((ucs == 'x' || ucs == 'X') && !word.empty() && word.canHush()) {
            word.hush();
            updateUI(ic, word);
            event.filterAndAccept();
            return;
        }
        if (wordChar && !key.states().testAny(fcitx::KeyStates{fcitx::KeyState::Ctrl})) {
            if (word.empty()) {
                word.setContext(contextBefore(ic, state));
            }
            word.push(fcitx::utf8::UCS4ToUTF8(ucs));
            updateUI(ic, word);
            event.filterAndAccept();
            return;
        }

        // A word boundary: commit, then let the key through.
        commitSelected(ic, word);
        state->last = (ucs >= 0x20 && ucs != 0x7f) ? fcitx::utf8::UCS4ToUTF8(ucs) : "";
    }

    void deactivate(const fcitx::InputMethodEntry &entry, fcitx::InputContextEvent &event) override {
        auto *ic = event.inputContext();
        commitSelected(ic, ic->propertyFor(&factory_)->word(language(entry)));
    }

    void reset(const fcitx::InputMethodEntry &entry, fcitx::InputContextEvent &event) override {
        auto *ic = event.inputContext();
        commitSelected(ic, ic->propertyFor(&factory_)->word(language(entry)));
    }

    void commitCandidate(fcitx::InputContext *ic, size_t index) {
        Word *word = ic->propertyFor(&factory_)->current;
        if (!word) {
            return;
        }
        const auto &candidates = word->candidates();
        if (index < candidates.size()) {
            commit(ic, *word, candidates[index]);
        }
    }

private:
    // "udnc-uk" -> "uk"
    static std::string language(const fcitx::InputMethodEntry &entry) {
        const std::string &name = entry.uniqueName();
        auto dash = name.rfind('-');
        return dash == std::string::npos ? "uk" : name.substr(dash + 1);
    }

    void initPython() {
        // Make libpython's symbols global so Python extension modules can resolve them.
        dlopen(UDNC_LIBPYTHON, RTLD_NOW | RTLD_GLOBAL | RTLD_NOLOAD);

        if (!Py_IsInitialized()) {
            PyConfig config;
            PyConfig_InitIsolatedConfig(&config);
            config.install_signal_handlers = 0;
            PyStatus status = Py_InitializeFromConfig(&config);
            PyConfig_Clear(&config);
            if (PyStatus_Exception(status)) {
                UDNC_ERROR() << "Failed to initialize Python: "
                             << (status.err_msg ? status.err_msg : "unknown error");
                return;
            }
        }

        PyObject *sysPath = PySys_GetObject("path"); // borrowed
        PyRef dir(PyUnicode_FromString(UDNC_PYTHON_DIR));
        if (!sysPath || !dir || PyList_Insert(sysPath, 0, dir.p) < 0) {
            PyErr_Print();
            return;
        }

        PyRef mod(PyImport_ImportModule("composer"));
        if (!mod) {
            UDNC_ERROR() << "Failed to import composer.py from " UDNC_PYTHON_DIR;
            PyErr_Print();
            return;
        }
        cls_.p = PyObject_GetAttrString(mod.p, "Composer");
        if (!cls_) {
            PyErr_Print();
        }
    }

    // The character before the cursor, so e.g. "j" after an existing "н"
    // produces "ь". Falls back to the last key we saw.
    std::string contextBefore(fcitx::InputContext *ic, UdncState *state) {
        if (ic->capabilityFlags().test(fcitx::CapabilityFlag::SurroundingText)) {
            const auto &st = ic->surroundingText();
            if (st.isValid()) {
                unsigned int pos = std::min(st.cursor(), st.anchor());
                if (pos == 0) {
                    return {};
                }
                const std::string &text = st.text();
                auto start = fcitx::utf8::nextNChar(text.begin(), pos - 1);
                return std::string(start, fcitx::utf8::nextChar(start));
            }
        }
        return state->last;
    }

    void commitSelected(fcitx::InputContext *ic, Word &word) {
        if (!word.ok() || word.empty()) {
            return;
        }
        const auto &candidates = word.candidates();
        commit(ic, word, candidates.at(std::min(word.selected, candidates.size() - 1)));
    }

    void commit(fcitx::InputContext *ic, Word &word, const std::string &text) {
        word.commit(text); // remembers Latin or Cyrillic for the next word
        updateUI(ic, word);
        if (!text.empty()) {
            ic->commitString(text);
            auto lastChar = fcitx::utf8::nextNChar(text.begin(), fcitx::utf8::length(text) - 1);
            ic->propertyFor(&factory_)->last.assign(lastChar, text.end());
        }
    }

    void updateUI(fcitx::InputContext *ic, Word &word) {
        auto &panel = ic->inputPanel();
        panel.reset();
        const auto &candidates = word.empty() ? std::vector<std::string>{} : word.candidates();
        if (!candidates.empty()) {
            // The preedit shows the Latin text as typed; the readings are in the candidate list.
            const std::string preview = word.raw();
            fcitx::Text text;
            text.append(preview, fcitx::TextFormatFlag::Underline);
            text.setCursor(fcitx::utf8::ncharByteLength(preview.begin(), word.cursor()));
            if (ic->capabilityFlags().test(fcitx::CapabilityFlag::Preedit)) {
                panel.setClientPreedit(text);
            } else {
                panel.setPreedit(text);
            }

            auto list = std::make_unique<fcitx::CommonCandidateList>();
            list->setPageSize(static_cast<int>(candidates.size()));
            list->setLabels(std::vector<std::string>(candidates.size(), ""));
            list->setLayoutHint(fcitx::CandidateLayoutHint::Vertical);
            for (size_t i = 0; i < candidates.size(); i++) {
                list->append<UdncCandidate>(this, i, candidates[i]);
            }
            list->setGlobalCursorIndex(static_cast<int>(word.selected));
            panel.setCandidateList(std::move(list));
        }
        ic->updatePreedit();
        ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
    }

    fcitx::Instance *instance_;
    PyRef cls_;
    fcitx::FactoryFor<UdncState> factory_;
};

void UdncCandidate::select(fcitx::InputContext *ic) const { engine_->commitCandidate(ic, index_); }

class UdncFactory : public fcitx::AddonFactory {
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new UdncEngine(manager->instance());
    }
};

} // namespace

FCITX_ADDON_FACTORY_V2_BACKWARDS(udnc, UdncFactory)
