# Tasks: 대회 서버 (SSH 해체 + 서버 기록 + 리더보드)

- **Feature ID**: 002-contest-server
- **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

`[P]` = 앞선 태스크가 끝났다면 병렬 가능.

---

## Phase A — 빌드 분리

- [x] **T001** `gen_bomb.py`에 `--out DIR`·`--bomb-id HEX` 추가, 생성물을 `src/`에서 `OUT`으로 이동
- [x] **T002** `Makefile`에 `OUT` / `NOTIFY` / `BOMB_ID` / `NOTIFY_SOCKET` 추가, `-I$(OUT)`
  - 검증: `make SEED=n` 오프라인 빌드·실행 정상 (`./bomb`, `build/seed-n/solution.txt`)

## Phase B — 서버 채점기

- [x] **T003** `tools/bombcheck.py` — `check_line(phase,line,params)`, `scan_d`/`scan_s`로 sscanf 흉내, 로직은 `gen_bomb` 재사용
- [x] **T004** `tools/fuzz_checker.py` — 경계 입력으로 폭탄 vs 판정기 대조, `verify.sh`에 편입
  - 검증: `make verify 1 20` → 1540 입력 0 불일치 (AC-11)

## Phase C — 폭탄 알림

- [x] **T005** `src/notify.c` + `bomb.h` 선언
- [x] **T006** `src/support.c` `#ifdef NOTIFY` 분기 (HELLO/EVENT, 실패 처리), 오프라인 경로 유지
  - 검증: mock 소켓으로 HELLO + EVENT 7건(hex 입력) 확인

## Phase D — 서버 코어

- [x] **T007** `config.py` — ini 로드, `state(override)`, 관리자 해시 확인
- [x] **T008** `db.py` — 스키마·쿼리, rw/ro 연결
- [x] **T009** `scoring.py` — cutoff·점수·순위·프리즈
- [x] **T010** `reportd.py` — SO_PEERCRED, HELLO/EVENT, 재채점, 속도 제한, params 캐시

## Phase E — 웹

- [x] **T011** `web.py` — 공개/관리자 라우트, Basic 인증, ro DB
- [x] **T012** `[P]` `templates/scoreboard.html`, `templates/admin.html`

## Phase F — 운영 CLI

- [x] **T013** `bomblabctl` — provision / 상태전환 / tick / list / status / lock·unlock / reset-password / export / purge / selftest-user / hash-password

## Phase G — 무권한 셀프테스트

- [x] **T014** `tools/server_selftest.sh` — AC-01~06,09,10
  - 검증: **passed=12 failed=0**

## Phase H — 배포

- [x] **T015** systemd 유닛 4종 (reportd·web·scheduler.service+timer)
- [x] **T016** `nginx/bomblab.conf`, `etc/sshd_config.d/bomblab.conf`, `etc/system/*.slice`, `etc/bomblab.ini.example`
- [x] **T017** `install.sh` (Ubuntu 22.04/24.04)

## Phase I — 문서

- [x] **T018** `docs/README.md` 서버 모드로 개정 (SSH 접속·리더보드·기록·오프라인 부록)
- [x] **T019** `server/README.md` 운영 매뉴얼

## Phase J — 실서버 리허설 (운영자 수행, VM 필요)

- [ ] **T020** 새 Ubuntu VM에 `install.sh` → 서비스 3종 active, 소켓 0666, DB 0700 확인
- [ ] **T021** 가짜 명단 provision → `cards.html`, 시작 전 로그인 거부 / start 후 허용 (AC-13)
- [ ] **T022** 동시 접속 해제·폭발 → 브라우저 리더보드 실시간, freeze 동작
- [ ] **T023** 격리 확인 (AC-12): 타 홈·DB·`/opt/bomblab` 접근 거부, `ps` 격리, `ssh -L` 거부
- [ ] **T024** 자동 종료 → 새 로그인 차단·폭탄 `CLOSED`, `export` → 순위 CSV

---

## 진행 현황

| Phase | 태스크 | 상태 |
|---|---|---|
| A 빌드 분리 | T001~T002 | 완료 |
| B 채점기 | T003~T004 | 완료 (1540 입력 0 불일치) |
| C 폭탄 알림 | T005~T006 | 완료 |
| D 서버 코어 | T007~T010 | 완료 |
| E 웹 | T011~T012 | 완료 |
| F 운영 CLI | T013 | 완료 |
| G 셀프테스트 | T014 | 완료 (12/12) |
| H 배포 | T015~T017 | 완료 |
| I 문서 | T018~T019 | 완료 |
| J 리허설 | T020~T024 | 대기 (운영자·VM 수행) |

## 남은 결정 사항 (001에서 이어짐)

- 서버 위치(클라우드/학교)·도메인·HTTPS
- 채점 배점 최종 확정 (기본 각 10점 vs 원본 10,10,10,10,15,15)
- 참가자 SSH 클라이언트 안내 필요 여부
