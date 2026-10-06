# Tasks: 대회용 신규 Bomb Lab

- **Feature ID**: 001-new-bomb
- **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

`[P]` = 앞선 태스크가 끝났다면 서로 병렬로 진행 가능.

---

## Phase A — 개발 환경

- [x] **T001** WSL Ubuntu-22.04에 `build-essential`, `gdb` 설치
  - 검증: `gcc 11.4.0`, `GNU Make 4.3`, `objdump 2.38` 확인
  - 의존: 없음

## Phase B — 기반 골격

- [x] **T002** `src/bomb.h` — 공통 선언, phase 프로토타입, 헬퍼 선언
- [x] **T003** `src/util.c` — `read_line`, `read_six_numbers`, `get_phase_input`, `rotl32`, `rotr32`, `bit_reverse`, `popcount32`
- [x] **T004** `src/support.c` — `initialize_bomb`, `explode_bomb`, `bomb_log`, `phase_defused`, secret 트리거 배선
  - 검증: 폭발 시 `bomb.log` 기록 + `exit(8)` 확인
- [x] **T005** `src/bomb.c` — main 루프 (stdin / 정답 파일 분기, phase 1~6 호출)
  - 검증: 판정 로직이 노출되지 않음 (호출 순서와 안내 문구만)

## Phase C — 생성기 골격

- [x] **T006** `tools/gen_bomb.py` 골격 — `--seed` CLI, `random.Random(seed)`, `bombdata.h`/`bombdata.c` 렌더러, `solution.txt`·`solution_secret.txt`·`SOLUTION.md` 출력
  - 검증: 같은 시드 → 동일 산출물 (결정성)

## Phase D — Phase 구현

- [x] **T007** phase_1 — 회전 + XOR 역산
  - 어셈블리 확인: `xor` → `call rotl32`(내부 `rol`) → `cmp` 3단계로 노출
- [x] **T008** phase_2 — 16비트 LFSR 점화식
  - 퇴화 배제 적용: 6개 값 상이, 0 미발생, 차분 4종 이상, 탭 분기 2~4회
- [x] **T009** phase_3 — 4×4 격자 순회
  - 유일성: 16개 시작점 전수 시뮬레이션. 시작점 `(0,0)` 배제
  - 어셈블리 확인: `shr $0x4` / `shr $0x2`+`and $3` / `and $3` 비트 언패킹, `p3_grid`·`p3_dr`·`p3_dc` 심볼 노출
- [x] **T010** phase_4 — 모듈러 역산 + 비트 역순
  - 어셈블리 확인: `imul $0xbdd265f5` → `shr $0x20` → `sar` → `imul $0x565` → `sub` magic-number 나눗셈 노출
- [x] **T011** phase_5 — 이진 트리 경로
  - 퇴화 배제: 정답 경로에 L·R 각각 최소 2회
- [x] **T012** phase_6 — 비트마스크 포함 사슬
  - 어셈블리 확인: `and (%rbx),%eax`+`cmp` 부분집합 검사, `mov 0x8(%rbx),%rbx` 연결리스트 순회
- [x] **T013** secret_phase — 비트 역순 + mod 65537 역산, phase 4 줄의 추가 토큰으로 진입
  - 유일성: `tools/check_secret_unique.py`가 1..65535 전수 재확인

## Phase E — 빌드·검증

- [x] **T014** `Makefile` — `all` / `gen` / `bomb` / `dist` / `verify` / `clean` / `distclean`
  - `dist`가 금지 파일 부재를 검사. 패키지 = `bomb`, `bomb.c`, `README.md`, `PRIMER.md` 4개
- [x] **T015** `tools/verify.sh` — AC-01~07 자동 검증
- [x] **T016** 시드 20종 일괄 검증 — `bash tools/verify.sh 1 20` → **501 pass / 0 fail** (25초)

## Phase F — 문서

- [x] **T017** `docs/README.md` — 참가자 안내 (규칙·실행법·폭발/로그·힌트·채점·제출)
- [x] **T018** `docs/PRIMER.md` — 참가자 교육자료 (개념 위주, 스포일러 없음)
- [x] **T019** `SOLUTION.md` 생성 로직 — phase별 정답·의도·도출 과정·예상 시간·3단계 힌트

## Phase G — 리허설·보정

- [ ] **T020** 대표 시드 1개로 실제 풀이 리허설 — 생성기 정답을 보지 않고 objdump/gdb만으로 6 phase + secret 해제, 구간별 소요 시간 측정
  - **출제자가 직접 수행해야 하는 항목.** 어셈블리 정적 점검(각 phase에 필요한 정보가 모두 노출되는지)은 T007~T013에서 완료했으나, 체감 소요 시간은 사람이 재야 한다.
  - 검증: 목표 시간(6 phase 4~6시간) 범위 (AC-08)
  - 의존: T016, T019

- [ ] **T021** 리허설 결과 반영 — 난이도 상수 보정(`P3_STEPS`, phase 5 경로 길이), 힌트 문구 다듬기, `SOLUTION.md` 시간 추정 갱신
  - 의존: T020

- [ ] **T022** 최종 배포 패키지 생성 — 참가자 수만큼 시드 배정, `make dist` 일괄 실행, 금지 파일 부재 최종 확인
  - 의존: T021

---

## 진행 현황

| Phase | 태스크 | 상태 |
|---|---|---|
| A 환경 | T001 | 완료 |
| B 골격 | T002~T005 | 완료 |
| C 생성기 | T006 | 완료 |
| D Phase 구현 | T007~T013 | 완료 |
| E 빌드·검증 | T014~T016 | 완료 (501 pass / 0 fail) |
| F 문서 | T017~T019 | 완료 |
| G 리허설 | T020~T022 | 대기 (출제자 수행 필요) |

## 남은 결정 사항

- 참가자 Linux 실행 환경 제공 방식(공용 서버 계정 / 각자 WSL / USB 라이브) — 확정 후 `docs/README.md` 9절에 반영
- 힌트 감점 폭, 폭발 감점 폭 — 확정 후 `docs/README.md` 6·7절에 반영
- 참가자별 시드 배정표 — T022에서 작성
