# Bomb Lab 대회 서버 — 운영 매뉴얼

참가자는 SSH로 서버에 접속해 자기 계정의 폭탄을 해체하고, 모든 해제·폭발은 서버 DB에 기록되어 웹 리더보드에 실시간으로 나타납니다. 이 문서는 서버를 세우고 대회를 운영하는 절차입니다.

구현·검증 세부는 [specs/002-contest-server](../specs/002-contest-server/spec.md)를 보세요.

---

## 1. 구성 요소

| 구성 | 사용자 | 역할 |
|---|---|---|
| `bomblab-reportd` | `bomblab` | Unix 소켓 `/run/bomblab/report.sock` 수신. 접속 uid로 참가자를 식별하고, 해제 주장은 입력을 **다시 채점**해 인정 |
| `bomblab-web` | `bomblab` | `127.0.0.1:8080` — 공개 리더보드 `/`, 관리자 `/admin` |
| `bomblab-scheduler.timer` | root | 15초마다 대회 상태에 맞춰 계정 잠금/해제 |
| `nginx` | — | 80/443을 web으로 프록시 |
| `bomblabctl` | root | 운영자 CLI |
| `/var/lib/bomblab/bomblab.db` | `bomblab` | SQLite. 참가자·이벤트·설정 |

**보안 골자**
- 신원은 커널이 보증하는 접속 uid(`SO_PEERCRED`)로 정해집니다. 폭탄에 토큰이 없고, 남의 이름으로 기록할 수 없습니다.
- 폭탄에는 시드가 없고 무작위 `BOMB_ID`만 있습니다. 시드·정답은 root만 읽는 DB에 있습니다.
- 서버는 폭탄의 "해제했다"는 말을 믿지 않고, 보고된 입력을 참가자 시드로 재채점해 통과할 때만 인정합니다. 위조 시도는 `invalid`로 남고 폭발로 집계됩니다.

## 2. 서버 준비

- Ubuntu 22.04 또는 24.04, 2 vCPU / 4GB 이상 (30명 기준).
- 공인 IP로 열 경우 방화벽에서 22(SSH)·80(·443)만 열고, `fail2ban` 설치를 권장합니다.
- 이 저장소를 서버에 복사(git clone 또는 scp)합니다.

## 3. 설치

```bash
sudo ./server/install.sh
```

패키지 설치 → `bomblab` 계정·`contestants` 그룹 → `/opt/bomblab` 배치 → systemd 유닛 → nginx → 참가자 격리(SSH 포워딩 차단, 사용자 자원 제한, `/home` 0700, `/proc hidepid`)까지 수행하고 자체 점검을 출력합니다. 재실행해도 안전합니다.

HTTPS가 필요하면 도메인 연결 후:

```bash
sudo certbot --nginx -d bomb.example.com
```

## 4. 설정

```bash
sudo nano /etc/bomblab/bomblab.ini
```

- `[contest]` 시각: `start_at` / `freeze_at` / `end_at` (ISO 8601 + 타임존). 시각에 따라 자동 전환됩니다.
- `[scoring]`: 단계별 점수·secret 점수·폭발 감점. 기본은 각 10점·secret 10점·폭발 −0.5(상한 −20). **원본 CMU 배점(10,10,10,10,15,15)** 은 파일 주석에 병기되어 있으니 한 줄만 바꾸면 됩니다.
- `[server] public_host`: 참가자 카드·리더보드 링크에 쓰일 주소.
- `[admin]`: 관리자 화면 로그인. 해시 생성:

```bash
sudo bomblabctl hash-password      # 비밀번호 입력 → sha256$... 출력
# 출력값을 bomblab.ini 의 password_hash 에 붙여넣기
```

설정을 바꾼 뒤 데몬 재시작:

```bash
sudo systemctl restart bomblab-reportd bomblab-web
```

## 5. 참가자 계정 만들기

명단 CSV를 준비합니다. 한 줄에 한 명, 닉네임만 있으면 됩니다(아이디를 지정하려면 둘째 열에).

```csv
# nickname[,username]
김철수
이영희
박민수,bomb_park
```

```bash
sudo bomblabctl provision roster.csv
```

각 참가자에 대해 리눅스 계정(`bomb01`, `bomb02`, …)·무작위 비밀번호·전용 폭탄을 만들어 `~/bomb/`에 설치하고 DB에 등록합니다. 계정은 **잠긴 상태**로 생성됩니다. 결과:

- `credentials.csv` (0600) — 닉네임·아이디·비밀번호·접속 명령
- `cards.html` — 인쇄용 접속 정보 카드 (한 명당 한 장)

`cards.html`을 인쇄해 나눠 주세요. **지각자**는 명단에 줄을 추가하고 다시 실행하면 기존 인원은 건너뛰고 새 인원만 생성됩니다.

## 6. 리허설 (대회 전 필수)

빌드·서버 로직은 자동 검증되어 있습니다(아래 8절). 대회 전에는 **실제 접속 흐름**을 리허설하세요.

1. 가짜 명단 2~3명으로 `provision`.
2. 시작 전 상태에서 SSH 로그인 → 거부되는지 확인.
3. `sudo bomblabctl start` → 로그인되고 `~/bomb/./bomb` 실행 → 리더보드(브라우저)에 반영되는지 확인.
4. 일부러 오답 → 폭발이 리더보드 폭발 수에 반영되는지.
5. `sudo bomblabctl freeze` → 공개 리더보드가 고정되고 `/admin` 은 계속 갱신되는지.
6. 격리 확인 (참가자 계정에서): `ls /home/다른계정`·`cat /var/lib/bomblab/bomblab.db`·`ls /opt/bomblab` 이 거부되고, `ps aux` 에 남의 프로세스가 안 보이고, `ssh -L` 포워딩이 거부되는지.
7. `sudo bomblabctl export result.csv` → 순위·이벤트가 나오는지.
8. `sudo bomblabctl purge --yes` 로 리허설 계정 정리.

## 7. 대회 당일

| 상황 | 명령 |
|---|---|
| 상태·시각 확인 | `bomblabctl status` |
| 참가자 목록·점수·잠금상태 | `bomblabctl list` |
| 시작(수동) | `sudo bomblabctl start` |
| 프리즈(수동) | `sudo bomblabctl freeze` / `unfreeze` |
| 종료(수동) | `sudo bomblabctl stop` |
| 설정 시각 자동으로 되돌리기 | `sudo bomblabctl auto` |
| 한 명만 잠그기/풀기 | `sudo bomblabctl lock bomb07` / `unlock bomb07` |
| 비밀번호 재발급 | `sudo bomblabctl reset-password bomb07` |

- 상태 전환은 **시각에 따라 자동**입니다. 위 `start/freeze/stop`은 그 위에 얹는 수동 덮어쓰기이며, `auto`로 언제든 자동으로 되돌립니다.
- 15초 주기 타이머가 상태에 맞춰 계정 잠금/해제를 계속 맞춥니다. 시각을 연장하려면 `bomblab.ini`의 `end_at`을 늦추고 데몬을 재시작하면 됩니다(또는 `stop`을 안 하고 `auto` 유지).
- 관리자 화면: 브라우저에서 `http://<서버>/admin` → 설정한 admin 계정으로 로그인. 실시간 순위 + 참가자별 입력 원문까지 봅니다.

## 8. 자동 검증 (root 불필요, WSL/로컬 가능)

```bash
make verify FROM=1 TO=20        # 폭탄 유일해 + 서버 채점 일치 퍼징
bash tools/server_selftest.sh   # 기록·위조 방지·프리즈·인증 등 서버 로직
```

`server_selftest.sh`는 임시 소켓·DB로 reportd/web을 띄우고 현재 계정을 테스트 참가자로 등록해, 정답 채점·위조 차단(`invalid`)·다른 폭탄 ID 거부·속도 제한·관리자 인증·시작 전 차단을 확인합니다.

## 9. 장애 대응

| 증상 | 조치 |
|---|---|
| 참가자가 "기록 서버 연결 실패" | `systemctl status bomblab-reportd`, 필요 시 `restart`. 소켓 권한 `stat /run/bomblab/report.sock` (0666) |
| 리더보드가 안 뜸 | `systemctl status bomblab-web nginx`, `journalctl -u bomblab-web` |
| 점수가 이상함 | `/admin`에서 해당 참가자 이벤트 확인. `invalid`가 많으면 위조 시도 또는 잘못된 시드 매핑 |
| 시작 시각인데 로그인 안 됨 | `bomblabctl status`로 상태 확인, `sudo bomblabctl tick` 강제 적용 |

## 10. 종료 후

```bash
sudo bomblabctl export result.csv     # result.csv(순위) + result.csv.events.csv(전체 이벤트)
sudo cp /var/lib/bomblab/bomblab.db ~/bomblab-backup.db   # 원본 백업
sudo bomblabctl purge --yes           # 계정·홈 삭제 (export/백업 후에!)
```

`purge`는 모든 대회 계정과 홈 디렉터리를 지웁니다. 반드시 `export`와 DB 백업을 마친 뒤 실행하세요.
