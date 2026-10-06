# Tasks: Bomb Lab 연습 문제은행 (개념 드릴 + CMU 구조 폭탄)

- **Feature ID**: 003-practice-bank
- **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

`[P]` = 앞선 태스크가 끝났다면 병렬 가능. 각 Phase 끝의 **검증**을 통과해야 다음 Phase로 간다.

---

## Phase 0 — 원본 실측과 툴체인 (완료)

- [x] **T001** 원본 자습용 폭탄 내려받기·실측 → `research.md` §1~4
- [x] **T002** `toolchain/Dockerfile` — Ubuntu 12.04 + GCC 4.8.1-2ubuntu1~12.04
- [x] **T003** `tools/asmdiff.py` — 함수 단위 비교, 주소 정규화(분기·호출·RIP 상대)
- [x] **T004** 보정 빌드(`ref/calib/`, git 제외)
  - 검증: 22개 함수 명령어 일치, `.comment`·DWARF producer 일치 (spec AC-05) → research §6

## Phase A — 빌드 기반

- [x] **T010** `asmdiff.py --mask-imm` — 즉시값 가림, 분기 대상을 명령어 순번으로 정규화. 데이터 심볼 순서 비교 옵션 `--data`. 피연산자를 capstone 상세 정보로 직접 정규화하고, 절대 주소·메모리 변위도 데이터 심볼 이름으로 바꿈
  - 반대 시험: 상수만 바꾼 빌드 → 기본 모드 DIFF / `--mask-imm` OK. `-O2` 빌드 → `--mask-imm`에서도 8/8 DIFF
- [x] **T011** `bank/csrc/Makefile.bomb` — 플래그 고정, `bomb.c`만 `-ggdb`. `NOTIFY=1`의 정의는 `bomb.c`에 넘기지 않아 DWARF producer 유지. 링크 순서 `bomb.o phases.o support.o [driverlib.o]`(원본 `STT_FILE` 순서)
- [x] **T012** `tools/buildbomb.py` — `--kind`(생성기 연결, Phase C에서 활성) / `--src DIR...`(렌더된 디렉터리 일괄 컴파일, 컨테이너 1회) → `elfcheck`. `manifest.json`의 `canary`로 기대 카나리 집합 지정. 결과물은 실행한 사용자 소유
- [x] **T013** `tools/elfcheck.py` — `ET_EXEC`, strip 안 됨, `.comment` 툴체인, DWARF CU = `bomb.c` 하나 + producer 문자열, `endbr64` 없음, 카나리(`phase_defused` 필수, `--canary`로 정확한 집합). 표준 라이브러리 + binutils만 사용
  - 서버 보고 함수(`driverlib.c`)는 카나리 비교에서 제외: 원본 `driverlib`의 `init_driver`·`submitr`에 카나리가 있고, 우리 구현은 다르기 때문
  - 원본·보정 빌드 통과, 001 폭탄은 툴체인·DWARF·`endbr64`·카나리 모두 실패(의도대로 잡음)
- [x] **T014** 상위 `Makefile` — `toolchain`, `calib`, `bomb KIND= SEED= [FORCE= NOTIFY=]`, `dist`. `KIND`가 없으면 001 빌드(`make SEED=`, `make verify`)를 그대로 유지해 서버(`bomblabctl`, `server_selftest.sh`)가 Phase F 전까지 동작
  - 검증(생성기가 없으므로 보정 소스로 대체): `make calib` → 컨테이너 빌드 + `elfcheck` 통과 + 원본 대비 **0/23 diff**. `--src` 2개 일괄 빌드 1.1초. `--notify` 빌드 통과. 001 `make verify FROM=1 TO=2` 52/52 통과. `make bomb KIND=cmu`는 생성기 없음 안내 후 실패(Phase C에서 활성)

## Phase B — 공통 런타임

- [x] **T020** `bank/csrc/common/support.c`·`support.h`·`phases.h` — 보정에서 일치한 원본 구현. 폭탄별 설정은 `bombdata.h` 매크로: `NUM_PHASES`(CMU 6, 드릴 3), `HAS_SECRET`, `SECRET_LINE`(CMU 3), `SECRET_WORD`. `HAS_SECRET=0`이면 `phase_defused`에 비밀 단어 버퍼가 없어 카나리도 없다(드릴 manifest의 기대 카나리에 반영)
- [x] **T021** `#ifdef NOTIFY` 보고 — 원본 과제용 버전처럼 `support.c`의 `send_msg(defused)`가 `driver_post`를 부른다. `initialize_bomb`: `init_driver`(HELLO) 실패 시 사유 출력 후 exit 9. `explode_bomb`·`phase_defused`: EVENT(phase = `num_input_strings`, 입력 = 저장된 줄 hex). 해제 보고 실패 시 exit 9(유실 방지), 폭발 보고 실패는 경고만. `driverlib.c`(`init_driver`, `driver_post`, 내부 AF_UNIX)는 원본처럼 오프라인 빌드에도 링크
- [x] **T022** `bank/csrc/common/bomb.c` — 배포용 main. 원본과 같은 코드·출력 메시지, 주석은 직접 작성
- [x] **T023** `bank/csrc/common/drill_main.c` — 3단계 main. 드릴 번호·제목은 렌더러가 `@DRILL_ID@`·`@DRILL_TITLE@`을 치환(학생이 받는 `bomb.c`에 실제 이름이 보임). D9 숨은 단계는 `HAS_SECRET`으로
  - `elfcheck` 조정: `phase_defused` 카나리 필수 규칙은 기대 카나리가 없을 때만 적용. 서버 빌드에서는 `send_msg`·`initialize_bomb`의 카나리를 비교에서 제외
  - `asmdiff` 수정: 같은 주소의 크기 0 링커 심볼(`__TMC_END__`)보다 실제 변수(`stdout`)를 우선
  - 검증: `tools/runtime_check.sh` **32/32 통과** (AC-06)
    - 오프라인 11개: 정답 통과, 숨은 단계 진입·미진입, 파일 → stdin 전환, 빈 줄, 78자 초과, EOF 두 경우, `GRADE_BOMB`, Ctrl-C
    - 드릴 2개: 3단계 후 해제, 3단계 입력 대기
    - 원본 대조(`ref/` 필요): 공통 `bomb.c`+`support.c`+보정 phase가 원본과 **0/23 diff**. 같은 입력 13개 시나리오(77·78·85자 줄, 개행 없는 마지막 줄, 인자 오류, `GRADE_BOMB`, Ctrl-C 등)에서 출력·종료 코드가 원본과 **완전히 같음**
    - 서버 보고 5개(가짜 데몬): HELLO + EVENT 순서·phase 번호(빈 줄 제외)·hex 입력, secret = phase 7, 거부 시 시작 안 함, 데몬 불통, 해제 보고 유실 시 중단

## Phase C — 생성기·판정기 프레임워크

- [x] **T030** `bank/core.py` — `Bomb`, 시드 → 결정적 난수, 공통 퇴화 검사 도구(사전 단어 검사 등)
- [x] **T031** `bank/__init__.py` — `build(kind, seed, force=None)`, kind 등록부
- [x] **T032** `bank/judge.py` — `sscanf`(`%d`, `%s`, `%c`) / `strtol` / `strings_not_equal` / signed `char` 재현(기존 `bombcheck.py`에서 이전·확장), `check(kind, params, phase, line)`
- [x] **T033** `bank/render.py` — `bombdata.h`(매크로만), `phases.c`(`#include` 조립, 원본 데이터 배치 순서), 정답 파일, `SOLUTION.md`, `notes/`, `hints/`, `manifest.json`
- [x] **T034** `tools/fuzz_bank.py` — 계열·단계마다 경계 입력 생성, 바이너리 판정과 대조
- [x] **T035** `tools/verify_bank.sh` — 모든 계열(강제) × 모든 드릴 단계 × 시드 N: 정답 통과, phase별 오답 폭발 위치, fuzz, elfcheck, 입력 처리, 배포 패키지 금지 파일

## Phase D — CMU 구조 폭탄 1차 (자습용 실측 계열)

- [x] **T040** `cmu/p1_strings.c` + 생성기(문장 풀) + 판정기
- [x] **T041** `[P]` `cmu/p2_double.c` + 생성기 + 판정기
- [x] **T042** `[P]` `cmu/p3_switch_dd.c` + 생성기(case 값) + 판정기(정답 8개)
- [x] **T043** `[P]` `cmu/p4_func4_bsearch.c` + 생성기(상한·목표값, 해 개수 전수 검사) + 판정기
- [x] **T044** `[P]` `cmu/p5_charmap.c` + 생성기(표·목표 문자열, 사전 단어 배제) + 판정기(하위 4비트 같은 문자 모두 허용)
- [x] **T045** `[P]` `cmu/p6_list.c` + 생성기(노드 값, 7-x·내림차순) + 판정기
- [x] **T046** `[P]` `cmu/secret_fun7.c` + 생성기(15노드 BST, 목표 반환값 유일) + 판정기(`strtol`) + 진입 문자열 풀
- [x] **T047** `SOLUTION.md`·notes·hints 내용 — phase별 풀이 경로(AT&T 인용), 원본 과제와의 대응, 3단계 힌트
- [x] **T048** `tools/parity.sh` — 1차 계열 CMU 폭탄(오프라인) vs 원본, `--mask-imm`으로 22개 함수 + 데이터 심볼 순서
  - 검증: `make parity` 0 diff (AC-05) · `make verify` 1차 계열 전부 통과, fuzz 0 불일치 (AC-01, 03, 04, 07)
  - 결과(2026-10-05): `tools/parity.sh 5` → 시드 5개 모두 원본 대비 **0/23 diff**(`--mask-imm --data`). `tools/verify_bank.py --seeds 5` → **95/95 통과**, 경계 입력 2,232개 판정 불일치 0, 렌더 결정성·학생용 `bomb.c` 누출 검사 포함
  - 설계 메모: 코드 모양을 바꾸는 상수는 원본 값으로 고정(p4 목표 반환값 0, secret 목표값은 0이 아닌 1~7). secret 정답은 원본처럼 여러 개일 수 있음(경로 끝에서 왼쪽으로만 더 내려간 노드도 같은 값을 돌려줌)
  - 검증 도구는 셸 대신 `tools/verify_bank.py`(Python)로 구현. `make verify` = verify_bank + runtime_check + parity. 001 검증은 `make verify-legacy`

## Phase E — 개념 드릴

드릴마다: 단계 3개의 C 템플릿 + 생성기 + 판정기 + 학생 해설(과제에서의 모습 포함) + 힌트 3단계. 원본 phase 순서대로 진행하며, 가능한 경우 Phase D 템플릿을 재사용한다.

- [x] **T050** D0 도구 기본기 (`.rodata` 문자열 / `cmp` 직전 레지스터 / 실행 중 스택에서 만들어지는 답)
- [x] **T051** D1 문자열 (전역 문자열 비교 / 길이 검사 + 스택에 조립되는 문자열 / 입력 길이로 고른 문자열)
- [x] **T052** D2 산술·비교 (`lea`·`imul`·시프트 식 / 부호 있는·없는 비교, 부호 확장 / 상수 나눗셈과 나머지)
- [x] **T053** D3 반복문·배열 (2배 수열 / 원본의 다른 점화식 계열 / 조건부 갱신·앞의 두 값을 쓰는 수열)
- [x] **T054** D4 switch·점프 테이블 (밀집 switch / `"%d %c %d"`·default·case 오프셋 / 희소 switch·fall-through)
- [x] **T055** D5 함수 호출·재귀 (인자 3개 보조 함수 / `func4` 이진 탐색형 / 재귀 호출 2번)
- [x] **T056** D6 문자 처리·테이블 (`& 0xf` 표 인덱싱 / 표 값의 합 / 배열 순환)
- [x] **T057** D7 구조체·연결 리스트 (노드 탐색 / 순열로 정한 순서의 오름차순 / 원본 6번 완전형)
- [x] **T058** D8 이진 트리 (BST 탐색 깊이 / `fun7` 경로 인코딩 / 메모리의 트리 덤프·역추적)
- [x] **T059** D9 숨은 단계·전체 흐름 (`phase_defused`의 추가 토큰 / 진입 조건이 입력 줄 수에 의존 / 미니 폭탄 + 숨은 단계)
  - 검증: `make verify`에 드릴 30단계 포함, 전부 통과 (AC-02, 03) · 모든 드릴 폭탄 `elfcheck` 통과
  - 결과(2026-10-05): `verify_bank.py --seeds 3` → 11개 종류(CMU + 드릴 10개) 폭탄 33개, **366/366 통과**, 경계 입력 6,302개 판정 불일치 0
  - 드릴에도 변형 계열을 둠: D3 2단계(`addi`/`fact`), 3단계(`fib`/`collatz`). 검증은 시드가 고르지 않은 계열을 자동으로 추가
  - 생성 코드 확인 후 수정: D5 1단계 `mix3`가 인라인·상수 접힘으로 사라져 `noinline` 부여(호출 직전 인자 레지스터를 읽는 학습 목표 유지). D2 3단계 해설을 실제 코드(작은 나누는 수는 `lea`·`shl` 조합)에 맞게 수정
  - 학생 해설 위에 "어셈블리는 대표적인 모양, 실제는 `objdump -d`로 확인" 안내를 붙임
- [x] **T059b** 드릴 분량 축소 (2026-10-06, 운영자 요청: "딱 그 개념만") — 15개 단계에서 부수적인 검사를 빼 **모든 단계 8~44개**(정렬용 `nop` 제외, 이전 최대 94개)로 줄임. 빠진 부분은 해설의 "과제에서는"에 명시하고, 원본과 같은 전체 모양은 연습 폭탄이 맡음(spec §9 분량 원칙)
  - 주요 변경: D7 3단계 94→44 (중복 검사·포인터 배열·재연결 제외, 7-x와 내림차순만), D7 2단계 74→40, D4 3단계 49→38, D2 2단계 27→16, D0 3단계 36→16(전역 버퍼로 카나리 제거), D6 1단계 37→27(글자별 비교), D6 3단계 횟수만 검사·단계 수 6~10으로 제한, D8 1·3단계 반복문으로, D2 3단계 부호 없는 나눗셈(나누는 수는 `imul`로 보이는 소수 23~97)
  - 점프 테이블 최소 크기: GCC 4.8은 case 4개면 비교문을 만들어 D4 1·2단계는 case 5개로 유지
  - 측정 방법 수정: 이전 분석은 함수 끝 정렬용 `nop`까지 세어 수치가 부풀어 있었음. 원본 CMU 기준값(nop 제외): phase 1 8 · 2 25 · 3 36 · 4 44 · 5 37 · 6 86 · secret 42
  - 검증: 드릴 30개 폭탄 309/309, `make verify SEEDS=2` 254/254 + 런타임 32/32 + 원본 대조 2/2, `make selftest` 36/36

## Phase F — 서버 개정 (002 2판)

- [x] **T060** `db.py` 스키마 v2(`bombs`, `build_requests`) + v1 마이그레이션
- [x] **T061** `config.py` — OPEN/CLOSED + 선택적 운영 기간, 원본 과제 채점 기본값, 힌트 간격·재발급 제한
- [x] **T062** `reportd.py` — 활성 폭탄 조회, `bank.build` 캐시 + `bank.judge` 재채점, STATUS/NOTES/HINT/NEW/REQ
- [x] **T063** `[P]` `scoring.py` — 과제형만 점수·감점, 드릴 진도·연습 완주 집계, 프리즈 제거
- [x] **T064** `[P]` `web.py` + `templates/` — 과제형 점수표 + 드릴 진도표, 피드에 트랙, 관리자 트랙 필터
- [x] **T065** `server/bin/bomblab` — 학생 CLI(`status`/`notes`/`hint`/`new`)
- [x] **T066** `bomblab-builder` 서비스 — 요청 처리, `buildbomb.py` 호출, 홈 설치, 해설·힌트를 `/var/lib/bomblab/bombs/<id>/`에 보관, 실패 시 이전 폭탄 유지
- [x] **T067** `bomblabctl` — provision(과제형 + 드릴 D0~D9 + 연습 1개), `reissue`, `open/close/auto`, `tick`은 운영 기간이 있을 때만
- [x] **T068** `install.sh`·systemd·nginx — `docker.io`, 이미지 빌드, 빌더 유닛, 디렉터리 권한
- [x] **T069** `tools/server_selftest.sh` 갱신 — mock 빌더로 002 2판 AC-01~11
  - 검증: `server_selftest.sh` 전부 통과
  - 결과(2026-10-05): `tools/server_selftest.py` **36/36 통과** (root 불필요). Docker가 있으면 실제 서버 모드 폭탄을 컴파일해 데몬에 연결한 채 7단계를 해제하고, 서버 재채점 7건 모두 유효 확인
  - 결정 반영: secret +10점, 운영 기간 2주(`[window]`), 과제형 폭탄은 해설·힌트 없음, 힌트는 시간 제한 없이 1 → 2 → 3 순서
  - 함께 고친 것: 입력 원문을 UTF-8 대신 latin-1(원본 바이트)로 디코딩해 판정기와 일치, 관리자 화면의 닉네임 HTML 이스케이프 누락(XSS) 수정, `install.sh`가 `ref/`(원본 폭탄)를 서버로 복사하지 않음, 학생 CLI는 `/opt/bomblab`에 의존하지 않는 단일 파일로 `/usr/local/bin`에 설치
  - 과제형 폭탄을 운영자가 재발급해도 이전 폭탄에서 해제한 단계는 점수에 남김
  - **미검증(root 필요)**: 실제 계정 생성·홈 설치·소유권 변경(`provision`, `reissue`, 빌더의 홈 설치). T082 실서버 리허설에서 확인

## Phase G — 문서·정리

- [x] **T070** `docs/README.md` — 연습 서버 안내(트랙, 학생 CLI, 해설·힌트, 스코어보드), 대회 규칙 제거
- [x] **T071** `[P]` `docs/PRIMER.md` — AT&T 문법 기준으로 개정, 드릴과 연결
- [x] **T072** `[P]` `docs/DRILLS.md` — 드릴 안내(권장 순서, 드릴별 목표, 대응하는 원본 phase)
- [x] **T073** `server/README.md` — 운영자 안내 2판(설치, provision, 재발급, 툴체인 이미지 보관)
- [x] **T074** 001 코드 제거 — `src/`, `gen_bomb.py`, `bombcheck.py`, `fuzz_checker.py`, `check_secret_unique.py`, `verify.sh`. `.gitignore` 갱신
- [x] **T075** 001·002 1판 문서 정리 → 2026-10-06: 001 전체와 002 1판 spec·plan·tasks를 1판 코드와 함께 `previous/`로 이동(현재 트리의 `specs/002`에는 2판 spec만 남김)
  - 결과(2026-10-05): 001 코드(`src/`, `gen_bomb.py`, `bombcheck.py`, `fuzz_checker.py`, `check_secret_unique.py`, `verify.sh`)와 Makefile의 예전 빌드 경로 제거. 제거 후 `make verify SEEDS=3`(366/366 + 런타임 32/32 + 원본 대조 3/3), `make selftest`(36/36), `make dist` 모두 통과
  - 문서: 학생 안내(`docs/README.md`), 개념 정리(`docs/PRIMER.md`, 원본 과제 패턴 중심으로 개정), 드릴 안내(`docs/DRILLS.md`, 학생 홈의 각 드릴에도 설치), 운영자 매뉴얼(`server/README.md`, AWS 절차 유지 + 노트북(WSL2) 운영 + 재발급 대처 추가)

- [x] **T076** 운영진 질문 대응 도구 (2026-10-06)
  - `bomblabctl solution <학생> <bomb|practice|d0..d9>`: 그 학생 폭탄의 `SOLUTION.md`(정답·풀이·힌트)와 해제한 단계·폭발 수·**학생이 연 힌트**를 함께 출력. 셀프테스트에 포함(38/38)
  - `server/HINTS.md`: 모든 드릴 단계·CMU phase의 힌트 3개씩을 모은 운영진용 목록(`tools/hint_catalog.py`, `make hints`로 생성). 힌트 문장이 시드와 무관함을 확인하고 만들었으며, 과제형 phase마다 "막히면 연습할 드릴"을 붙임. `make verify`가 이 문서가 최신인지 검사
  - `server/README.md` 8장에 "학생 질문 대응" 절차 추가(드릴·연습은 힌트 → 짚어 주기 → 해설, 과제형은 답 대신 같은 개념의 드릴 권유)

## Phase H — 2차 변형 계열과 운영 검증

- [ ] **T080** 2차 변형 계열의 원본 존재 확인(공개 자료 조사) → 확인된 것만 `research.md`에 기록
- [ ] **T081** 확인된 계열 구현(p2 `addi`/`fact`, p3 `switch_dcd`, p4 `func4_fib`, p5 `cycle`, p6 정렬 방향·변환 조합) + verify 편입
- [ ] **T082** 실서버 리허설(VM) — 설치 → provision → 과제형 해제·폭발 → 드릴 재발급 → 해설·힌트 → 격리 (002 AC-08, 12)
  - root가 필요해 개발 PC에서 검증하지 못한 경로를 여기서 확인: `provision`(계정 생성 + 학생당 폭탄 12개 빌드·홈 설치·소유권), `reissue`, 빌더 서비스의 홈 설치, 학생 계정에서 `/var/lib/bomblab/bombs` 읽기 거부
- [x] **T083** 툴체인 이미지 `docker save` 보관 절차 문서화
- [ ] **T084** 파일럿 — 학생 3명 이상, 드릴 완료 후 CMU 구조 폭탄 하루 안에 해제 여부 측정 (spec AC-08)

---

## 의존 관계 요약

```
Phase 0 ─▶ A ─▶ B ─▶ C ─▶ D ─▶ E
                          │
                          └────▶ F (D의 bank.build·judge가 있으면 시작 가능)
D, E, F ─▶ G ─▶ H
```
