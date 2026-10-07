# Bomb Lab 연습 서버 — 운영자 매뉴얼

학생은 SSH로 서버에 접속해 자기 계정의 폭탄을 해체합니다. 모든 해제·폭발은 서버 DB에 기록되어 웹 스코어보드에 실시간으로 나타납니다. 이 문서 하나로 **배포 → 설정 → 학생 등록 → 2주 운영 → 상황 대처 → 종료**까지 다룹니다.

- 설계·검증 세부: [specs/002-contest-server](../specs/002-contest-server/spec.md) (서버), [specs/003-practice-bank](../specs/003-practice-bank/spec.md) (문제은행)
- 학생용 안내: [docs/README.md](../docs/README.md), 드릴 안내: [docs/DRILLS.md](../docs/DRILLS.md)
- 운영진용 힌트 전체 목록: [HINTS.md](HINTS.md) (`tools/hint_catalog.py`로 생성)

---

## 1. 구성 요소 한눈에

| 구성 | 실행 사용자 | 역할 |
|---|---|---|
| `bomblab-reportd` | `bomblab` | Unix 소켓 `/run/bomblab/report.sock`. 접속 uid로 학생 식별, 해제 주장을 **재채점**, 해설·힌트 전달, 재발급 요청 접수 |
| `bomblab-builder` | root | 학생의 재발급 요청(`bomblab new ...`)을 받아 폭탄을 빌드하고 홈에 설치 |
| `bomblab-web` | `bomblab` | `127.0.0.1:8080` — 공개 스코어보드 `/`, 관리자 `/admin` |
| `bomblab-scheduler.timer` | root | 15초마다 운영 기간에 맞춰 로그인 열기/닫기 |
| `nginx` | — | 80/443 → web 프록시 |
| `bomblabctl` | root | 운영자 CLI (아래 명령어 표) |
| `bomblab` | 학생 | 학생 CLI (`/usr/local/bin/bomblab`) |
| Docker 이미지 `bomblab-gcc48` | — | 원본 CMU 폭탄과 같은 컴파일러(GCC 4.8.1). 모든 폭탄은 여기서 빌드 |
| `/var/lib/bomblab/bomblab.db` | `bomblab` | SQLite. 학생·폭탄·이벤트·힌트 열람·재발급 요청 |
| `/var/lib/bomblab/bombs/<bomb_id>/` | `bomblab` (0700) | 폭탄별 소스·정답·해설·힌트. 학생은 읽을 수 없음 |

**학생 한 명이 받는 폭탄** (홈 디렉터리):

| 위치 | 종류 | 점수 | 해설·힌트 | 재발급 |
|---|---|---|---|---|
| `~/bomb` | 과제형 (CMU 구조) | ✅ 원본 과제 배점 | ❌ | 운영자만 (`reissue`) |
| `~/practice` | 연습 (CMU 구조) | ❌ | ✅ | 학생이 `bomblab new practice` |
| `~/drills/d0` ~ `d9` | 개념 드릴 10개 | ❌ (진도표만) | ✅ | 학생이 `bomblab new d3` |

**보안 골자**: 신원은 커널이 보증하는 접속 uid(`SO_PEERCRED`)로 정해져 위조 불가. 폭탄에는 시드가 없고 무작위 `BOMB_ID`만 있음. 서버는 폭탄의 "해제했다"는 말을 믿지 않고 입력을 재채점해 통과할 때만 인정(위조 시도는 `invalid` → 폭발로 집계). 재발급되면 이전 폭탄의 보고는 거부.

---

## 2. AWS EC2 배포

### 2.1 ⚠️ 인스턴스는 반드시 x86-64

학생이 서버 안에서 폭탄을 실행하므로 **서버 CPU = 폭탄 아키텍처**입니다.

| | 인스턴스 | 비고 |
|---|---|---|
| ✅ | **t3.medium** (Intel), t3a.medium (AMD) | x86-64 |
| ❌ | t4g·m6g·c7g 등 (Graviton) | ARM → 폭탄이 실행되지 않음 |

30명 기준 **t3.medium (2 vCPU / 4GB)**, 디스크 **20GB 이상** 권장(Docker 이미지와 폭탄 빌드 디렉터리).

### 2.2 인스턴스 생성

- 리전 **서울(ap-northeast-2)**, AMI **Ubuntu 24.04 LTS (x86)**, 타입 **t3.medium**
- 키 페어 생성 → `bomblab-key.pem` 다운로드 (관리자 접속용)
- 보안 그룹 인바운드: **22 / 80 / 443** 모두 `0.0.0.0/0` (8080은 열지 말 것)

### 2.3 퍼블릭 IP·DNS

- 인스턴스의 **퍼블릭 IPv4**를 가비아 A 레코드 `bomb` → 그 IP 로 등록.
- 재부팅은 IP 유지, **Stop→Start는 IP가 바뀝니다**(그때 A 레코드 수정). 2주 동안 켜 둘 것이므로 **탄력적 IP**를 쓰는 편이 편합니다.

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

패키지(Docker 포함) → **GCC 4.8.1 툴체인 이미지 빌드**(처음 한 번, 몇 분) → `bomblab` 계정·`contestants` 그룹 → `/opt/bomblab` 배치(원본 폭탄이 든 `ref/`는 복사하지 않음) → 학생 CLI 설치 → systemd 4종 → nginx → 학생 격리(SSH 포워딩 차단·**학생 그룹만 비밀번호 로그인**·자원 제한·`/home` 0700·`/proc hidepid`) → fail2ban 까지 수행하고 재시작합니다. **재실행 = 재배포**(코드 업데이트 후 `git pull` → `sudo bash server/install.sh`).

**툴체인 이미지는 꼭 백업하세요.** 이미지는 지원이 끝난 Ubuntu 12.04 보관소에서 패키지를 받아 만듭니다. 보관소가 사라지면 다시 만들 수 없습니다.

```bash
sudo docker save bomblab-gcc48 | gzip > ~/bomblab-gcc48.tar.gz    # 약 100MB
scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomblab-gcc48.tar.gz .
```

저장소 옆(`../bomblab-gcc48.tar.gz`)이나 `/opt/bomblab-gcc48.tar.gz`에 두면 `install.sh`가 빌드 대신 불러옵니다.

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
이메일 입력 → 약관 `Y` → 리다이렉트 선택. 이미 인증서가 있어 물으면 **1(Reinstall)** 선택. 확인: `sudo ss -ltnp | grep ':443'`.

---

## 3. 노트북(WSL2)에서 운영하기

학생이 같은 네트워크(강의실·연구실)에 있을 때 쓸 수 있습니다. 외부에서 접속해야 하면 EC2를 권장합니다.

1. **Ubuntu 22.04/24.04 on WSL2**에서 **systemd를 켭니다.** `/etc/wsl.conf`에 아래를 넣고, PowerShell에서 `wsl --shutdown` 후 다시 엽니다.
   ```ini
   [boot]
   systemd=true
   ```
2. **SSH 서버**: `sudo apt install openssh-server && sudo systemctl enable --now ssh`
3. **네트워크**: WSL2 기본(NAT) 모드에서는 다른 PC가 WSL에 바로 접속할 수 없습니다. Windows 11이면 `%UserProfile%\.wslconfig`에서 미러 모드를 켜고(`[wsl2]` 아래 `networkingMode=mirrored`), Windows 방화벽에서 22·80번 인바운드를 허용하세요. 정확한 설정은 Microsoft의 "WSL 네트워킹" 문서를 확인하세요.
4. 2장의 설치(`sudo bash server/install.sh`)를 그대로 실행합니다. Docker Desktop을 쓰고 있다면 그 Docker를 그대로 씁니다.
5. **2주 동안 노트북을 켜 두어야 합니다.** 절전·최대 절전을 끄고, 전원을 연결해 두세요. WSL은 마지막 터미널을 닫으면 잠시 뒤 멈출 수 있으니, 운영 중에는 WSL 터미널 하나를 열어 두는 것이 안전합니다.
6. `public_host`에는 학생이 접속할 노트북의 IP(또는 이름)를 적습니다.

---

## 4. 설정 `/etc/bomblab/bomblab.ini`

```bash
sudo nano /etc/bomblab/bomblab.ini
sudo systemctl restart bomblab-reportd bomblab-web bomblab-builder   # 바꾼 뒤 재시작
```

- `[window]` `start_at`/`end_at` — 운영 기간(ISO 8601 + `+09:00`). 교육 직후부터 과제 공개 전까지 **2주**. 기간 밖에는 로그인·기록이 막힙니다. 둘 다 비우면 상시 개방.
- `[scoring]` — 과제형 폭탄 배점. 기본값은 원본 CMU 과제와 같음: `10,10,10,10,15,15`, 숨은 단계 +10, 폭발 -0.5(상한 20).
- `[practice] reissue_per_hour` — 학생이 연습·드릴을 다시 받을 수 있는 시간당 횟수(기본 30).
- `[server] public_host` — 카드·스코어보드 링크 주소.
- `[admin]` — `/admin` 로그인. 해시: `sudo bomblabctl hash-password` 출력을 `password_hash`에 붙여넣기.

---

## 5. 학생 계정 만들기 & 추가

### 5.1 최초 생성

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

학생마다 계정(`bomb01`, `bomb02`…)·무작위 비밀번호를 만들고 **폭탄 12개**(과제형 1 + 연습 1 + 드릴 10)를 빌드해 홈에 설치합니다. 30명이면 폭탄 360개라 몇 분 걸립니다. 운영 기간 전이면 계정은 **잠긴 상태**로 만들어지고, 기간이 시작되면 자동으로 열립니다. 산출물:

- `credentials.csv` (아이디·비밀번호·접속 명령) / `cards.html` (인쇄용 카드) — sudo 실행 사용자 소유로 생성되니 바로 내려받아 배포:
  ```bash
  # 로컬에서
  scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomb-contest/cards.html .
  ```

### 5.2 운영 중 학생 추가

**명단에 줄을 추가하고 provision을 다시 실행**하면 됩니다. 기존 학생은 이름(username을 적었으면 username)으로 알아보고 건너뛰므로 **기존 계정·비밀번호·폭탄·점수는 그대로**이고, 새 사람만 계정과 폭탄 12개를 만듭니다. 새 번호는 비어 있는 가장 작은 `bombNN`입니다. 그래서 **기존 줄의 이름을 고치지 마세요.** 이름이 바뀌면 새 사람으로 보고 계정을 하나 더 만듭니다. 처음 만든 `credentials.csv`·`cards.html`은 덮어쓰지 않고, 새 사람 것만 `credentials-<날짜시각>.csv`·`cards-<날짜시각>.html`로 따로 만듭니다.

```bash
sudo bomblabctl provision roster.csv
```

> provision 도중 빌드가 실패하면 계정은 만들어졌는데 폭탄이 없는 학생이 생길 수 있습니다. 원인을 고친 뒤 `sudo bomblabctl reissue <user> <bomb|practice|d0..d9>`로 채우세요.

---

## 6. 운영 명령어 레퍼런스 `bomblabctl`

> 심링크(`sudo bomblabctl …`)로 쳐서 `ModuleNotFound`가 나오면 전체 경로로: `sudo /opt/bomblab/server/bin/bomblabctl …`

| 명령 | 설명 |
|---|---|
| `provision <roster.csv>` | 계정+비밀번호+폭탄 12개+카드 생성 (기존자 건너뜀) |
| `reissue <user> <bomb\|practice\|d0..d9>` | 그 학생에게 새 폭탄 빌드·설치. 과제형도 가능(점수는 이전 기록 유지) |
| `solution <user> <bomb\|practice\|d0..d9>` | 그 학생 폭탄의 정답·풀이·힌트, 해제한 단계, **학생이 연 힌트** (8장 "학생 질문 대응") |
| `status` | 운영 상태·기간·학생 수·활성 폭탄 수 |
| `list` | 학생별 순위·점수·폭발·해제 단계·드릴 완료 수·연습 완주 수 |
| `open` | 지금 바로 열기 (운영 기간 무시) |
| `close` | 지금 바로 닫기 |
| `auto` | 수동 override 해제 → 운영 기간대로 |
| `tick` | 현재 상태에 맞게 로그인 열기/닫기 즉시 적용 |
| `lock <user>` / `unlock <user>` | 한 명만 잠금/해제 |
| `reset-password <user>` | 비밀번호 재발급(출력됨) |
| `export <out.csv>` | 점수·드릴 진도 + 전체 이벤트 CSV |
| `purge --yes` | 모든 학생 계정·홈 삭제 (export 후에!) |
| `hash-password` | admin 비밀번호 해시 생성 |

- **상태 우선순위**: 운영 기간으로 자동 전환되며, `open/close`는 그 위에 얹는 수동 덮어쓰기. `auto`로 자동 복귀. 15초 타이머가 상태에 맞춰 계정을 계속 맞춥니다.
- **주의**: 닫힌 상태에서 `unlock bomb01`만 하면 15초 뒤 다시 잠깁니다. 계속 열어두려면 `open`.

---

## 7. 2주 운영 타임라인

1. **교육 전**: 설치(2장), 설정(4장), provision(5장), 리허설(9장). 카드 인쇄.
2. **교육 당일**: 운영 기간 시작(`start_at`) 또는 `sudo bomblabctl open`. 카드 배부, D0부터 시작하도록 안내.
3. **운영 중 (2주)**: 가끔 `list`와 `/admin`으로 진행 확인. 학생 질문은 대부분 `bomblab hint`로 해결됩니다. 매일 DB 백업을 권장:
   ```bash
   sudo sqlite3 /var/lib/bomblab/bomblab.db ".backup '/home/ubuntu/bomblab-$(date +%F).db'"
   ```
4. **과제 공개 전날**: 운영 기간 종료(`end_at`) 또는 `sudo bomblabctl close`.
5. **정리**: `export` → 결과 저장 → `purge` → 인스턴스 Stop/Terminate.

---

## 8. 운영북 — 상황별 대처

### 학생 질문 대응

운영진이 모든 폭탄을 미리 풀어 둘 필요는 없습니다. 폭탄마다 정답·풀이·힌트가 자동으로 만들어져 있습니다.

| 볼 것 | 방법 |
|---|---|
| 전체 힌트 (모든 드릴 단계, 연습 폭탄 phase별 3개씩) | [`server/HINTS.md`](HINTS.md). 힌트는 학생마다 같고 정답은 없음 |
| 질문한 학생의 그 폭탄 정답·풀이 | `sudo bomblabctl solution bomb07 d3` (또는 `practice`, `bomb`) |
| 그 학생이 이미 연 힌트, 해제한 단계 | 같은 명령의 맨 위 세 줄 |

대응 순서:

1. **드릴·연습 폭탄**이면 먼저 `bomblab hint <폭탄> <단계>`를 쓰라고 안내합니다. `solution`으로 학생이 몇 번 힌트까지 열었는지 보고, 그다음 힌트 수준으로 말해 주세요.
2. 그래도 막히면 `solution`의 풀이를 보며 **어디를 보면 되는지**(어느 명령어, 어느 gdb 명령)만 짚어 줍니다. 정답을 불러 주면 연습이 되지 않습니다.
3. 해제하면 `bomblab notes <폭탄>`으로 해설이 열립니다. 풀이를 비교해 보라고 권하세요.
4. **과제형 `~/bomb`**은 실제 과제와 같은 조건이라 힌트·해설이 없습니다. 운영진도 그 폭탄의 답은 알려 주지 마세요. 대신 같은 개념의 드릴을 권합니다(`HINTS.md`의 phase마다 "연습할 드릴"이 적혀 있음). 예: phase 3에서 막힘 → D4, phase 6 → D7.

운영진이 직접 풀어 보는 것을 권장하는 범위: 드릴 D0~D9를 한 번씩(나눠서 맡아도 됨, 전부 약 10시간), 연습 폭탄 하나. 과제형은 연습 폭탄과 같은 종류라 따로 풀 필요가 없습니다.

### 접속 문제

**학생: 로그인이 `Account has expired`**
→ 운영 기간 밖이거나 계정이 잠김. `sudo bomblabctl status` 확인 후 `sudo bomblabctl open`(전체) 또는 `unlock <user>`(한 명).

**학생: `Permission denied (publickey)` (비밀번호를 못 넣음)**
→ 학생 그룹 비밀번호 로그인이 꺼진 것. 확인·조치:
```bash
sudo sshd -T -C user=bomb01 | grep -i passwordauthentication   # no면 문제
sudo systemctl reload ssh
```
(설정 파일 `sshd_config.d/bomblab.conf`의 `Match Group contestants → PasswordAuthentication yes` 가 적용됐는지)

**학생: `Could not resolve hostname … Temporary failure in name resolution`**
→ 그 학생이 **WSL**에서 접속 중일 가능성. WSL은 DNS가 따로 놀아 실패함. **PowerShell(윈도)·터미널(맥)** 로 접속하라고 안내. 급하면 도메인 대신 IP로.

**SSH가 `kex_exchange_identification: read: Connection reset by peer`로 끊김 (웹은 됨)**
→ 그 IP가 fail2ban에 차단됐을 가능성. 차단은 **IP 단위**라서 학교 와이파이처럼 한 IP를 같이 쓰면, 누군가 10분에 5번 틀리는 순간 그 와이파이의 모두(운영자 포함)가 1시간 막힙니다. 다른 회선(휴대폰 핫스팟)으로 운영자 접속 후:
```bash
sudo fail2ban-client status sshd                               # Banned IP list 확인
sudo fail2ban-regex /var/log/auth.log /etc/fail2ban/filter.d/sshd.conf --print-all-matched | grep <IP>   # 무엇이 실패로 세어졌나
sudo fail2ban-client set sshd unbanip <IP>                      # 즉시 해제
```
학교 IP는 `bomblab.ini`의 `[fail2ban] ignoreip`에 적고 `sudo bash server/install.sh`를 다시 실행하면 예외가 됩니다. 차단 목록이 비어 있는데도 끊기면 sshd 기록(`sudo journalctl -u ssh --since today | grep <IP>`)을 확인합니다. 기록이 없으면 연결이 서버에 오기 전에 끊긴 것이니 학교망 문제입니다.

**비밀번호 분실**
→ `sudo bomblabctl reset-password bomb07` → 출력된 새 비밀번호 전달.

### 기록·스코어보드 문제

**학생: "기록 서버에 연결할 수 없습니다"**
→ reportd 확인:
```bash
sudo systemctl status bomblab-reportd
sudo systemctl restart bomblab-reportd
stat /run/bomblab/report.sock          # 0666 이어야 함
```
해제 기록은 유실되지 않으니 학생은 다시 실행하면 됩니다.

**학생: "This bomb is not active right now: ERR bad bomb"**
→ 그 폭탄이 재발급으로 교체된 것. 새 폭탄은 같은 위치(`~/practice`, `~/drills/dN`)에 설치되어 있으니 그것을 실행하라고 안내.

**스코어보드가 안 뜸**
```bash
sudo systemctl status bomblab-web nginx
sudo journalctl -u bomblab-web -n 50 --no-pager
sudo ss -ltnp | grep -E ':(80|443|8080)'
```

**점수가 안 오르는데 학생은 풀었다고 함**
→ `/admin`에서 그 학생 이벤트 확인. 과제형(`~/bomb`)이 아니라 연습·드릴을 풀었다면 점수에 들어가지 않는 것이 정상입니다(드릴은 진도표에 나옴). `invalid`가 찍혔으면 폭탄이 정답이 아닌 값을 보고한 것.

### 재발급 문제

**학생: `bomblab new ...`가 "만들지 못했습니다"**
```bash
sudo systemctl status bomblab-builder
sudo journalctl -u bomblab-builder -n 50 --no-pager
sudo docker image inspect bomblab-gcc48 >/dev/null && echo image-ok
```
이미지가 없으면 2.5의 백업에서 불러오거나 `sudo bash server/install.sh`로 다시 만듭니다. 실패해도 학생의 이전 폭탄은 그대로 동작합니다.

**학생: `bomblab new ...`가 "한 시간에 받을 수 있는 횟수를 넘었습니다"**
→ `[practice] reissue_per_hour`를 늘리고 reportd 재시작. 또는 운영자가 직접 `sudo bomblabctl reissue <user> d3`.

### 계정·부정행위

**한 명 즉시 차단**
```bash
sudo bomblabctl lock bomb07        # 로그인 차단
sudo pkill -KILL -u bomb07         # 접속 중 세션도 끊기
```
`/admin`의 이벤트·입력 원문으로 정황 확인.

### 인프라 문제

**운영 기간 연장**
→ `bomblab.ini`의 `end_at`을 늦추고 `sudo systemctl restart bomblab-reportd bomblab-web`.

**서버가 재부팅됨**
→ 서비스 4종은 자동 시작. 확인:
```bash
sudo bomblabctl status
sudo systemctl is-active bomblab-reportd bomblab-web bomblab-builder
```

**Stop→Start로 IP가 바뀜**
→ 가비아 A 레코드를 새 IP로 수정(그 외 nginx·인증서·계정·카드는 그대로).

---

## 9. 리허설 (운영 전 필수)

```bash
sudo bomblabctl open
sudo bomblabctl provision test-roster.csv    # 가짜 2~3명
# 테스트 계정으로 ssh 접속해서:
#   cd ~/drills/d0 && ./bomb      → 폭발/해제가 스코어보드 드릴 진도에 반영되는지
#   bomblab                       → 폭탄 목록
#   bomblab hint d0 1 / bomblab notes d0
#   bomblab new d0                → 새 폭탄이 설치되는지
#   cd ~/bomb && ./bomb           → 과제형 점수표에 반영되는지
sudo bomblabctl reissue bomb01 bomb          # 운영자 재발급
sudo bomblabctl export test.csv               # 결과 뽑히는지
sudo bomblabctl purge --yes                   # 리허설 계정 정리
sudo bomblabctl auto
```

격리 확인(학생 계정에서): `ls /home/다른계정`·`cat /var/lib/bomblab/bomblab.db`·`ls /opt/bomblab`·`ls /var/lib/bomblab/bombs` 모두 거부, `ps aux`에 남 프로세스 안 보임, `ssh -L` 거부.

무권한 자동 검증(로컬/WSL, Docker 필요):
```bash
make toolchain                   # 처음 한 번
make verify                      # 문제은행 전체 + 런타임 + 원본 대조(ref/ 있을 때)
bash tools/server_selftest.sh    # 기록·재채점·해설·힌트·재발급·운영 기간·인증
```

---

## 10. 종료 후

```bash
sudo bomblabctl export result.csv                       # result.csv + result.csv.events.csv
sudo cp /var/lib/bomblab/bomblab.db ~/bomblab-backup.db  # 원본 백업
# 로컬로 내려받기
scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomb-contest/result.csv .
sudo bomblabctl purge --yes                             # 계정·홈 삭제 (백업 후!)
```

그다음 EC2 콘솔에서 **인스턴스 Stop/Terminate**. 탄력적 IP를 썼다면 release까지. **켜둔 시간만큼 과금**되니 잊지 마세요.
