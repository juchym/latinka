PREFIX ?= /usr
ADDONDIR ?= $(PREFIX)/lib/fcitx5
DATADIR ?= $(PREFIX)/share/fcitx5
# Where the Python modules and data are installed; the addon imports composer.py from here.
PYDIR ?= $(DATADIR)/udnc

PYTHON ?= python3
LIBPYTHON := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('INSTSONAME'))")

CXXFLAGS ?= -O2 -Wall -Wextra
CXXFLAGS += -std=c++20 -fPIC -fvisibility=hidden \
	$(shell pkg-config --cflags Fcitx5Core) \
	$(shell $(PYTHON)-config --includes) \
	-DUDNC_PYTHON_DIR='"$(PYDIR)"' -DUDNC_LIBPYTHON='"$(LIBPYTHON)"'
LDLIBS += $(shell pkg-config --libs Fcitx5Core) $(shell $(PYTHON)-config --embed --libs)

udnc.so: udnc.cpp
	$(CXX) $(CXXFLAGS) -shared -o $@ $< $(LDFLAGS) $(LDLIBS)

install: udnc.so
	install -Dm755 udnc.so $(DESTDIR)$(ADDONDIR)/udnc.so
	install -Dm644 udnc-addon.conf $(DESTDIR)$(DATADIR)/addon/udnc.conf
	install -Dm644 udnc-uk.conf $(DESTDIR)$(DATADIR)/inputmethod/udnc-uk.conf
	install -Dm644 udnc-ru.conf $(DESTDIR)$(DATADIR)/inputmethod/udnc-ru.conf
	install -Dm644 -t $(DESTDIR)$(PYDIR) ../composer.py ../rules.py ../lexicon.py
	install -Dm644 -t $(DESTDIR)$(PYDIR)/data ../data/*.rules ../data/*.loans $(wildcard ../data/*.db)

uninstall:
	rm -f $(DESTDIR)$(ADDONDIR)/udnc.so $(DESTDIR)$(DATADIR)/addon/udnc.conf \
		$(DESTDIR)$(DATADIR)/inputmethod/udnc-uk.conf $(DESTDIR)$(DATADIR)/inputmethod/udnc-ru.conf
	rm -rf $(DESTDIR)$(PYDIR)

clean:
	rm -f udnc.so

.PHONY: install uninstall clean
