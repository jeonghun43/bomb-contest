# Bomb Lab 연습 서버

시스템프로그래밍 수업의 **CMU Bomb Lab 과제**를 미리 연습하는 서버와 문제은행입니다. Bomb Lab 교육 뒤 **2주** 동안 서버를 열어 두고, 학생들이 과제가 나왔을 때 **하루 안에 전부 해제할 수 있는 실력**을 기르는 것이 목표입니다.

모든 폭탄은 원본 CMU 폭탄과 **같은 컴파일러(GCC 4.8.1)와 같은 플래그**로 빌드합니다. CMU 구조 폭탄은 원본과 명령어 단위로 모양이 같고, 시드마다 상수와 정답만 다릅니다.

---

## 학생이 받는 폭탄 세 종류

| 위치 | 이름 | 무엇인가 | 점수 | 해설·힌트 | 다시 받기 |
|---|---|---|---|---|---|
| `~/drills/d0` ~ `d9` | **개념 드릴** | 과제의 개념 하나씩을 짧게 연습하는 3단계 미니 폭탄 10개 | 진도표만 | ✅ | ✅ 학생이 |
| `~/practice` | **연습 폭탄** | **CMU 구조 폭탄**: 원본 과제와 같은 6단계 + 숨은 단계. 원본과 같은 코드 모양, 상수·정답만 다름 | ✗ | ✅ | ✅ 학생이 |
| `~/bomb` | **과제형 폭탄** | **연습 폭탄과 같은 CMU 구조 폭탄**(시드만 다름). 실제 과제처럼 1인 1개, 점수와 폭발 감점이 스코어보드에 올라감 | ✅ | ✗ | 운영자만 |

`~/bomb`과 `~/practice`는 **같은 종류의 폭탄**입니다. 둘 다 이 저장소의 생성기로 만든 CMU 구조 폭탄이고, 원본 CMU 폭탄(CS:APP 자습용 배포본) 자체는 서버에 올리지 않습니다. 원본을 분석해 같은 동작의 C 코드를 새로 쓰고 같은 컴파일러로 빌드했기 때문에 코드 모양·메시지·입력 처리는 원본과 같고, phase 1 문장(직접 만든 문장 풀), 수열의 첫 값, case 값, 표, 노드·트리 값, 숨은 단계 단어 같은 **상수와 정답만** 학생마다 다릅니다. 원본 풀이법은 통하지만 원본 정답은 통하지 않습니다. 차이는 운영 방식뿐입니다: `~/bomb`은 실제 과제처럼 한 번만, 점수를 걸고, 도움 없이 풉니다. `~/practice`는 해설·힌트를 보며 몇 번이든 새로 받아 반복합니다.

권장 순서: 드릴 D0 → D9 → 연습 폭탄(여러 번) → 과제형 폭탄.

---

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `bank/` | 문제은행. 생성기·판정기(Python)와 폭탄 C 템플릿(`bank/csrc/`) |
| `bank/csrc/common/` | 모든 폭탄이 쓰는 런타임: `main`, `read_line`, `phase_defused`, 서버 보고(`driverlib.c`) |
| `bank/csrc/cmu/` | CMU 구조 폭탄 phase 템플릿 |
| `bank/csrc/drills/` | 개념 드릴 템플릿 |
| `toolchain/Dockerfile` | 원본과 같은 컴파일러(GCC 4.8.1, Ubuntu 12.04) 이미지 |
| `tools/` | 빌드(`buildbomb.py`), 검증(`verify_bank.py`, `fuzz_bank.py`, `runtime_check.sh`), 원본 대조(`asmdiff.py`, `parity.sh`, `elfcheck.py`), 서버 셀프테스트 |
| `server/` | 연습 서버: 기록 데몬, 빌더, 웹 스코어보드, 운영자 CLI `bomblabctl`, 학생 CLI `bomblab`, 설치 스크립트 |
| `docs/` | 학생 문서: [README](docs/README.md)(안내), [DRILLS](docs/DRILLS.md)(드릴), [PRIMER](docs/PRIMER.md)(개념 정리) |
| `specs/` | 설계 문서: [003 문제은행](specs/003-practice-bank/spec.md) (spec·plan·research·tasks), [002 서버 2판](specs/002-contest-server/spec.md) |
| `previous/` | 보관용: 처음 만든 대회용 자체제작 폭탄과 대회 서버 ([설명](previous/README.md)) |
| `ref/` | (git 제외, 개발 PC에만) 원본 CMU 자습용 폭탄과 보정용 재구성 소스. 재배포 금지 |

---

## 어떤 문서를 보면 되나

| 하려는 일 | 문서 |
|---|---|
| **실서버에 올리기·운영하기** | [server/README.md](server/README.md) — EC2/노트북 설치, 설정, 학생 등록, 운영, 상황별 대처, 리허설 |
| 학생에게 안내하기 | [docs/README.md](docs/README.md), [docs/DRILLS.md](docs/DRILLS.md) |
| 학생 질문에 답하기 | [server/README.md](server/README.md) 8장 "학생 질문 대응", 힌트 전체 목록 [server/HINTS.md](server/HINTS.md), `sudo bomblabctl solution <학생> <폭탄>` |
| 왜 이렇게 만들었는지 | [specs/003 spec](specs/003-practice-bank/spec.md), [plan](specs/003-practice-bank/plan.md) |
| 원본 폭탄 실측·검증 결과, 드릴 분량·난이도, 파일럿 기록표 | [specs/003 research](specs/003-practice-bank/research.md) |
| 무엇을 했고 무엇이 남았는지 | [specs/003 tasks](specs/003-practice-bank/tasks.md) |
| 서버 요구사항과 결정 사항 | [specs/002 spec](specs/002-contest-server/spec.md) |

---

## 개발 PC에서 (Linux 또는 WSL, Docker 필요)

```bash
make toolchain                       # GCC 4.8.1 이미지 (처음 한 번)
make bomb KIND=cmu SEED=7            # CMU 구조 폭탄 → build/cmu-7/
make bomb KIND=drill:d3 SEED=7       # 드릴 D3 → build/drill-d3-7/
make kinds                           # 만들 수 있는 종류
make verify                          # 문제은행 전체 + 런타임 + 원본 대조(ref/ 있을 때)
make selftest                        # 서버 셀프테스트 (root 불필요)
```

빌드 디렉터리의 `answers.txt`·`SOLUTION.md`에 정답과 해설이 있습니다. `build/`는 git에서 제외되어 있으니 커밋하지 마세요.

---

## 현재 상태 (2026-10-06)

- 완료: 원본 실측·툴체인 보정, 공통 런타임, CMU 구조 폭탄(자습용 계열 7개), 개념 드릴 10개, 연습 서버, 문서. 자동 검증 전부 통과.
- 남은 일: 실서버 리허설(root 권한 경로 확인), 파일럿, 다른 학기 변형 계열 조사(선택). 자세히는 [tasks](specs/003-practice-bank/tasks.md) Phase H.
