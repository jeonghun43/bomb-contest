# Plan: 대회 서버 (SSH 해체 + 서버 기록 + 리더보드)

- **Feature ID**: 002-contest-server
- **Spec**: [spec.md](spec.md) · **선행**: [001-new-bomb](../001-new-bomb/plan.md)

---

## 1. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 폭탄 보고 | C, `AF_UNIX` 로컬 소켓 | 네트워크 노출 없음. 커널이 접속 uid를 보증 |
| 신원 | `SO_PEERCRED` | 폭탄에 토큰 불필요, 위조 불가 |
| 서버 | Python 3 표준 라이브러리 (`socketserver`, `http.server`, `sqlite3`) | 의존성 0, Ubuntu 기본 |
| 저장 | SQLite (WAL) | 단일 파일, 동시 읽기 |
| 서비스 | systemd + nginx | 자동 재시작, 표준 배포 |
| 계정 게이팅 | `usermod --expiredate` | 비밀번호·키 로그인 모두 차단 |

## 2. 핵심 설계 결정

### 2.1 신원 = 접속 uid (토큰 없음)
`reportd`는 연결마다 `getsockopt(SO_PEERCRED)`로 pid/uid를 읽어 `users.uid`로 참가자를 찾는다. 메시지 안의 어떤 값도 신원 근거로 쓰지 않는다. 소켓은 `0666`이라 누구나 연결할 수 있지만, 연결하는 순간 그 사람의 uid로 확정된다.

### 2.2 서버 재채점 (폭탄을 믿지 않음)
`defused` 보고는 입력 원문(hex)을 동반한다. 서버는 참가자 `seed`로 `gen_bomb.build(seed)`를 재현하고 `bombcheck.check_line`으로 다시 판정한다. 통과 → `defused`, 실패 → `invalid`(폭발로 집계). 응답은 항상 `OK`라 유효 여부가 새지 않는다(AC-04, AC-05). 점수 = "서버가 그 uid로부터 정답 입력을 받은 phase 집합".

### 2.3 정답 비노출
폭탄에는 `BOMB_ID`(hex 16)만 박히고 시드는 없다. 시드·정답·생성기는 `/opt/bomblab`(0750, contestants 접근 불가)와 DB(0700)에 있다. 시드는 `secrets.randbits(63)`.

### 2.4 판정 일치 강제
`bombcheck.py`는 `sscanf` 동작(앞 공백·부호·뒤 잔여·glibc long 클램프 후 int 절삭, `%Ns`)까지 흉내 낸다. `fuzz_checker.py`가 시드·경계 입력마다 컴파일된 폭탄과 대조해 불일치 0을 강제하며 `verify.sh`에 편입(AC-11).

## 3. 컴포넌트

### 3.1 폭탄 (기존 코드 확장)
- **`src/notify.c`** (신규, `-DNOTIFY`): `notify_request(line, reply, n)` — `AF_UNIX` 연결, 한 줄 요청/응답, 송·수신 3초 타임아웃. 소켓 경로는 `NOTIFY_SOCKET` 매크로.
- **`src/support.c`** `#ifdef NOTIFY` 분기:
  - `initialize_bomb()` → `HELLO <BOMB_ID>`. 응답이 `OK`가 아니면 사유 출력 후 `exit(9)` (phase 시작 전).
  - `bomb_log(phase, result)` → `EVENT <BOMB_ID> <defused|exploded> <phase> <hex(입력)>`. 해제 보고 실패 시 `exit(9)`(유실 방지·재실행 안내), 폭발 보고 실패 시 경고만.
  - phase 번호는 기존 호출부(`explode_bomb`의 `num_defused+1`, `phase_defused`의 `num_defused`, secret `7`)를 그대로 사용.
  - 오프라인 모드(기본)는 로컬 `bomb.log`로 001과 동일.
- **`src/bomb.h`**: `notify_request` 선언(NOTIFY에서만).

### 3.2 빌드
- **`tools/gen_bomb.py`**: `--out DIR`(생성물을 DIR에, `src/`를 안 건드림), `--bomb-id HEX`(헤더에 `BOMB_ID`, 없으면 `BOMB_SEED`).
- **`Makefile`**: `OUT ?= build/seed-$(SEED)`로 생성물·바이너리 위치 지정, `-I$(OUT)`. `NOTIFY=1`이면 `-DNOTIFY -DNOTIFY_SOCKET=...` + `src/notify.c`, `BOMB_ID` 필수. 호환을 위해 `./bomb`에도 복사.

### 3.3 서버 (`server/bomblab/`, 표준 라이브러리만)
| 모듈 | 내용 |
|---|---|
| `config.py` | ini 로드, `state(override)` = 시각+운영자 덮어쓰기로 BEFORE/RUNNING/FROZEN/ENDED 계산, 관리자 비밀번호 해시(`sha256$salt$hex`) 확인 |
| `db.py` | 스키마·쿼리. writer는 rw, web은 `mode=ro` |
| `scoring.py` | cutoff 이하 `late=0` 이벤트로 점수·순위. 공개 cutoff=프리즈 시각, 관리자 cutoff=현재 |
| `reportd.py` | `ThreadingUnixStreamServer`. HELLO/EVENT 처리, 재채점, 속도 제한(분당 N), `params` 캐시 |
| `web.py` | `ThreadingHTTPServer`. `/`·`/api/scoreboard`·`/api/feed` 공개, `/admin`·`/api/admin/*` Basic 인증 |
| `templates/` | `scoreboard.html`(10초 폴링, 프리즈 배너), `admin.html`(5초, 입력 원문) |

**DB 스키마**: `users(username,uid,nickname,seed,bomb_id,locked)`, `events(user_id,bomb_id,phase,kind,input,peer_pid,created_at,late)` — `kind ∈ {hello,defused,exploded,invalid,rejected}`, `settings(key,value)`(override 저장).

### 3.4 운영 CLI `server/bin/bomblabctl` (root)
`provision`(계정+비밀번호+폭탄 빌드+홈 설치+DB 등록, 잠금 생성, `credentials.csv`·`cards.html` 출력) / `start·freeze·unfreeze·stop·auto`(override) / `tick`(상태에 맞춰 `usermod --expiredate` 잠금·해제, 종료 시 `kick_on_end`면 `pkill`) / `list·status` / `lock·unlock·reset-password` / `export`(순위+이벤트 CSV) / `purge`(계정·홈 삭제) / `selftest-user`(현재 계정 등록) / `hash-password`.

### 3.5 배포 (`server/`)
`install.sh`(Ubuntu 22.04/24.04), systemd 유닛 4개(reportd·web·scheduler.service+timer), `nginx/bomblab.conf`, `etc/sshd_config.d/bomblab.conf`(contestants 포워딩 차단·MaxSessions), `etc/system/*.slice`(CPU/메모리/태스크 상한), `etc/bomblab.ini.example`.

격리: `/opt/bomblab` 0750(root:bomblab) → 참가자 소스 접근 불가, `/var/lib/bomblab` 0700, `/home/*` 0700 + `UMASK 077`, `/proc hidepid=invisible`, SSH `AllowTcpForwarding no`.

## 4. 프로토콜 (한 줄, 개행 종료)

```
HELLO <bomb_id>                              -> OK | CLOSED <reason> | ERR <reason>
EVENT <bomb_id> <defused|exploded> <phase> <hexinput>  -> OK | ERR <reason>
```
입력은 hex 인코딩(공백·특수문자 안전). 서버는 재채점 결과와 무관하게 `OK`.

## 5. 검증
- **오프라인 회귀+퍼저**: `make verify FROM=1 TO=20` → 001의 501 검사 + 채점 일치 퍼징(AC-11).
- **서버 셀프테스트(root 불필요)**: `bash tools/server_selftest.sh` → AC-01~06,09,10.
- **실서버 리허설(VM)**: 설치→provision→시작 전 로그인 거부→해제·폭발 리더보드 반영→격리(AC-12)→프리즈→자동 종료(AC-13)→export.

## 6. 리스크

| 리스크 | 완화 |
|---|---|
| 채점 불일치로 억울한 감점 | 퍼저가 경계 입력까지 폭탄과 대조, verify에 상시 편입 |
| WAL DB read-only 매핑 | web은 `mode=ro`지만 유닛에서 `/var/lib/bomblab` 쓰기 허용(-shm 매핑용) |
| gcc 버전차로 난이도·채점 변동 | 대회 빌드 환경 고정, 최종 바이너리로 리허설 |
| 소켓 폭주 | 분당 한도 + 연결당 타임아웃/최대 길이 |
| 계정 게이팅 누락 | 15초 타이머가 상태에 맞춰 지속 재적용 |
