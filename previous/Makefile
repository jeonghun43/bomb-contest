# Makefile - build a seeded variant of the bomb.
#
#   make SEED=20260215                    build ./bomb for that seed (offline)
#   make dist SEED=20260215               package what contestants receive
#   make verify FROM=1 TO=20              run the automated checks
#   make NOTIFY=1 BOMB_ID=<hex16> \       build a server-mode bomb that reports
#        SEED=... OUT=<dir>               to the record server
#   make clean / distclean
#
# OUT controls where generated data and the binary go, so several bombs can be
# built side by side without clobbering one another. The generator no longer
# writes into src/; bombdata.{h,c} live under $(OUT).

CC      := gcc
CFLAGS  := -O1 -g -Wall -no-pie -fno-stack-protector
PYTHON  := python3

SEED    ?= 0
FROM    ?= 1
TO      ?= 20
OUT     ?= build/seed-$(SEED)

# Server mode: report to the record daemon instead of writing a local log.
NOTIFY        ?= 0
BOMB_ID       ?=
NOTIFY_SOCKET ?= /run/bomblab/report.sock

BASE_SRCS := src/bomb.c src/phases.c src/support.c src/util.c
DATA_SRC  := $(OUT)/bombdata.c
HDRS      := src/bomb.h $(OUT)/bombdata.h

ifeq ($(NOTIFY),1)
CFLAGS  += -DNOTIFY -DNOTIFY_SOCKET='"$(NOTIFY_SOCKET)"'
BASE_SRCS += src/notify.c
GEN_ID   := --bomb-id $(BOMB_ID)
else
GEN_ID   :=
endif

SRCS := $(BASE_SRCS) $(DATA_SRC)

DISTDIR    := dist/bomb-$(SEED)
FORBIDDEN  := phases.c support.c util.c notify.c bombdata.h bombdata.c \
              solution.txt solution_secret.txt SOLUTION.md

.PHONY: all gen dist verify clean distclean

all: bomb

# The generator is cheap and must rerun whenever SEED/OUT/BOMB_ID changes, so
# it is a phony prerequisite rather than a file rule.
gen:
ifeq ($(NOTIFY),1)
	@test -n "$(BOMB_ID)" || { echo "NOTIFY=1 requires BOMB_ID=<hex16>"; exit 1; }
endif
	@$(PYTHON) tools/gen_bomb.py --seed $(SEED) --out $(OUT) $(GEN_ID)

bomb: gen $(HDRS) $(BASE_SRCS)
	$(CC) $(CFLAGS) -I$(OUT) -Isrc -o $(OUT)/bomb $(SRCS)
	@cp $(OUT)/bomb ./bomb

dist: bomb docs/README.md docs/PRIMER.md
	@rm -rf $(DISTDIR)
	@mkdir -p $(DISTDIR)
	@cp $(OUT)/bomb $(DISTDIR)/
	@cp src/bomb.c $(DISTDIR)/
	@cp docs/README.md docs/PRIMER.md $(DISTDIR)/
	@for f in $(FORBIDDEN); do \
	    if [ -e "$(DISTDIR)/$$f" ]; then \
	        echo "FAIL: forbidden file in package: $$f"; exit 1; \
	    fi; \
	done
	@echo "$(DISTDIR) ready:"
	@ls -1 $(DISTDIR)

verify:
	@bash tools/verify.sh $(FROM) $(TO)

clean:
	rm -f bomb bomb.log

distclean: clean
	rm -rf dist build src/bombdata.h src/bombdata.c tools/__pycache__
