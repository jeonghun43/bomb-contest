# Bomb Lab 대회 서버 — 운영자 매뉴얼

참가자는 SSH로 서버에 접속해 자기 계정의 폭탄을 해체하고, 모든 해제·폭발은 서버 DB에 기록되어 웹 리더보드에 실시간으로 나타납니다. 이 문서 하나로 **배포 → 설정 → 대회 운영 → 상황 대처 → 종료**까지 다룹니다.

- 설계·검증 세부: [specs/002-contest-server](../specs/002-contest-server/spec.md)
- 참가자용 안내: [docs/README.md](../docs/README.md)

---

## 1. 구성 요소 한눈에

| 구성 | 실행 사용자 | 역할 |
|---|---|---|
| `bomblab-reportd` | `bomblab` | Unix 소켓 `/run/bomblab/report.sock` 수신. 접속 uid로 참가자 식별, 해제 주장을 **재채점** |
| `bomblab-web` | `bomblab` | `127.0.0.1:8080` — 공개 리더보드 `/`, 관리자 `/admin` |
| `bomblab-scheduler.timer` | root | 15초마다 대회 상태에 맞춰 계정 잠금/해제 |
| `nginx` | — | 80/443 → web 프록시 |
| `bomblabctl` | root | 운영자 CLI (아래 명령어 표) |
| `/var/lib/bomblab/bomblab.db` | `bomblab` | SQLite. 참가자·이벤트·설정 |

**보안 골자**: 신원은 커널이 보증하는 접속 uid(`SO_PEERCRED`)로 정해져 위조 불가. 폭탄에는 시드가 없고 무작위 `BOMB_ID`만 있음. 서버는 폭탄의 "해제했다"는 말을 믿지 않고 입력을 재채점해 통과할 때만 인정(위조 시도는 `invalid` → 폭발로 집계).

---

## 2. AWS EC2 배포

### 2.1 ⚠️ 인스턴스는 반드시 x86-64

참가자가 서버 안에서 폭탄을 실행하므로 **서버 CPU = 폭탄 아키텍처**입니다.

| | 인스턴스 | 비고 |
|---|---|---|
| ✅ | **t3.medium** (Intel), t3a.medium (AMD) | x86-64 |
| ❌ | t4g·m6g·c7g 등 (Graviton) | ARM → 폭탄이 ARM으로 빌드되어 깨짐 |

30명 기준 **t3.medium (2 vCPU / 4GB)** 권장.

### 2.2 인스턴스 생성

- 리전 **서울(ap-northeast-2)**, AMI **Ubuntu 24.04 LTS (x86)**, 타입 **t3.medium**
- 키 페어 생성 → `bomblab-key.pem` 다운로드 (관리자 접속용)
- 보안 그룹 인바운드: **22 / 80 / 443** 모두 `0.0.0.0/0` (8080은 열지 말 것)

### 2.3 퍼블릭 IP·DNS

- 인스턴스의 **퍼블릭 IPv4**를 가비아 A 레코드 `bomb` → 그 IP 로 등록.
- 재부팅은 IP 유지, **Stop→Start는 IP가 바뀝니다**(그때 A 레코드 수정). 미리 셋업 후 껐다 켤 계획이면 A 레코드 **TTL을 300초로 낮춰두세요**.
- 탄력적 IP는 선택(껐다 켜도 IP 고정하고 싶을 때만).

### 2.4 접속 & 저장소

```bash
ssh -i bomblab-key.pem ubuntu@bomb.doublejeong.com     # (또는 IP)
# 비공개 저장소 클론 (fine-grained 토큰: Contents=Read 권한 필요)
git clone https://github.com/jeonghun43/bomb-contest.git
cd bomb-contest
```

### 2.5 설치

```bash
sudo bash server/install.sh
```

패키지 → `bomblab` 계정·`contestants` 그룹 → `/opt/bomblab` 배치 → systemd 3종 → nginx → 참가자 격리(SSH 포워딩 차단·**참가자 그룹만 비밀번호 로그인**·자원 제한·`/home` 0700·`/proc hidepid`) → fail2ban 까지 수행하고 재시작합니다. **재실행 = 재배포**(코드 업데이트 후 `git pull` → `sudo bash server/install.sh`).

### 2.6 시간대 (중요)

EC2는 기본 UTC라 시각이 한국시간과 9시간 어긋납니다. 서울로 바꾸세요:
```bash
sudo timedatectl set-timezone Asia/Seoul
sudo systemctl restart bomblab-web bomblab-reportd
```

### 2.7 HTTPS

```bash
sudo certbot --nginx -d bomb.doublejeong.com
```
이메일 입력 → 약관 `Y` → 리다이렉트 선택. 이미 인증서가 있어 물으면 **1(Reinstall)** 선택(새로 받을 필요 없음). 확인: `sudo ss -ltnp | grep ':443'`.

---

## 3. 설정 `/etc/bomblab/bomblab.ini`

```bash
sudo nano /etc/bomblab/bomblab.ini
sudo systemctl restart bomblab-reportd bomblab-web   # 바꾼 뒤 재시작
```

- `[contest]` `start_at`/`freeze_at`/`end_at` — ISO 8601 + `+09:00`. 이 시각에 자동 전환.
- `[scoring]` — 단계별 점수·secret 점수·폭발 감점. 기본 각 10점 + secret 10점 / 원본 CMU는 `10,10,10,10,15,15`.
- `[server] public_host` — 카드·리더보드 링크 주소.
- `[admin]` — `/admin` 로그인. 해시: `sudo bomblabctl hash-password` 출력을 `password_hash`에 붙여넣기.

---

## 4. 참가자 계정 만들기 & 추가

### 4.1 최초 생성

명단 CSV(한 줄에 한 명, 이름만 있으면 됨. 이름은 운영자만 보는 라벨이고 공개 화면엔 bomb 번호로 나옴):

```csv
# 이름(운영자 확인용)[,username]
홍길동
김철수
이영희,bomb_lee
```

```bash
sudo bomblabctl provision roster.csv
```

각 참가자에 계정(`bomb01`, `bomb02`…)·무작위 비밀번호·전용 폭탄을 만들어 `~/bomb/`에 설치하고 DB에 등록합니다(계정은 **잠긴 상태**). 산출물:

- `credentials.csv` (아이디·비밀번호·접속 명령) / `cards.html` (인쇄용 카드) — sudo 실행 사용자 소유로 생성되니 바로 내려받아 배포:
  ```bash
  # 로컬에서
  scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomb-contest/cards.html .
  ```

### 4.2 ✅ 대회 도중 참가자 추가 (지각자) — 가능합니다

5명으로 시작한 뒤 더 추가하려면, **명단에 줄을 추가하고 provision을 다시 실행**하면 됩니다:

```bash
# roster.csv 에 새 이름을 추가한 뒤
sudo bomblabctl provision roster.csv
```

- 기존 `bomb01~05`는 **건너뛰고**, 새 사람만 `bomb06`… 으로 생성됩니다.
- `credentials.csv`·`cards.html`에는 **새로 추가된 사람 것만** 나옵니다 → 그 카드만 지각자에게 배포.
- 대회가 이미 `start` 상태면, 새 계정은 15초 내 스케줄러가 자동으로 엽니다. 즉시 열려면:
  ```bash
  sudo bomblabctl tick
  ```

> 별도 CSV를 써도 됩니다(예: `latecomers.csv`에 새 사람만). provision은 이미 있는 username은 무조건 건너뛰므로 안전합니다.

---

## 5. 운영 명령어 레퍼런스 `bomblabctl`

> 심링크(`sudo bomblabctl …`)로 쳐서 `ModuleNotFound`가 나오면 전체 경로로: `sudo /opt/bomblab/server/bin/bomblabctl …`

| 명령 | 설명 |
|---|---|
| `provision <roster.csv>` | 계정+비밀번호+폭탄+카드 생성 (기존자 건너뜀) |
| `status` | 대회 상태·시각·참가자 수 |
| `list` | 참가자별 순위·점수·폭발·잠금상태·해제단계 |
| `start` | 대회 시작(계정 전체 열기, override=RUNNING) |
| `freeze` / `unfreeze` | 공개 리더보드 고정 / 해제 |
| `stop` | 대회 종료(새 로그인 차단, override=ENDED) |
| `auto` | 수동 override 해제 → 설정 시각대로 자동 |
| `tick` | 현재 상태에 맞게 계정 잠금/해제 즉시 적용 |
| `lock <user>` / `unlock <user>` | 한 명만 잠금/해제 |
| `reset-password <user>` | 비밀번호 재발급(출력됨) |
| `export <out.csv>` | 최종 순위 + 전체 이벤트 CSV |
| `purge --yes` | 모든 대회 계정·홈 삭제 (export 후에!) |
| `hash-password` | admin 비밀번호 해시 생성 |

- **상태 우선순위**: 설정 시각으로 자동 전환되며, `start/freeze/stop`은 그 위에 얹는 수동 덮어쓰기. `auto`로 자동 복귀. 15초 타이머가 상태에 맞춰 계정을 계속 맞춥니다.
- **주의**: 상태가 `before`인데 `unlock bomb01`만 하면 15초 뒤 다시 잠깁니다. 계속 열어두려면 `start`.

---

## 6. 대회 진행 타임라인

1. **전날**: provision으로 계정·카드 생성, 리허설(7장), 필요 시 TTL 낮추기.
2. **시작 전**: 계정 잠김 상태 확인(`status`가 `before`). 참가자에게 카드 배부.
3. **시작**: 설정 `start_at` 도달 시 자동 개방, 또는 `sudo bomblabctl start`. 참가자 접속 시작.
4. **진행 중**: `list`로 진행 확인, `/admin`으로 실시간 이벤트·입력 원문 확인.
5. **종료 30분 전**: `freeze_at` 자동, 또는 `sudo bomblabctl freeze` → 공개 보드 고정.
6. **종료**: `end_at` 자동, 또는 `sudo bomblabctl stop`. `unfreeze`로 최종 순위 공개.
7. **정리**: `export` → 결과 저장 → `purge` → 인스턴스 Stop/Terminate.

---

## 7. 운영북 — 상황별 대처

대회 중 실제로 자주 나오는 상황과 해결법입니다.

### 접속 문제

**참가자: 로그인이 `Account has expired`**
→ 대회가 아직 시작 전이거나 계정이 잠김. `sudo bomblabctl status` 확인 후 `sudo bomblabctl start`(전체) 또는 `unlock <user>`(한 명).

**참가자: `Permission denied (publickey)` (비밀번호를 못 넣음)**
→ 참가자 그룹 비밀번호 로그인이 꺼진 것. 확인·조치:
```bash
sudo sshd -T -C user=bomb01 | grep -i passwordauthentication   # no면 문제
sudo systemctl reload ssh
```
(설정 파일 `sshd_config.d/bomblab.conf`의 `Match Group contestants → PasswordAuthentication yes` 가 적용됐는지)

**참가자: `Could not resolve hostname … Temporary failure in name resolution`**
→ 그 참가자가 **WSL**에서 접속 중일 가능성. WSL은 DNS가 따로 놀아 실패함. **PowerShell(윈도)·터미널(맥)** 로 접속하라고 안내. 급하면 도메인 대신 IP로.

**참가자: 도메인은 안 되는데 IP는 됨**
→ 그 참가자 로컬 DNS 캐시 문제. Windows면 `ipconfig /flushdns`. 서버·도메인은 정상이니 IP로 우회 가능.

**비밀번호 분실**
→ `sudo bomblabctl reset-password bomb07` → 출력된 새 비밀번호 전달.

### 리더보드·기록 문제

**참가자: "기록 서버에 연결할 수 없습니다"**
→ reportd 확인:
```bash
sudo systemctl status bomblab-reportd
sudo systemctl restart bomblab-reportd
stat /run/bomblab/report.sock          # 0666 이어야 함
```
해제 기록은 유실되지 않으니 참가자는 다시 실행하면 됩니다.

**리더보드가 안 뜸**
```bash
sudo systemctl status bomblab-web nginx
sudo journalctl -u bomblab-web -n 50 --no-pager
sudo ss -ltnp | grep -E ':(80|443|8080)'
```
- `Address already in use`는 에러 아님(서비스가 이미 돎).
- 코드 수정 후 안 바뀌면 `sudo systemctl restart bomblab-web`.

**HTTPS만 안 됨(HTTP는 됨)**
→ certbot 미설정. `sudo ss -ltnp | grep ':443'`이 비었으면 `sudo certbot --nginx -d bomb.doublejeong.com`. 보안그룹 443도 확인.

**시각이 한국시간이 아님**
→ `sudo timedatectl set-timezone Asia/Seoul && sudo systemctl restart bomblab-web bomblab-reportd`.

**점수가 안 오르는데 참가자는 풀었다고 함**
→ `/admin`에서 그 참가자 이벤트 확인. `invalid`가 찍혔으면 폭탄이 정답이 아닌 값을 보고한 것(재채점 실패). 진짜 정답이면 통과되어야 하므로, 반복되면 시드 매핑·빌드 문제 의심.

### 계정·부정행위

**부정행위 의심 — 한 명 즉시 차단**
```bash
sudo bomblabctl lock bomb07        # 로그인 차단
sudo pkill -KILL -u bomb07         # 접속 중 세션도 끊기
```
`/admin`의 이벤트·입력 원문으로 정황 확인.

**한 명만 다시 열기**
→ `sudo bomblabctl unlock bomb07` (단 상태가 running이어야 유지됨).

### 인프라 문제

**대회 시간 연장**
→ `bomblab.ini`의 `end_at`을 늦추고 `sudo systemctl restart bomblab-reportd bomblab-web`. 또는 아직 `stop` 안 했으면 `sudo bomblabctl auto` 유지.

**서버가 재부팅됨**
→ 서비스 3종은 자동 시작. 확인:
```bash
sudo bomblabctl status
sudo systemctl is-active bomblab-reportd bomblab-web
```

**Stop→Start로 IP가 바뀜**
→ 가비아 A 레코드를 새 IP로 수정(그 외 nginx·인증서·계정·카드는 그대로). 자세히는 2.3.

**`bomblabctl`이 `ModuleNotFoundError`**
→ 심링크 경로 문제. `sudo /opt/bomblab/server/bin/bomblabctl …` 전체 경로로 실행.

---

## 8. 리허설 (대회 전 필수)

```bash
sudo bomblabctl provision test-roster.csv   # 가짜 2~3명
# 시작 전: 밖에서 ssh → 거부 확인
sudo bomblabctl start                        # 열림 → 접속·해제·폭발이 리더보드 반영되는지
sudo bomblabctl freeze                        # 공개 보드 고정, /admin 은 계속 갱신
sudo bomblabctl export test.csv               # 결과 뽑히는지
sudo bomblabctl purge --yes                   # 리허설 계정 정리
```

격리 확인(참가자 계정에서): `ls /home/다른계정`·`cat /var/lib/bomblab/bomblab.db`·`ls /opt/bomblab` 거부, `ps aux`에 남 프로세스 안 보임, `ssh -L` 거부.

무권한 자동 검증(로컬/WSL):
```bash
make verify FROM=1 TO=20         # 폭탄 유일해 + 서버 채점 일치
bash tools/server_selftest.sh    # 기록·위조차단·프리즈·인증
```

---

## 9. 종료 후

```bash
sudo bomblabctl export result.csv                       # result.csv + result.csv.events.csv
sudo cp /var/lib/bomblab/bomblab.db ~/bomblab-backup.db  # 원본 백업
# 로컬로 내려받기
scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomb-contest/result.csv .
sudo bomblabctl purge --yes                             # 계정·홈 삭제 (백업 후!)
```

그다음 EC2 콘솔에서 **인스턴스 Stop/Terminate**. 탄력적 IP를 썼다면 release까지. **켜둔 시간만큼 과금**되니 잊지 마세요.
