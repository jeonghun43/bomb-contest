# Makefile - Bomb Lab practice bank (specs/003-practice-bank).
#
# Every bomb is compiled inside the bomblab-gcc48 container, the original CMU
# bomb's own compiler (GCC 4.8.1). Build the image once per machine:
#
#   make toolchain
#
# Bombs:
#   make bomb KIND=cmu SEED=7                 build/cmu-7/bomb, copied to ./bomb
#   make bomb KIND=drill:d3 SEED=7            build/drill-d3-7/bomb
#   make bomb KIND=cmu SEED=7 FORCE="p3=switch_dd p6=list"
#                                             pin variant families
#   make bomb KIND=cmu SEED=7 NOTIFY=1 BOMB_ID=<hex16> OUT=<dir>
#                                             server-mode bomb
#   make dist KIND=cmu SEED=7                 what a student receives
#   make kinds                                list every kind
#
# Verification:
#   make verify                 every kind and variant (5 seeds), runtime, parity
#   make verify SEEDS=2 VKIND="cmu drill:d3"
#   make parity                 CMU-structure bombs vs the original (needs ref/)
#   make calib                  toolchain calibration (dev machine, needs ref/)
#   make selftest               practice server end to end, no root
#   make hints                  regenerate server/HINTS.md (operators' hint list)

PYTHON        ?= python3
IMAGE         ?= bomblab-gcc48

KIND          ?=
SEED          ?= 0
FORCE         ?=
NOTIFY        ?= 0
BOMB_ID       ?=
NOTIFY_SOCKET ?= /run/bomblab/report.sock
SEEDS         ?= 5
VKIND         ?=

OUT        ?= build/$(subst :,-,$(KIND))-$(SEED)
DISTDIR    := dist/$(subst :,-,$(KIND))-$(SEED)
BUILD_ARGS := --kind $(KIND) --seed $(SEED) --out $(OUT) --image $(IMAGE) \
              $(foreach f,$(FORCE),--force $(f))
ifeq ($(NOTIFY),1)
BUILD_ARGS += --notify --bomb-id $(BOMB_ID) --socket $(NOTIFY_SOCKET)
endif

# Everything a rendered bomb dir holds that must never reach a student.
FORBIDDEN := phases.c support.c driverlib.c support.h phases.h driverlib.h \
             bombdata.h answers.txt answers_secret.txt SOLUTION.md \
             manifest.json notes hints

.PHONY: all toolchain kinds bomb dist verify hints parity calib selftest clean distclean

all: bomb

toolchain:
	docker build -t $(IMAGE) toolchain/

kinds:
	@$(PYTHON) -c "import bank; print('\n'.join(bank.kinds()))"

bomb:
	@test -n "$(KIND)" || { echo "make bomb KIND=<cmu|drill:d0..d9> SEED=<n>"; exit 1; }
	$(PYTHON) tools/buildbomb.py $(BUILD_ARGS)
	@cp $(OUT)/bomb ./bomb

dist: bomb docs/README.md docs/PRIMER.md
	@rm -rf $(DISTDIR) && mkdir -p $(DISTDIR)
	@cp $(OUT)/bomb $(OUT)/bomb.c docs/README.md docs/PRIMER.md $(DISTDIR)/
	@for f in $(FORBIDDEN); do \
	    if [ -e "$(DISTDIR)/$$f" ]; then \
	        echo "FAIL: forbidden file in package: $$f"; exit 1; \
	    fi; \
	done
	@echo "$(DISTDIR) ready:" && ls -1 $(DISTDIR)

verify:
	$(PYTHON) tools/verify_bank.py --seeds $(SEEDS) \
	    $(foreach k,$(VKIND),--kind $(k))
	bash tools/runtime_check.sh
	bash tools/parity.sh $(SEEDS)
	@mkdir -p build && $(PYTHON) tools/hint_catalog.py build/HINTS.check.md >/dev/null
	@cmp -s build/HINTS.check.md server/HINTS.md || \
	    { echo "server/HINTS.md is stale: run 'make hints'"; exit 1; }
	@echo "server/HINTS.md up to date"

# Operators' catalogue of every hint (regenerate after editing any hint).
hints:
	$(PYTHON) tools/hint_catalog.py

parity:
	bash tools/parity.sh $(SEEDS)

selftest:
	bash tools/server_selftest.sh

# ---- calibration (AC-05) ---------------------------------------------------
# ref/ holds the original self-study bomb and our reconstruction of it. Both
# are git-ignored: the reconstruction contains the original's answers.

CALIB_SRCS  := bomb.c phases.c support.c support.h phases.h
CALIB_FUNCS := main phase_1 phase_2 phase_3 func4 phase_4 phase_5 phase_6 \
               fun7 secret_phase sig_handler invalid_phase string_length \
               strings_not_equal initialize_bomb initialize_bomb_solve \
               blank_line skip explode_bomb read_six_numbers read_line \
               phase_defused

calib:
	@test -f ref/calib/phases.c -a -f ref/cmu-selfstudy/bomb/bomb || \
	    { echo "calib: ref/ not present (dev machine only)"; exit 1; }
	@rm -rf build/calib && mkdir -p build/calib
	@cd ref/calib && cp $(CALIB_SRCS) ../../build/calib/
	@echo '{"canary": ["phase_5", "phase_defused"]}' > build/calib/manifest.json
	$(PYTHON) tools/buildbomb.py --src build/calib --image $(IMAGE)
	$(PYTHON) tools/asmdiff.py --data ref/cmu-selfstudy/bomb/bomb \
	    build/calib/bomb $(CALIB_FUNCS)

clean:
	rm -f bomb

distclean: clean
	rm -rf dist build tools/__pycache__ bank/__pycache__ bank/drills/__pycache__
