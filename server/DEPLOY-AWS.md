# AWS EC2 배포 가이드

대회 서버를 AWS EC2에 올리는 전체 절차입니다. `server/README.md`(운영 매뉴얼)의 AWS 버전으로, 처음부터 끝까지 따라 하면 됩니다. 예시 도메인은 `bomb.doublejeong.com`이니 본인 값으로 바꿔 넣으세요.

---

## 0. 사전 확인

- AWS 계정, 결제 수단 등록됨
- 도메인 DNS를 편집할 수 있음 (A 레코드 추가)
- 폭탄 저장소가 **비공개(private) GitHub 저장소**에 올라가 있음

## ⚠️ 가장 중요 — 인스턴스는 반드시 x86-64

참가자는 서버에 접속해 **그 안에서 폭탄을 실행**합니다. 서버 CPU 아키텍처가 곧 폭탄 아키텍처입니다. 이 폭탄은 x86-64 리버싱 문제이므로:

| | 인스턴스 | 비고 |
|---|---|---|
| ✅ 사용 | **t3.medium** (Intel), t3a.medium (AMD) | x86-64 |
| ❌ 금지 | t4g·m6g·c7g 등 (Graviton) | ARM → gcc가 ARM 바이너리 생성, 문제 전체가 깨짐 |

30명 기준 **t3.medium (2 vCPU / 4GB)** 권장. (t3.small은 2GB라 gdb 여러 개 뜨면 빠듯합니다.)

---

## 1. EC2 인스턴스 생성

EC2 콘솔 → **인스턴스 시작**:

| 항목 | 값 |
|---|---|
| 리전 | **서울 (ap-northeast-2)** — 참가자 지연 최소 |
| 이름 | `bomblab` |
| AMI | **Ubuntu Server 24.04 LTS (x86)** (22.04도 가능) |
| 아키텍처 | **64비트(x86)** ← ARM 아님 |
| 인스턴스 타입 | **t3.medium** |
| 키 페어 | 새로 생성 → `bomblab-key.pem` 다운로드 (관리자 접속용, 잘 보관) |
| 스토리지 | 기본 8GB gp3 (충분) |

보안 그룹은 다음 단계에서 만들거나, 생성 화면에서 바로 아래 규칙을 넣습니다.

## 2. 보안 그룹 (방화벽) 인바운드 규칙

| 유형 | 포트 | 소스 | 용도 |
|---|---|---|---|
| SSH | 22 | `0.0.0.0/0` | 참가자·관리자 SSH |
| HTTP | 80 | `0.0.0.0/0` | certbot 인증 + HTTPS 리다이렉트 |
| HTTPS | 443 | `0.0.0.0/0` | 리더보드 |

- **8080은 열지 마세요.** 웹 서버는 `127.0.0.1:8080`에만 묶여 있고 nginx가 앞단에서 프록시합니다.
- 팁: 셋업 동안은 22 소스를 **내 IP**로 좁혀두고, 대회 직전 `0.0.0.0/0`으로 넓혀도 됩니다.

## 3. 탄력적 IP (Elastic IP)

EC2 콘솔 → **탄력적 IP** → 할당 → 방금 인스턴스에 **연결**.

- 재부팅해도 IP가 고정되어 DNS가 계속 유효합니다.
- 인스턴스에 연결된 상태면 추가 과금 없음 (할당만 하고 방치하면 소액 과금).

## 4. DNS A 레코드

도메인 관리 페이지에서:

| 타입 | 이름(호스트) | 값 |
|---|---|---|
| A | `bomb` | 위 탄력적 IP |

반영 확인 (몇 분 후): 로컬에서 `nslookup bomb.doublejeong.com` → 탄력적 IP가 나와야 함.

## 5. 서버 접속 & 저장소 가져오기

로컬(내 PC)에서 키로 접속:

```bash
chmod 400 bomblab-key.pem            # macOS/Linux. Windows는 생략 가능
ssh -i bomblab-key.pem ubuntu@bomb.doublejeong.com
```

첫 접속 시 지문 확인 `yes`. 접속되면 프롬프트가 `ubuntu@...:~$`.

비공개 저장소를 가져오는 방법(하나 선택):

- **A. Personal Access Token (간단)** — GitHub → Settings → Developer settings → Fine-grained token (해당 repo read 권한). 서버에서:
  ```bash
  git clone https://<TOKEN>@github.com/<계정>/bomblab.git
  ```
- **B. Deploy key** — 서버에서 `ssh-keygen -t ed25519` → 공개키를 저장소 Settings → Deploy keys에 등록 → `git clone git@github.com:<계정>/bomblab.git`
- **C. 그냥 복사** — 로컬에서 `scp -i bomblab-key.pem -r ./bomblab ubuntu@bomb.doublejeong.com:~/`

> 저장소 내용은 정답 로직을 포함하므로, 대회 계정(참가자)이 읽을 수 없는 곳에 둡니다. `install.sh`가 이를 `/opt/bomblab`(0750, 참가자 접근 불가)으로 옮기니, 클론 위치(`~ubuntu/bomblab`)는 임시로 봐도 됩니다.

## 6. 설치

```bash
cd bomblab
sudo ./server/install.sh
```

패키지 설치 → `bomblab` 계정·`contestants` 그룹 → `/opt/bomblab` 배치 → systemd 3종 → nginx → 참가자 격리(SSH 포워딩 차단·**참가자 그룹만 비밀번호 로그인 허용**·자원 제한·`/home` 0700·`/proc hidepid`) → fail2ban(SSH 무차별 대입 차단)까지 수행하고 자체 점검을 출력합니다.

> AWS Ubuntu는 비밀번호 로그인을 기본 차단하지만, 설치 시 넣는 `sshd_config.d/bomblab.conf`가 **참가자 그룹에만** 비밀번호 로그인을 켭니다. 관리자(ubuntu) 본인은 계속 `.pem` 키로만 들어갑니다.

## 7. 설정

```bash
sudo nano /etc/bomblab/bomblab.ini
```

- `[contest]` `start_at`/`freeze_at`/`end_at` — 대회 시각 (ISO 8601 + `+09:00`)
- `[scoring]` — 배점 (기본 각 10점 + secret 10점 / 원본 CMU는 `10,10,10,10,15,15`)
- `[server] public_host = bomb.doublejeong.com`
- `[admin]` — 관리자 화면 로그인:
  ```bash
  sudo bomblabctl hash-password        # 비밀번호 입력 → sha256$... 출력
  # 출력값을 ini의 password_hash 에 붙여넣기
  ```

바꾼 뒤 재시작:
```bash
sudo systemctl restart bomblab-reportd bomblab-web
```

## 8. HTTPS 인증서

DNS가 서버를 가리키고 80이 열려 있으면 한 줄:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d bomb.doublejeong.com
```

certbot이 443·인증서·80→443 리다이렉트를 자동 설정하고 자동 갱신을 등록합니다. 끝나면 `https://bomb.doublejeong.com` 접속 가능.

## 9. 참가자 계정 만들기

명단 CSV(한 줄에 한 명, 닉네임만 있으면 됨):

```csv
# nickname[,username]
김철수
이영희
박민수,bomb_park
```

```bash
sudo bomblabctl provision roster.csv
```

- 계정·무작위 비밀번호·전용 폭탄을 만들어 `~/bomb/`에 설치하고 DB에 등록 (계정은 잠금 상태로 생성)
- 산출물: `credentials.csv`(0600), 인쇄용 `cards.html` → 로컬로 내려받아 배부:
  ```bash
  # 로컬에서
  scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomblab/cards.html .
  ```

## 10. 대회 전 리허설

```bash
sudo bomblabctl provision test-roster.csv    # 가짜 2~3명
# 시작 전: 다른 PC에서 ssh 로그인 → 거부되는지
sudo bomblabctl start                         # 열림
# 참가자 계정으로 ssh → ~/bomb/./bomb 실행 → 브라우저 리더보드 반영 확인
sudo bomblabctl freeze                         # 공개 보드 고정, /admin 은 계속 갱신
sudo bomblabctl export test.csv                # 순위 뽑히는지
sudo bomblabctl purge --yes                    # 리허설 계정 정리
```

자동 검증(빌드·서버 로직)은 `server/README.md` 8절 참고.

## 11. 대회 당일

| 상황 | 명령 |
|---|---|
| 상태·시각 확인 | `bomblabctl status` |
| 목록·점수·잠금 | `bomblabctl list` |
| 수동 시작/프리즈/종료 | `sudo bomblabctl start` / `freeze` / `stop` |
| 자동으로 되돌리기 | `sudo bomblabctl auto` |
| 비밀번호 재발급 | `sudo bomblabctl reset-password bomb07` |
| 관리자 화면 | `https://bomb.doublejeong.com/admin` (ini의 admin 계정) |

상태는 설정 시각에 따라 자동 전환되며(15초 타이머), 위 명령은 그 위에 얹는 수동 덮어쓰기입니다.

## 12. 종료 후 — 결과 저장 & 인스턴스 정리

```bash
sudo bomblabctl export result.csv                     # 순위 + 이벤트 CSV
sudo cp /var/lib/bomblab/bomblab.db ~/bomblab-backup.db
# 로컬로 내려받기
scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomblab/result.csv .
scp -i bomblab-key.pem ubuntu@bomb.doublejeong.com:~/bomblab-backup.db .
```

그다음 **인스턴스를 Stop 또는 Terminate** 하세요 (콘솔에서). 결과를 내려받기 전에 Terminate 하지 마세요.

## 💰 비용

- t3.medium 온디맨드: 서울 리전 대략 시간당 수십~백 원대. **하루 대회면 몇백 원~몇천 원.**
- **켜둔 시간만큼 계속 과금**되므로 대회 끝나면 반드시 Stop/Terminate.
- Terminate 하면 스토리지·탄력적 IP도 함께 정리하세요 (미사용 탄력적 IP는 소액 과금).
- 걱정되면 AWS Budgets로 소액 알림을 걸어두세요.

## 문제 해결

| 증상 | 조치 |
|---|---|
| 참가자 SSH가 `Permission denied` | 아직 시작 전이거나(계정 잠금), 비밀번호 오타. `bomblabctl status`로 상태 확인 |
| 참가자 로그인이 아예 안 됨(비밀번호 맞는데) | `sudo sshd -T \| grep -i passwordauth` 확인. `bomblab.conf`의 `Match Group contestants` 아래 `PasswordAuthentication yes`가 적용됐는지, `sudo systemctl reload ssh` |
| certbot 실패 | DNS가 아직 전파 안 됨(`nslookup` 확인), 80 포트 보안그룹 확인 |
| 리더보드 안 뜸 | `systemctl status bomblab-web nginx`, `journalctl -u bomblab-web` |
| "기록 서버 연결 실패" | `systemctl status bomblab-reportd`, 소켓 권한 `stat /run/bomblab/report.sock`(0666) |

자세한 운영·장애 대응은 [server/README.md](README.md)를 참고하세요.
