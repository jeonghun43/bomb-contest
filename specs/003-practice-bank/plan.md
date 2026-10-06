# Plan: Bomb Lab 연습 문제은행 (개념 드릴 + CMU 구조 폭탄)

- **Feature ID**: 003-practice-bank
- **Spec**: [spec.md](spec.md) · **Research**: [research.md](research.md) · **서버 개정**: [002 spec 2판](../002-contest-server/spec.md)
- **작성일**: 2026-10-05

---

## 1. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 폭탄 컴파일 | **GCC 4.8.1** (`toolchain/Dockerfile`, Ubuntu 12.04 컨테이너) | 원본과 같은 컴파일러. AC-05 보정에서 22개 함수 일치 확인 |
| 폭탄 소스 | C 템플릿 + 생성 헤더(`#define`만) | 시드가 바뀌어도 코드 모양은 그대로, 상수만 바뀜 |
| 생성기·판정기 | Python 3 표준 라이브러리 (`bank/` 패키지) | 서버가 같은 코드로 재채점 |
| 원본 일치 검사 | `tools/asmdiff.py` (capstone, pyelftools) | 개발 PC 전용. 서버에는 필요 없음 |
| 서버 | 002 1판 구현 재사용 (Python 표준 라이브러리, SQLite, systemd, nginx) | |
| 서버의 폭탄 빌드 | `docker.io`(Ubuntu 기본 패키지) + `bomblab-gcc48` 이미지 | 서버에서도 같은 툴체인 |

## 2. 핵심 설계 결정

### 2.1 "원본과 같게"는 툴체인으로 보장하고, 흉내 내지 않는다
카나리 위치, `endbr64` 없음, 절대 주소 참조, `phase_5`의 특이한 스택 사용은 모두 GCC 4.8.1 + 원본 플래그 + 원본과 같은 모양의 C에서 저절로 나온다(research §6). 따라서:
- 모든 폭탄(드릴 포함)은 `bomblab-gcc48` 컨테이너 안에서만 컴파일한다. 호스트 gcc로 빌드하는 경로는 두지 않는다.
- 플래그는 한 곳(`bank/csrc/Makefile.bomb`)에만 둔다: `-O1 -fstack-protector -mtune=generic -march=x86-64`, `bomb.c`만 `-ggdb`.
- CMU 구조 폭탄의 C 템플릿은 보정 때 원본과 일치가 확인된 재구성 소스(`ref/calib/`)를 출발점으로 삼고, 상수 자리만 매크로로 바꾼다.

### 2.2 원본 일치의 회귀 검사
보정 소스에는 원본 정답이 들어 있어 저장소에 넣을 수 없다. 대신:
- `asmdiff.py --mask-imm`: 상수(즉시값)까지 가리고 **명령어 모양만** 비교하는 모드를 추가한다.
- `tools/parity.sh`: `ref/cmu-selfstudy/bomb/bomb`이 있으면, 자습용과 같은 변형 계열로 만든 CMU 구조 폭탄(오프라인 빌드)을 원본과 `--mask-imm`으로 비교해 22개 함수 모두 일치해야 통과한다. `ref/`가 없으면 건너뛴다(서버 등).
- 모든 빌드 결과에 대해 ELF 특성 검사(AC-05b)를 `verify`에 넣는다: `ET_EXEC`, strip 안 됨, DWARF CU = `bomb.c` 하나, `endbr64` 없음, 카나리가 있는 함수 목록이 기대값과 같음. 카나리 비교에서는 서버 보고 함수(`driverlib.c`)를 뺀다. 원본 `driverlib`에도 카나리가 있지만(`init_driver`, `submitr`) 우리 구현은 내부가 다르기 때문이다.
- 개발 PC 전용인 `make calib`은 보정 소스(`ref/calib/`)를 `Makefile.bomb`으로 빌드해 원본과 비교한다. 빌드 규칙(플래그·링크 순서)을 바꾸면 반드시 돌린다.

### 2.3 폭탄 = (종류, 시드)
- **종류(kind)**: `cmu` 또는 `drill:d0` ~ `drill:d9`.
- `bank.build(kind, seed)` → `Bomb(kind, seed, variants, params, answers)`. 결정적이다(NFR-14).
- `variants`: 슬롯마다 고른 변형 계열 이름(예: `{"p3": "switch_dd", "p6": "list_7x_desc"}`). `params`: 그 계열의 상수·테이블.
- 서버는 DB에 `(kind, seed)`만 저장하고, 재채점할 때 `bank.build`로 다시 만든다(002의 `gen_bomb.build(seed)`를 대체).

### 2.4 소스 조립: 원본처럼 phase는 한 번역 단위에
원본은 phase 1~6, `func4`, `fun7`, `secret_phase`와 그 데이터가 한 파일(`phases.c`)에 있다. 심볼 순서, 정적 지역 변수 이름(`array.3449` 형식), 데이터 배치를 맞추려고 생성기는 다음을 만든다:

```c
/* OUT/phases.c (생성) */
#include "bombdata.h"            /* 시드별 #define만 */
#include "cmu/p1_strings.c"
#include "cmu/p2_double.c"
#include "cmu/p3_switch_dd.c"    /* 슬롯별로 고른 변형 계열 */
...
#include "cmu/secret_fun7.c"
```

- 변형 계열 파일은 해당 `phase_N`과 그 phase의 데이터(노드, 트리, 표)를 정의하고, 상수는 `bombdata.h`의 매크로로 받는다. 예: `static char array[] = P5_ARRAY;`, `listNode node1 = {P6_V1, 1, &node2};`.
- 데이터 정의 순서는 원본의 메모리 배치(`n1`… 다음 `node1`…)가 나오도록 정한다. `parity.sh`에서 데이터 심볼 순서도 비교한다.

### 2.5 판정 방식과 서버 보고
- 각 phase 템플릿은 원본과 같은 지점에서 검사하고 즉시 `explode_bomb()`를 부른다. 판정 순서를 바꾸는 개선은 하지 않는다(spec FR-12).
- 공통 런타임(`support.c`)은 보정에서 일치한 원본 구현을 그대로 쓴다: `read_line`/`skip`/`blank_line`(빈 줄 무시, 파일 EOF → stdin, 78자 제한, `len-1` 위치 절단), `strings_not_equal`, `read_six_numbers`, `sig_handler`, `phase_defused`(4번째 줄 `"%d %d %s"`).
- 서버 모드(`-DNOTIFY`)에서는 원본 과제용 버전처럼 `initialize_bomb`에서 `HELLO`, `explode_bomb`과 `phase_defused`에서 `EVENT`를 보낸다. phase 번호는 `num_input_strings`(빈 줄을 뺀 실제 입력 줄 수)다. 이 세 함수의 서버 모드 코드는 원본 자습용과 달라지며, 이것이 원본과의 유일한 차이다(spec FR-35). `parity.sh`는 오프라인 빌드로 검사한다.
- 서버로 보내는 입력은 `input_strings`에 저장된 줄(절단 후) 그대로다. 판정기도 그 줄로 판정하므로, 줄 끝 개행이 없을 때 마지막 글자가 잘리는 원본 특성까지 일치한다.

### 2.6 판정기 = C 의미론의 Python 재현
- `bank/judge.py`: 기존 `bombcheck.py`의 `sscanf` 재현(`scan_d`, `scan_s`)을 옮기고 `strtol`(앞 공백, 부호, `long` 클램프 후 `int` 절삭), `strings_not_equal`, 문자 부호 확장(`char`는 signed)을 추가한다.
- 변형 계열마다 `check(params, line) -> bool`을 구현한다. 정답이 여러 개인 계열(switch, func4, 문자 매핑)도 그대로 처리된다(spec FR-04).
- `tools/fuzz_bank.py`: 계열마다 경계 입력(정답, 정답의 한 자리 변형, 범위 끝 ±1, 형식 오류, 공백·부호 변형, 78자 초과)을 만들어 **실제 바이너리의 판정**과 대조한다. 불일치가 하나라도 있으면 실패한다.

### 2.7 서버: 재발급과 해설은 root 빌더가, 내용 전달은 소켓으로
`reportd`는 `bomblab` 계정 + `ProtectHome=true`라 학생 홈에 쓸 수 없다. 이 제약을 유지한 채:
- **학생 CLI** `bomblab`(`/usr/local/bin`, 일반 권한 Python 스크립트)이 기록 소켓에 요청한다: `status`, `notes`, `hint`, `new`.
- **해설·힌트**는 빌드할 때 `/var/lib/bomblab/bombs/<bomb_id>/`(학생 접근 불가)에 저장한다. `reportd`는 해당 단계가 유효하게 해제됐거나(해설) 힌트 시각이 지났을 때(힌트)만 소켓으로 내용을 돌려준다. 학생 홈에 파일을 쓰지 않는다.
- **재발급**은 `reportd`가 `build_requests` 행을 만들고, root 서비스 `bomblab-builder`가 처리한다: `bank` 생성 → 컨테이너 컴파일 → 학생 홈에 설치 → DB에서 이전 폭탄 비활성화 → 요청 완료 표시. CLI는 완료될 때까지 기다린다(보통 2~3초).

## 3. 디렉터리 구조

```
bank/                         Python 패키지: 생성기 + 판정기 (서버가 import)
  __init__.py                 build(kind, seed) -> Bomb
  core.py                     Bomb, Rng(시드→결정적 난수), 공통 퇴화 검사
  cmu.py                      CMU 구조 폭탄: 슬롯별 변형 계열 생성기
  drills/d0.py … d9.py        드릴별 3단계 생성기
  judge.py                    C 의미론 재현(sscanf/strtol/strings) + check(kind, params, phase, line)
  render.py                   bombdata.h, phases.c, 정답 파일, SOLUTION.md, notes/hints 렌더링
  csrc/
    Makefile.bomb             컨테이너 안에서 쓰는 유일한 빌드 규칙(플래그 고정)
    common/
      bomb.c                  배포용 main (원본 배포본과 같은 코드·출력 메시지, 주석은 직접 작성)
      drill_main.c            드릴용 main (3단계, D9는 숨은 단계 포함)
      support.c support.h     원본과 일치 확인된 공통 런타임 + #ifdef NOTIFY 보고
      phases.h                phase 선언 (secret_phase는 원본처럼 매개변수 목록 없이)
      driverlib.c             서버 보고. 원본과 같은 파일 이름·API(init_driver, driver_post),
                              내부는 AF_UNIX (002의 notify.c에서 이전). 원본처럼 오프라인에도 링크
    cmu/                      1차(구현됨): p1_strings.c, p2_double.c, p3_switch_dd.c,
                              p4_func4_bsearch.c, p5_charmap.c, p6_list.c, secret_fun7.c
                              2차(T081, 미구현): p2_addi.c, p2_fact.c, p3_switch_dcd.c,
                              p4_func4_fib.c, p5_cycle.c
    drills/d0/ … d9/          s1.c s2.c s3.c (D3은 s2_addi/s2_fact, s3_fib/s3_collatz; D9는 secret.c)
    test/phases_rt.c          런타임 시험용 phase (답이 뻔함, 배포 안 함)
  words.py                    드릴용 단어·문구 풀
toolchain/Dockerfile          GCC 4.8.1 이미지
tools/
  asmdiff.py                  함수 단위 비교 (--mask-imm: 상수 무시, --data: 데이터 배치 순서)
  buildbomb.py                bank → OUT 디렉터리 → 컨테이너 컴파일 (Makefile·서버 공용)
  parity.sh                   원본 일치 회귀 검사 (ref/ 있을 때)
  elfcheck.py                 AC-05b ELF 특성 검사 (표준 라이브러리 + binutils만)
  runtime_check.sh            공통 런타임 검사: 입력 처리, 드릴 main, 원본 대조(ref/), 서버 보고(가짜 데몬)
  fuzz_bank.py                판정기 vs 바이너리 대조
  verify_bank.py              모든 계열 × 모든 드릴 단계 × N 시드 검증 (AC-01~04, 07, NFR-11, 14)
  server_selftest.py / .sh    002 2판 서버 셀프테스트 (root 불필요)
```

**보관**: 001 자체제작 폭탄과 002 1판(대회 서버)의 코드·문서는 `previous/`로 옮겼다([previous/README.md](../../previous/README.md)). 현재 코드와 서로 참조하지 않는다.

### 빌드 산출물 (`OUT/`)

| 파일 | 학생 배포 | 내용 |
|---|---|---|
| `bomb` | ✅ | 바이너리 |
| `bomb.c` | ✅ | 배포용 main |
| `bombdata.h`, `phases.c`, `*.c` | ❌ | 생성 소스 |
| `answers.txt`, `answers_secret.txt` | ❌ | 정답 한 벌 |
| `SOLUTION.md` | ❌ | 운영자용 전체 해설 |
| `notes/stageN.md`, `hints/stageN-K.md` | ❌ (서버가 조건부 전달) | 학생용 해설·힌트 |
| `manifest.json` | ❌ | kind, seed, variants, 빌드 툴체인 버전 |

## 4. CMU 구조 폭탄 (Lv.2)

### 4.1 슬롯별 변형 계열

1차 구현은 자습용에서 **실측한 계열**만 한다(✅). 나머지는 공개 자료로 존재를 확인한 뒤 2차로 추가한다.

| 슬롯 | 계열 | 1차 | 시드로 바꾸는 것 | 퇴화 배제 / 생성 규칙 |
|---|---|---|---|---|
| p1 | `strings` | ✅ | 문장 | 문장 풀에서 선택. 길이 30~70자 |
| p2 | `double` | ✅ | 초항 | 초항 1~9, 6번째 값이 `int` 범위 안 |
| p2 | `addi`, `fact` | 2차 | 초항 | 같은 규칙 |
| p3 | `switch_dd` | ✅ | case 0~7의 값 | 값 100~999, 서로 다름 |
| p3 | `switch_dcd` | 2차 | case별 (문자, 값) | 문자는 소문자, 서로 다름 |
| p4 | `func4_bsearch` | ✅ | 상한 `hi`(10~30, 원본 14), 둘째 수(0~99) | 목표 반환값은 원본처럼 0 고정(다른 값이면 `test`가 `cmp`로 바뀌어 코드 모양이 달라짐). 정답은 왼쪽으로만 내려가는 값들(여러 개) |
| p4 | `func4_fib` | 2차 | 목표값 | |
| p5 | `charmap` | ✅ | 16칸 표, 목표 6글자 | 표는 서로 다른 소문자 16개. 목표는 표 글자로 만든 무작위 문자열. 하위 4비트만 맞으면 되므로 정답은 여러 개 |
| p5 | `cycle` | 2차 | 16칸 순환 배열, 횟수 | |
| p6 | `list` | ✅(7-x, 내림차순) | 노드 값 6개, 7-x 유무, 정렬 방향 | 값 100~999 서로 다름. 정답 순열이 항등·역순이면 다시 뽑음. 1차는 원본과 같은 7-x·내림차순 고정 |
| secret | `fun7` | ✅ | 15노드 완전 BST 값, 목표 반환값, 진입 문자열 | 값 1~1000, 목표 반환값 1~7(0이면 `test`로 코드 모양이 바뀜). 경로 끝에서 왼쪽으로만 더 내려간 노드도 같은 값을 돌려주므로 정답이 여러 개일 수 있음(원본도 그렇다). 진입 문자열은 단어 풀에서 선택 |

### 4.2 정답과 해설
- `answers.txt`: 6줄. `answers_secret.txt`: 4번째 줄에 진입 문자열을 붙이고 7번째 줄 추가.
- `SOLUTION.md`: phase마다 정답(여러 개면 전부), 풀이 경로(어떤 명령어에서 무엇을 읽는지), 원본 과제와의 대응, 3단계 힌트. 어셈블리 인용은 AT&T 문법(spec NFR-06).
- 학생용 `notes/stageN.md`: SOLUTION의 해당 phase 부분에서 운영자 메모를 뺀 것. `hints/stageN-{1,2,3}.md`: 3단계 힌트.

## 5. 개념 드릴 (Lv.1)

- 드릴 폭탄은 `drill_main.c`로 만든다. 원본 `main`과 같은 흐름(환영 → `read_line` → `phase_N` → `phase_defused` → 메시지)을 3단계로 줄인 것이며, 함수 이름도 `phase_1`~`phase_3`을 쓴다. 과제에서 쓸 gdb 습관(`break phase_2`, `break explode_bomb`)이 그대로 연습되게 하기 위해서다.
- D9만 원본 `phase_defused` 진입 구조(특정 줄의 추가 토큰)로 숨은 단계를 포함한다.
- 단계 템플릿 하나 = `drills/dN/sK.c` 하나.
- **분량 원칙**: 드릴 단계는 그 개념만 보이게 짧게(명령어 8~44개, 정렬용 `nop` 제외). 과제 phase에 붙는 부수적인 검사(두 번째 입력값, 중복 검사, 재연결 등)는 빼고 해설의 "과제에서는"에 적는다. 원본과 똑같은 전체 모양은 CMU 구조 연습 폭탄이 맡는다. 단, 점프 테이블처럼 컴파일러가 만드는 구조 자체가 학습 대상이면 그 구조가 나오는 최소 크기를 지킨다(GCC 4.8은 case 5개부터 점프 테이블). 측정값은 [research.md §7](research.md).
- 단계마다 생성기·판정기·학생 해설·힌트를 둔다. 해설에는 "과제에서는 이 패턴이 이런 모습으로 나온다"를 반드시 포함한다(spec FR-24).
- 컴파일러가 학습 대상을 없애 버리는 경우(인라인·상수 접힘)는 소스에서 막는다. 예: D5 1단계 `mix3`에 `noinline`.
- 구현 순서: D0 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8 → D9. 원본 phase 순서와 같아서, 앞 드릴을 만들 때 쓴 CMU 템플릿을 뒤 드릴이 재사용할 수 있다.

## 6. 빌드 파이프라인

```
bank.build(kind, seed) ──render──▶ OUT/{bombdata.h, phases.c, *.c, Makefile.bomb, answers…, notes…}
                                     │
          docker run --rm -v OUT:/src bomblab-gcc48 make -f Makefile.bomb [NOTIFY=1 …]
                                     ▼
                                   OUT/bomb ──elfcheck──▶ 통과해야 설치·배포
```

- `tools/buildbomb.py --kind cmu --seed N --out DIR [--notify --bomb-id HEX --socket PATH] [--force-variant p3=switch_dd]`. `Makefile`, `bomblabctl`, 빌더 서비스가 모두 이것을 쓴다.
- `--force-variant`는 검증용이다. 시드와 무관하게 특정 계열을 강제한다(NFR-11).
- 여러 폭탄을 한 번에 빌드할 때는 컨테이너를 하나만 띄우고 안에서 반복한다(검증 시간 단축).
- 상위 `Makefile`: `make bomb KIND=cmu SEED=n`, `make verify`, `make parity`, `make toolchain`(이미지 빌드).

## 7. 서버 변경 (002 2판)

### 7.1 DB 스키마 v2

```sql
CREATE TABLE bombs (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    track      TEXT NOT NULL,          -- assign | practice | drill
    kind       TEXT NOT NULL,          -- cmu | drill:d0 … drill:d9
    seed       INTEGER NOT NULL,
    bomb_id    TEXT UNIQUE NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE build_requests (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, track TEXT NOT NULL,
    kind TEXT NOT NULL, status TEXT NOT NULL,   -- pending | building | done | failed
    bomb_id TEXT, error TEXT, created_at REAL NOT NULL, finished_at REAL
);
```
- `users.seed`, `users.bomb_id`는 v1 호환용으로 남기되 쓰지 않는다. 마이그레이션은 기존 사용자 행을 `bombs(track='assign', kind='cmu')`로 옮긴다. (v1 폭탄은 자체제작이라 재채점할 수 없으므로, 실제로는 새 서버에 새로 provision하는 것을 기본으로 한다.)
- `events`는 그대로 두고 `bomb_id`로 `bombs`와 조인해 트랙을 얻는다.

### 7.2 프로토콜 (한 줄 요청, 응답은 한 줄 또는 길이 접두 본문)

```
HELLO <bomb_id>                    -> OK | CLOSED <reason> | ERR <reason>          (유지)
EVENT <bomb_id> <kind> <phase> <hex> -> OK | ERR <reason>                         (유지)
STATUS                             -> OK <json>          자기 폭탄 목록·진도·열린 해설·힌트
NOTES <bomb_id> <stage>            -> OK <n>\n<본문 n바이트> | LOCKED
HINT  <bomb_id> <stage> <k>        -> OK <n>\n<본문> | LOCKED <이유>
NEW   <practice | drill:dN>        -> OK <request_id> | ERR <reason>
REQ   <request_id>                 -> PENDING | DONE <설치 경로> | FAILED <reason>
```
- 모든 요청은 `SO_PEERCRED` uid로 신원을 정한다(1판과 같음). 남의 `bomb_id`는 `ERR`.
- `HELLO`/`EVENT`는 **활성** 폭탄만 받는다. 재발급으로 비활성화된 폭탄은 `ERR`(spec 002 AC-04).
- `NEW`는 과제형(`assign`)을 받지 않는다(FR-13). 학생당 진행 중 요청 1개, 분당 3회로 제한한다.
- 힌트는 시간 제한 없이 요청하면 열린다. 단, k번째 힌트는 k-1번째를 연 뒤에만 열린다(열람 기록은 `hint_views`). 드릴·연습 폭탄만 해당하고, 과제형 폭탄은 해설·힌트 모두 `LOCKED`.

### 7.3 컴포넌트별 변경

| 컴포넌트 | 변경 |
|---|---|
| `config.py` | 대회 상태 기계(BEFORE/RUNNING/FROZEN/ENDED)를 **OPEN/CLOSED**로 단순화. `[window] start/end`는 선택. 채점 기본값을 원본 과제 기준으로(10,10,10,10,15,15 / secret 10 / -0.5 / 상한 20). 재발급 제한 설정 추가 |
| `db.py` | 스키마 v2, 마이그레이션, `bombs`·`build_requests` 쿼리 |
| `reportd.py` | `bomb_id`로 활성 폭탄 조회 → `bank.build(kind, seed)` 캐시 → `bank.judge` 재채점. STATUS/NOTES/HINT/NEW/REQ 처리 |
| `scoring.py` | 과제형 폭탄만 점수·순위·감점. 드릴 진도(드릴 × 3단계)와 연습 폭탄 완주 횟수 집계는 별도 함수. 프리즈 제거 |
| `web.py`, `templates/` | 스코어보드에 과제형 점수표 + 드릴 진도표. 공개 피드에 트랙 표시. 프리즈 배너 제거. 관리자 화면에 트랙별 필터 |
| `bin/bomblab` (신규) | 학생 CLI: `status`, `notes <폭탄> [단계]`, `hint <폭탄> <단계> <k>`, `new practice`, `new drill dN` |
| `bin/bomblabctl` | `provision`: 계정 + 과제형 폭탄 + 드릴 D0~D9 + 연습 폭탄 1개. `reissue <user> assign`. 상태 명령은 `open/close/auto`로. `tick`은 운영 기간이 있을 때만 계정 잠금 |
| `bomblab-builder` (신규) | root systemd 서비스. `build_requests`를 처리해 빌드·설치·DB 갱신. 동시 빌드 2개 |
| `install.sh` | `docker.io` 설치, `bomblab-gcc48` 이미지 빌드, 빌더 유닛 등록, `/var/lib/bomblab/bombs` 생성(0700, bomblab 소유) |

### 7.4 학생 홈 레이아웃

```
~/bomb/          과제형 폭탄 (bomb, bomb.c, README.md, PRIMER.md)
~/practice/      현재 연습 폭탄 (재발급 시 교체)
~/drills/d0/ … ~/drills/d9/   드릴 폭탄 (재발급 시 해당 드릴만 교체)
```

## 8. 검증 계획

| 검사 | 도구 | 범위 | 대응 AC |
|---|---|---|---|
| 원본 일치 (모양) | `parity.sh` | 자습용 계열 CMU 폭탄 vs 원본, 22개 함수 + 데이터 심볼 순서 | spec AC-05 |
| ELF 특성 | `elfcheck.py` | 빌드되는 모든 폭탄 | AC-05b, AC-04 |
| 정답 통과 / 오답 폭발 위치 / 렌더 결정성 | `verify_bank.py` | 모든 계열(강제) × 모든 드릴 단계 × 시드 5개 | AC-01, AC-02, NFR-14 |
| 판정 일치 | `fuzz_bank.py` | 같은 범위, 계열마다 경계 입력 | AC-03, 002 AC-11 |
| 입력 처리 | `runtime_check.sh` | 파일 EOF → stdin 전환, 빈 줄, 78자 초과, Ctrl-C, 원본과 동작 비교 | AC-06 |
| 배포 패키지 | `verify_bank.py` | 학생용 `bomb.c`에 정답·비밀 단어·생성 헤더가 없음 | AC-07 |
| 서버 | `server_selftest.py` (root 불필요, 빌더는 프로세스 안에서 실행) | 002 2판 AC-01~10 | 002 AC |
| 실서버 리허설 | VM | 설치 → provision → 재발급 → 해설 → 격리 | 002 AC-08, 12 |
| 파일럿 | 학생 3명 이상 | 드릴 완료 후 CMU 구조 폭탄 하루 안에 해제 | spec AC-08 |

## 9. 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| Ubuntu 12.04 `old-releases`·Launchpad 보관 파일이 사라짐 | 툴체인 이미지 재생성 불가 | 이미지를 `docker save`로 tar 보관(저장소 밖, 운영 자료). 최후 수단으로 14.04 + GCC 4.8.4를 쓰고 parity로 차이 확인 |
| 상수 크기에 따라 명령어 인코딩이 달라짐(imm8 ↔ imm32) | 모양 비교 오탐 | `--mask-imm`은 즉시값만 가리므로 인코딩 길이 차이는 분기 오프셋 차이로 나타남 → 분기 대상은 명령어 순번으로 정규화 |
| 상수 선택이 코드 모양을 바꿈 (예: 곱셈 상수 2 → `add`) | 시드별 체감 차이 | 계열마다 상수 범위를 원본과 같은 코드가 나오는 범위로 제한하고, verify에서 시드별 명령어 모양이 계열 기준과 같은지 검사 |
| 서버 빌드 지연·실패 | 재발급 대기 | 빌드 2~3초. 실패 시 요청 `failed`와 사유 기록, 이전 폭탄은 비활성화하지 않음 |
| 판정 불일치 | 억울한 폭발 기록 | `fuzz_bank.py` 0 불일치를 verify 통과 조건으로 |
| 2차 변형 계열의 원본 존재를 확인할 수 없음 | 원본에 없는 문제를 연습 | 확인되지 않은 계열은 CMU 구조 폭탄에 넣지 않고, 필요하면 드릴 ③ 응용 단계로만 사용 |
| 원본 자료 재배포 | 저작권 | `ref/`는 git 제외. 배포 `bomb.c`의 주석·라이선스 문구와 학생 문서는 직접 작성(출력 메시지만 원본과 같게). 보정 소스와 원본 정답은 저장소에 넣지 않음 |
