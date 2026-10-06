# Research: CMU 원본 폭탄 환경 실측

- **대상**: CS:APP 3e 자습용 배포본 `bomb.tar` (http://csapp.cs.cmu.edu/3e/bomb.tar, 2015-06-10, `bomb` 26,406 B)
- **실측일**: 2026-10-05
- **보관 위치**: `ref/cmu-selfstudy/` (`.gitignore` 처리 — 저장소에 커밋하거나 학생에게 배포하지 않는다)
- **방법**: pyelftools(ELF·DWARF), capstone(디스어셈블)

이 문서에는 원본의 **정답을 적지 않는다**. 구조와 환경만 기록한다.

---

## 1. 툴체인과 빌드 플래그

| 항목 | 실측값 | 근거 |
|---|---|---|
| 컴파일러 | **GCC 4.8.1** (`Ubuntu 4.8.1-2ubuntu1~12.04`) | `.comment` |
| 빌드 OS | **Ubuntu 12.04** (crt 파일은 시스템 GCC 4.6.3 것) | `.comment`의 두 번째 항목 `Ubuntu/Linaro 4.6.3-1ubuntu5`, `.jcr` 섹션, `call_gmon_start` |
| 플래그 (`bomb.c`) | `-mtune=generic -march=x86-64 -ggdb -O1 -fstack-protector` | `DW_AT_producer` |
| 디버그 정보 | **`bomb.c` 컴파일 단위 하나만** 존재 | DWARF CU 목록 |
| phase·보조 코드 | 디버그 정보 없음. 명령어 모양으로 보아 같은 컴파일러 `-O1` | 디스어셈블 |
| 바이너리 형식 | x86-64 `ET_EXEC` (**non-PIE**), 진입점 `0x400c90`, `.text`가 `0x400xxx` | ELF 헤더 |
| 심볼 | **strip 안 함**. 전역·지역 심볼 전부 존재 (`array.3449` 같은 정적 지역 배열 포함) | `.symtab` |
| `endbr64` | 없음 (GCC 4.8에는 CET 없음) | 디스어셈블 |
| 주소 지정 | 상수·문자열을 절대 즉시값으로 참조 (`mov $0x402400,%esi`) | 디스어셈블 |

### 스택 카나리가 있는 함수

`-fstack-protector`(GCC 4.8 기본 규칙: 8바이트 이상 char 배열을 가진 함수만 보호)의 결과로, **두 함수에만** 카나리가 있다.

| 함수 | 카나리 | 이유 |
|---|---|---|
| `phase_5` | 있음 | 스택에 변환 결과 문자열 버퍼 |
| `phase_defused` | 있음 | secret 진입 문자열을 받을 `char[]` |
| 나머지 전부 | 없음 | — |

→ 카나리 위치는 직접 넣는 것이 아니라, **같은 컴파일러·같은 플래그로 같은 모양의 C를 빌드하면 자동으로 같아진다.**

## 2. 심볼 구성

| 분류 | 심볼 |
|---|---|
| phase | `phase_1`~`phase_6`, `secret_phase` |
| phase 보조 | `func4`(phase 4 재귀), `fun7`(secret 재귀) |
| 데이터 | `node1`~`node6`(16 B, phase 6 연결 리스트), `n1`, `n21`, `n22`, `n31`~`n34`, `n41`~`n48`(24 B, secret BST), `array.3449`(16 B, phase 5 표) |
| 입력 | `read_line`, `skip`, `blank_line`, `read_six_numbers`, `input_strings`(80 B × 20줄), `num_input_strings`, `infile` |
| 문자열 | `string_length`, `strings_not_equal` |
| 폭탄 | `initialize_bomb`, `initialize_bomb_solve`, `explode_bomb`, `phase_defused`, `invalid_phase`, `sig_handler` |
| 서버 보고 | `init_driver`, `driver_post`, `submitr`, `rio_readlineb`, `init_timeout`, `sigalrm_handler`, `host_table`, `bomb_id`, `scratch` (자습용에서도 코드는 들어 있음) |

## 3. 동작 실측

### 입력 처리 (`read_line`)
- `skip()`이 `fgets(…, 80, infile)`로 읽고 `blank_line()`이면 다음 줄로 넘어간다 → **빈 줄 무시**.
- 파일 EOF: `infile == stdin`이면 `Error: Premature EOF on stdin` 후 `exit(8)`. 아니면 `getenv("GRADE_BOMB")`가 있으면 `exit(0)`, 없으면 **`infile = stdin`으로 바꿔 이어서 읽는다.**
- 길이 78자 초과: `Error: Input line too long` 출력, 해당 줄을 `***truncated***`로 바꾸고 폭발.
- 개행 문자 제거 후 `input_strings[num_input_strings++]`에 보관.

### 판정과 흐름
- `explode_bomb`: `BOOM!!!`, `The bomb has blown up.` 출력 후 `exit(8)`. (과제용 버전은 그 전에 서버 보고)
- `phase_defused`: `num_input_strings == 6`일 때만 4번째 줄(`input_strings + 240`)을 `"%d %d %s"`로 다시 읽고, 문자열이 일치하면 secret 진입 메시지 2줄 후 `secret_phase()` 호출. 마지막에 축하 메시지 출력.
- `secret_phase`: `read_line` → **`strtol(…, NULL, 10)`**, 범위 `1..1001` 검사 → `fun7(&n1, x)`가 특정 값을 반환해야 함.
- `initialize_bomb`: `signal(SIGINT, sig_handler)`만 등록. `sig_handler`는 메시지 → `sleep(3)` → `Well...` → `sleep(1)` → `OK. :-)` → `exit(16)`.
- `main`의 단계별 메시지는 `puts`로 출력되며 배포용 `bomb.c`에 그대로 보인다.

### phase별 구조 (자습용 버전)

| phase | 입력 | 구조 | 판정 시점 |
|---|---|---|---|
| 1 | 문장 | `strings_not_equal(input, 전역 문자열)` | 1회 |
| 2 | 6개 정수 | `read_six_numbers` → 첫 값 고정 → 루프에서 앞 값으로 다음 값 검사 | **원소마다** |
| 3 | `"%d %d"` | 개수 검사 → 첫 수 `ja 7` 범위 검사 → **점프 테이블** `jmp *0x402470(,%rax,8)` → case별 상수와 둘째 수 비교 | 단계마다 |
| 4 | `"%d %d"` | 개수·범위(`jbe 0xe`) → `func4(x, 0, 14)` **이진 탐색형 재귀** 반환값 검사 → 둘째 수 검사 | 단계마다 |
| 5 | 6글자 | `string_length == 6` → 글자마다 `& 0xf`로 `array.3449` 인덱싱해 스택 버퍼에 작성 → `strings_not_equal` | **마지막 1회** (카나리) |
| 6 | 6개 정수 | 범위(1~6)·중복 이중 루프 → `7-x` 변환 → `node` 포인터를 스택 배열에 배치 → 재연결 → **내림차순** 검사 | 정렬 검사는 **노드마다** |
| secret | 정수 | `strtol` → 범위 → `fun7` **BST 재귀 경로 인코딩** (`2*f(left)`, `2*f(right)+1`, 없으면 -1) | 1회 |

## 4. 우리 폭탄(001 빌드, seed-1)과의 차이

| 항목 | 원본 | 001 빌드 | 003에서 |
|---|---|---|---|
| 컴파일러 | GCC 4.8.1 | 최신 GCC (Ubuntu 22.04+) | **GCC 4.8 툴체인으로 빌드** |
| `endbr64` | 없음 | 모든 함수 앞에 있음 | 툴체인을 맞추면 자동으로 사라짐 |
| 디버그 정보 | `bomb.c`만 | 전체 (phase 지역변수·구조체 필드·빌드 경로 노출) | `bomb.c`만 `-ggdb` |
| 카나리 | `-fstack-protector` | 꺼짐 | `-fstack-protector` |
| 주소 지정 | 절대 즉시값 | RIP 상대 주소 (`lea rsi,[rip+…]`) | 툴체인을 맞추면 원본과 같아짐 |
| 파일 EOF | stdin으로 전환 | 종료 | 원본과 같게 |
| 빈 줄 | 무시 | 입력으로 처리 | 원본과 같게 |
| secret 입력 | `strtol` | `sscanf` | 원본과 같게 |

## 5. 툴체인 재현 방안

| 방안 | 컴파일러 | 원본과의 일치도 | 비고 |
|---|---|---|---|
| **A. Ubuntu 12.04 + toolchain PPA** | GCC 4.8.1-2ubuntu1~12.04 (원본과 같은 패키지) | 최고 (crt까지 같음) | 12.04는 지원 종료. `old-releases.ubuntu.com`과 Launchpad PPA 보관본에 의존 |
| **B. Ubuntu 14.04** | GCC 4.8.4 (기본 컴파일러) | 높음 (4.8 버그 수정판 차이) | 패키지 확보가 쉬움. crt는 다름 |

- 두 방안 모두 컨테이너(또는 chroot)에서 빌드하고, 결과 바이너리는 Ubuntu 22.04/24.04 서버에서 실행한다(glibc는 하위 호환).
- **채택 기준**: 원본 phase들을 직접 C로 재구성해 각 툴체인으로 빌드했을 때, 원본과 **명령어 단위로 일치**하는 방안을 채택한다(spec AC-05). A를 우선 시도하고, 패키지 확보가 안 되면 B로 간다.

## 6. 결과: 방안 A 채택, AC-05 통과 (2026-10-05)

### 툴체인
- [`toolchain/Dockerfile`](../../toolchain/Dockerfile): `ubuntu:12.04` + `old-releases.ubuntu.com` + Launchpad PPA 보관 파일에서 받은 `gcc-4.8 4.8.1-2ubuntu1~12.04` 패키지 묶음.
- 이미지 안의 버전: `gcc (Ubuntu 4.8.1-2ubuntu1~12.04) 4.8.1`, `GNU ld 2.22`, `EGLIBC 2.15-0ubuntu10.23`.
- 빌드 결과물은 Ubuntu 22.04(WSL2)에서 그대로 실행된다.

### 보정 빌드
- 원본 함수들을 C로 재구성(`ref/calib/`, git 제외)해 `-O1 -fstack-protector -mtune=generic -march=x86-64`(`bomb.c`만 추가로 `-ggdb`)로 빌드했다.
- [`tools/asmdiff.py`](../../tools/asmdiff.py)로 비교한 결과, **22개 함수 전부 명령어 단위로 일치**했다: `main`, `phase_1`~`6`, `func4`, `fun7`, `secret_phase`, `sig_handler`, `invalid_phase`, `string_length`, `strings_not_equal`, `initialize_bomb`, `initialize_bomb_solve`, `blank_line`, `skip`, `explode_bomb`, `read_six_numbers`, `read_line`, `phase_defused`.
  - 비교할 때 주소는 정규화한다. 분기는 함수 안의 오프셋으로, 호출은 호출 대상 심볼 이름으로, RIP 상대 참조는 가리키는 전역 변수 이름으로 바꾼다. 상수는 그대로 비교한다.
- `.comment`(두 줄 모두), DWARF CU 목록(`bomb.c` 하나), `DW_AT_producer` 문자열, `ET_EXEC`까지 원본과 같다.
- `phase_5`의 특이한 스택 사용(글자를 `[rsp]`에 한 바이트 저장했다가 8바이트로 다시 읽음)과 카나리 위치는 직접 손대지 않았는데도 그대로 재현됐다. NFR-04("흉내 내지 말고 툴체인으로 같아지게")가 실제로 성립한다는 증거다.

### 보정에서 얻은 원본 소스 작성 관례 (003 구현 시 그대로 따름)
| 관찰 | 소스 작성 방식 |
|---|---|
| `phase_defused`가 `secret_phase`를, `read_line`이 `skip`을 부르기 직전에 `mov $0,%eax` | 두 함수는 **매개변수 목록 없이** `void secret_phase();`, `char *skip()`처럼 선언한다 |
| `phase_5`의 표 이름이 `array.3449` | 표는 phase 함수 안의 `static char array[]`로 둔다 |
| 노드 크기 16 B / 24 B | `struct { int value; int index; struct node *next; }`, `struct { int value; struct tree *left, *right; }` |
| `blank_line` 루프 모양 | `if (!isspace(*input++)) return 0;` 형태로 써야 일치 |
| 메시지 출력 | 개행으로 끝나는 고정 문자열 `printf`는 컴파일러가 `puts`로 바꾼다. 소스에서는 `printf`를 그대로 쓴다 |
