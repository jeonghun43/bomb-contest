# Plan: 대회용 신규 Bomb Lab

- **Feature ID**: 001-new-bomb
- **Spec**: [spec.md](spec.md)

---

## 1. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 폭탄 본체 | C11, gcc, `-O1 -g -Wall -no-pie -fno-stack-protector` | 원본 Bomb Lab과 동일한 어셈블리 가독성. `-no-pie`로 주소 고정 |
| 타깃 | x86-64 Linux ELF | 참고자료·도구(gdb/objdump/Ghidra) 생태계가 가장 두터움 |
| 생성기 | Python 3 (표준 라이브러리만) | 유일성 전수 검증과 참조 구현을 빠르게 작성 |
| 빌드 | GNU Make | 시드 → 헤더 생성 → 컴파일 의존성 표현 |
| 검증 | bash | 바이너리 실행·종료 코드·출력 검사 |

## 2. 모듈 구조

```
src/
├── bomb.h        공통 선언 (배포 X)
├── bomb.c        main 루프                       ← 참가자에게 배포 O
├── phases.c      phase_1..6 + secret_phase       ← 배포 X (문제 본체)
├── support.c     폭발/해제/로그/secret 트리거     ← 배포 X
├── util.c        입력 읽기·파싱 헬퍼              ← 배포 X
└── bombdata.h    시드 상수·테이블 (생성물)        ← 배포 X
```

**배포 경계**: 참가자는 `bomb` 바이너리와 `bomb.c`만 받는다. `bomb.c`에는 phase 호출 순서와 안내 문구만 있고 판정 로직은 없다. 원본 Bomb Lab과 동일한 구도다.

### 2.1 `bomb.c` (배포용)

```c
int main(int argc, char *argv[]) {
    /* argc==1: stdin, argc==2: 정답 파일, 그 외: usage 후 exit(8) */
    initialize_bomb();
    input = read_line();  phase_1(input);  phase_defused();  /* "Phase 1 defused." */
    /* ... phase_2 ~ phase_6 동일 패턴 ... */
    return 0;
}
```

`phase_defused()` 호출이 코드에 보이는 것이 secret phase 존재의 유일한 단서다.

### 2.2 `support.c`

| 함수 | 동작 |
|---|---|
| `initialize_bomb()` | 배너 출력, 로그 파일 준비, 시드 기록 |
| `explode_bomb()` | `"BOOM!!!"` + 안내 출력 → `bomb_log(phase, "EXPLODED")` → `exit(8)` |
| `bomb_log(phase, result)` | `bomb.log`에 `ISO시각 \| seed=N \| phase=N \| RESULT` append |
| `phase_defused()` | 해제 카운트 증가 → `bomb_log(n, "DEFUSED")`. 4번째 해제 시 phase_4 입력 줄을 `"%d %d %s"`로 재파싱해 세 번째 토큰이 `PS_WORD`면 플래그 세팅. 6번째 해제 시 플래그가 서 있으면 `secret_phase()` 호출 |
| `set_phase_input(n, s)` | 각 phase 입력 원문 보관 (secret 재파싱용) |

### 2.3 `util.c`

| 함수 | 동작 |
|---|---|
| `read_line()` | stdin 또는 정답 파일에서 한 줄 읽기, 개행 제거, EOF면 종료 |
| `read_six_numbers(s, a)` | `sscanf(s, "%d %d %d %d %d %d")`, 6개 미만이면 폭발 |
| `rotl32(v, n)` / `bit_reverse(v, n)` / `popcount32(v)` | phase 공용 비트 헬퍼 |

## 3. Phase 알고리즘 명세

모든 phase는 `bombdata.h`의 시드 상수만 참조하고 **로직 구조는 고정**이다.

### phase_1 — 쉬움 · 회전 + XOR 역산

- **입력**: `%d` 정수 1개
- **판정**: `rotl32((unsigned)x ^ P1_KEY, P1_ROT) == P1_TARGET`
- **참가자 경험**: `xor` / `rol` / `cmp` 세 명령만 보인다. objdump만으로 풀리는 워밍업.
- **역산**: `x = rotr32(P1_TARGET, P1_ROT) ^ P1_KEY` — 1스텝
- **유일성**: 회전·XOR 모두 전단사 → 자명
- **시드 파라미터**: `P1_KEY`(32bit), `P1_ROT`(3~29), `P1_TARGET`(정답에서 역산)
- **퇴화 배제**: `P1_KEY != 0`, `P1_ROT`가 8의 배수가 아닐 것(단순 바이트 스왑으로 보이는 것 방지)

### phase_2 — 쉬움 · 16비트 LFSR 점화식

- **입력**: `%d %d %d %d %d %d` 정수 6개
- **판정**:
  ```
  a[0] == P2_SEED
  for i in 1..5:
      t = a[i-1];  n = (t << 1) & 0xFFFF
      if (t & 0x8000) n ^= P2_POLY
      a[i] == n
  ```
- **참가자 경험**: 첫 값은 `cmp`에서 바로 읽히고, 나머지는 시프트·XOR 루프를 5회 손으로 돌린다.
- **역산**: 순방향 5스텝
- **유일성**: 결정적 점화식 → 자명
- **시드 파라미터**: `P2_SEED`(1~0xFFFF), `P2_POLY`(16bit)
- **퇴화 배제**: 6개 값이 서로 다를 것, 0이 나오지 않을 것, 등차·등비 수열로 보이지 않을 것

### phase_3 — 중간 · 4×4 격자 순회

- **입력**: `%d %d` 시작 좌표 `r c`
- **데이터**: `unsigned char p3_grid[4][4]` (16바이트)
- **판정**:
  ```
  0 <= r,c <= 3
  sum = 0
  repeat P3_STEPS(=6) times:
      v    = p3_grid[r][c]
      dir  = v & 3                    /* 0=상 1=우 2=하 3=좌 */
      step = ((v >> 2) & 3) + 1
      sum += (v >> 4) & 0xF
      r = (r + dr[dir]*step) & 3      /* 토러스 wrap */
      c = (c + dc[dir]*step) & 3
  r*4 + c == P3_GOAL  &&  sum == P3_SUM
  ```
- **참가자 경험**: `x/16xb`로 격자를 덤프하고 각 칸에 화살표를 그리면 함수 그래프가 보인다. 목표 칸에서 거꾸로 6칸 추적.
- **유일성**: 생성기가 **16개 시작점 전수 시뮬레이션** → `(GOAL, SUM)`을 만족하는 시작점이 정확히 1개인 격자만 채택
- **시드 파라미터**: `p3_grid[16]`, `P3_GOAL`, `P3_SUM`
- **퇴화 배제**: 정답 경로가 한 칸에 고정(자기 루프)되지 않을 것, 서로 다른 칸을 3개 이상 방문할 것

### phase_4 — 중간 · 모듈러 역산 + 비트 역순

- **입력**: `%d %d` 정수 2개 `x y`
- **판정**:
  ```
  1 <= x < P4_MOD
  (x * P4_MUL) % P4_MOD == P4_RES
  y == bit_reverse(x, 11)
  ```
- **참가자 경험**: 이 phase의 진짜 관문은 **gcc가 `%` 상수 나눗셈을 magic-number 곱셈+시프트로 컴파일한다**는 사실이다. `imul`+`sar` 조합이 사실 나머지 연산임을 알아채야 한다. 그 뒤엔 확장 유클리드 몇 스텝.
- **역산**: `x = P4_RES * inverse(P4_MUL) mod P4_MOD`, `y`는 파생 검산값
- **유일성**: `P4_MOD` 소수이고 `gcd(P4_MUL, P4_MOD) = 1` → 해가 정확히 하나
- **시드 파라미터**: `P4_MOD`(1021·1031·1049·1063·2039 등 소수 풀), `P4_MUL`(2 ≤ MUL < MOD), `P4_RES`
- **퇴화 배제**: `P4_MUL != 1`, 정답 `x`가 1이나 MOD-1이 아닐 것, `x`가 11비트 안에 들 것

### phase_5 — 어려움 · 이진 트리 경로

- **입력**: `%s` 6자 문자열, 각 문자는 `L` 또는 `R`
- **데이터**: `unsigned p5_tree[127]` (heap 순서 완전이진트리, 깊이 7)
- **판정**:
  ```
  strlen == 6
  acc = P5_INIT;  idx = 0
  for i in 0..5:
      v    = p5_tree[idx]
      want = (acc ^ v) & 1              /* 이번 스텝 방향이 여기서 결정된다 */
      got  = (buf[i] == 'R')            /* L/R 외 문자는 폭발 */
      got == want
      idx  = 2*idx + 1 + want
      acc  = rotl32(acc, 5) + v
  acc == P5_TARGET
  ```
- **핵심 설계**: 경로가 누산기에서 **결정**되므로 64가지 브루트포스가 필요 없다. 참가자는 방문하는 노드 값만 읽으며 6스텝 순방향으로 진행하면 답이 나온다. NFR-02·03을 만족한다.
- **참가자 경험**: heap 인덱싱(`lea (%rax,%rax,1)` 류)과 rotl·XOR이 결합된 형태. 트리 노드 접근 주소 계산을 읽어야 한다.
- **유일성**: 각 스텝 방향이 결정적 → 자명. `P5_TARGET`은 오답 조기 차단용 검산.
- **시드 파라미터**: `p5_tree[127]`, `P5_INIT`, `P5_TARGET`(정답 경로에서 계산)
- **퇴화 배제**: 정답 경로가 `LLLLLL`·`RRRRRR` 같은 단조 문자열이 아닐 것, L과 R이 각각 최소 2회 등장할 것

### phase_6 — 어려움 · 비트마스크 포함 사슬

- **입력**: `%d %d %d %d %d %d` — 1~6의 순열
- **데이터**:
  ```c
  struct p6_node { unsigned mask; int id; struct p6_node *next; };
  static struct p6_node p6_nodes[6];   /* 물리 배치는 셔플, next로 체인 연결 */
  ```
- **판정**:
  ```
  a[0..5]가 1..6의 순열
  prev = 0
  for i in 0..5:
      n = p6_lookup(a[i])               /* next 체인을 따라가 id 매칭 */
      (prev & n->mask) == prev          /* prev ⊂ n->mask */
      prev = n->mask
  prev == P6_FULL
  ```
- **핵심 설계**: 마스크 6개를 비트로 적어놓으면 사슬 `m1 ⊂ m2 ⊂ … ⊂ m6`의 순서가 눈에 보인다. 720가지 순열 탐색이 필요 없다. 정렬처럼 보이지만 기준이 **집합 포함관계**라 원본 phase_6과 성격이 다르다.
- **참가자 경험**: `next` 포인터 체인 순회로 gdb 포인터 추적을 겸한다. 마스크 6개(24바이트)만 읽으면 된다.
- **유일성**: 엄격 증가 사슬이므로 전순서가 유일
- **시드 파라미터**: 각 노드 `mask`(사슬로 생성), 배열 물리 배치 셔플 순서, `next` 연결 순서, `P6_FULL`
- **퇴화 배제**: 각 단계에서 최소 1비트 이상 추가되되 popcount 증가폭이 일정하지 않을 것(자명한 패턴 방지), 배열 물리 순서가 정답 순서와 다를 것

### secret_phase — 비트 역순 + 모듈러

- **트리거**: phase_4 정답 줄을 `"%d %d %s"`로 재파싱해 세 번째 토큰이 `PS_WORD`와 일치하면, 6 phase 해제 시점에 진입
- **입력**: `%d` 정수 1개
- **판정**:
  ```
  1 <= x <= 0xFFFF
  r = bit_reverse(x, 16)
  (r * PS_MUL) % PS_MOD == PS_RES        /* PS_MOD = 65537, 소수 */
  popcount32(x) == PS_POP
  ```
- **핵심 설계**: 65537이 소수이므로 `r`이 모듈러 역원으로 **한 번에 결정**된다. phase 4에서 익힌 확장 유클리드를 재사용하고, 비트 역순을 한 번 더 적용하면 x가 나온다. 탐색 요소가 없다. popcount는 검산용 파생 조건.
- **유일성**: 생성기가 1..65535 **전수 조사**로 조건을 만족하는 x가 정확히 1개인 파라미터 조합만 채택하며, `tools/check_secret_unique.py`가 시드마다 이를 독립적으로 재확인한다
- **시드 파라미터**: `PS_MUL`(2 ≤ MUL < 65537), `PS_RES`, `PS_POP`(4~12), `PS_WORD`(단어 풀에서 선택)

## 4. 데이터 모델 — `bombdata.h` / `bombdata.c`

`gen_bomb.py`가 두 파일로 나누어 생성한다. 헤더에는 스칼라 상수와 `extern` 선언만 두고 테이블 정의는 `.c`에 둔다. `support.c`처럼 테이블이 필요 없는 번역 단위가 헤더만 포함해도 `-Wall` 경고가 나지 않고, 테이블이 **이름 있는 전역 심볼**로 남아 참가자가 gdb에서 `x/16xb &p3_grid` 로 바로 덤프할 수 있다.

```c
/* bombdata.h */
#define BOMB_SEED 20260215

#define P1_KEY      0xE619D244u
#define P1_ROT      6
#define P1_TARGET   0x84D7AD79u
/* ... P2_*, P3_*, P4_*, P5_*, P6_*, PS_* ... */

extern const unsigned char p3_grid[4][4];
extern const unsigned      p5_tree[127];
extern const unsigned      p6_masks[6];   /* 물리 슬롯별 마스크 */
extern const int           p6_ids[6];     /* 물리 슬롯별 id */
extern const int           p6_chain[6];   /* next 연결 순서 (물리 슬롯) */

#define PS_MOD   65537
#define PS_WORD  "cinnabar"
```

```c
/* bombdata.c */
#include "bombdata.h"
const unsigned char p3_grid[4][4] = { ... };
/* ... */
```

## 5. 생성기 `tools/gen_bomb.py`

```
python3 tools/gen_bomb.py --seed N
  → src/bombdata.h
  → build/seed-N/solution.txt
  → build/seed-N/SOLUTION.md
```

구조:

- `random.Random(seed)` 하나로 모든 샘플링 — 결정성(NFR-07) 보장
- phase별 `gen_phaseN(rng) -> (params, answer)`: **샘플링 → 퇴화 검사 → 유일성 검증 → 실패 시 재샘플링** 루프
- C 로직의 **참조 구현**(`check_phaseN`)을 Python으로 보유. 정답 도출과 유일성 검증에 사용하며, `verify.sh`가 C 바이너리와 대조하므로 두 구현의 불일치는 빌드 단계에서 잡힌다.

| phase | 유일성 검증 방법 |
|---|---|
| 1, 2, 5 | 구조적 보장(전단사·결정적) + 퇴화 케이스 배제 |
| 3 | 16개 시작점 전수 시뮬레이션 → 해 1개 확인 |
| 4 | `P4_MOD` 소수 판정 + `gcd(P4_MUL, P4_MOD) == 1` |
| 6 | 엄격 증가 마스크 사슬 구성 → 전순서 유일 |
| secret | 1..65535 전수 → 해 1개인 파라미터만 채택 |

## 6. 빌드 `Makefile`

```make
CC      = gcc
CFLAGS  = -O1 -g -Wall -no-pie -fno-stack-protector
SEED   ?= 0
```

타깃: `bomb`(컴파일) / `src/bombdata.h`(생성기 호출) / `dist`(배포 패키지) / `verify` / `clean` / `distclean`

`make dist SEED=n` 산출물:

```
dist/bomb-n/
├── bomb          (심볼 유지, -no-pie)
├── bomb.c        (배포용 사본)
├── README.md
└── PRIMER.md
```

`phases.c`·`support.c`·`util.c`·`bombdata.h`·`solution.txt`·`SOLUTION.md`는 **포함하지 않으며**, dist 타깃이 존재 여부를 검사해 발견 시 실패한다(FR-08 / AC-06).

## 7. 검증 `tools/verify.sh`

```
bash tools/verify.sh [시작시드] [끝시드]
```

시드마다:

1. `make SEED=n` 빌드
2. 정답 파일 주입 → 6 phase 해제 + 종료 코드 0 확인 (AC-01)
3. secret 토큰 포함 정답 주입 → secret 해제 확인 (AC-02)
4. phase별 오답 3종(경계값·off-by-one·형식 오류) 주입 → **정확히 그 phase에서** 폭발 확인 (AC-03)
5. phase 3: 16개 시작점을 C 바이너리로 직접 전수 실행 → "Halfway there!"가 정확히 1회 나오는지 확인. secret: `tools/check_secret_unique.py`가 1..65535를 전수 조사해 해가 1개이고 생성기 정답과 일치하는지 재확인 (AC-04)
6. `bomb.log` 기록 확인 (AC-07)
7. dist 금지 파일 부재 확인 (AC-06)

하나라도 실패하면 비영 종료(FR-10).

## 8. 문서

| 파일 | 대상 | 내용 |
|---|---|---|
| `docs/README.md` | 참가자 | 대회 규칙, 실행법(`./bomb`, `./bomb sol.txt`), 폭발·로그 동작, 제출 방법, 도구 정책 |
| `docs/PRIMER.md` | 참가자 | **개념 위주 교육자료, 스포일러 없음**: x86-64 레지스터와 System V 호출 규약·스택 프레임 / `objdump -d` 읽는 법 / gdb 필수 동작(`break`·`run`·`stepi`·`info registers`·`x` 포맷·`disas`) / 비트연산 어셈블리 패턴(`shl`·`sar`·`rol`·`and`·`xor`·`test`·`popcnt`) / 배열·구조체 주소 계산(`lea`, 스케일 인덱스) / `cmp`·`test`와 부호·무부호 분기 / 상수 나눗셈이 magic-number 곱셈으로 바뀌는 현상 |
| `docs/SOLUTION.md` | 출제자 (자동 생성) | phase별 정답·설계 의도·도출 과정·예상 소요 시간·**3단계 힌트 문구**(① 개념 ② 어디를 볼지 ③ 구체적 방법) |

## 9. 개발 환경

빌드·실행은 Linux에서 수행한다. 저장소가 Windows 경로에 있는 경우 WSL에서 `/mnt/<드라이브>/<경로>`로 접근한다. WSL Ubuntu-22.04에 `build-essential`·`gdb` 설치가 선행 조건이다.

## 10. 리스크

| 리스크 | 완화 |
|---|---|
| C 구현과 Python 참조 구현의 불일치 | `verify.sh`가 실제 바이너리로 정답·오답을 모두 실행해 대조 |
| gcc 버전에 따라 어셈블리 패턴이 달라져 난이도가 변동 | 대회에 쓸 단일 빌드 환경(WSL 또는 Docker 이미지)을 고정하고 최종 바이너리로 리허설 |
| 시드에 따른 난이도 편차 | 퇴화 케이스 배제 규칙을 phase마다 명시하고 20 시드 일괄 검증 |
| 분량 초과 | `P3_STEPS`(6→4), phase 5 경로 길이(6→5)를 상수만 바꿔 조절 가능하게 설계 |
