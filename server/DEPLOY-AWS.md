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

## 3. 퍼블릭 IP 확인 (탄력적 IP는 선택)

인스턴스가 생성되면 **자동 할당 퍼블릭 IPv4**가 붙습니다. 인스턴스 세부 정보의 "퍼블릭 IPv4 주소"를 그대로 DNS에 쓰면 됩니다. **하루짜리 대회면 이걸로 충분합니다.**

- 재부팅(reboot)해도 이 IP는 유지됩니다.
- 단, 인스턴스를 **Stop → Start** 하면 IP가 **바뀝니다**. 그러면 4번의 A 레코드를 새 IP로 고쳐야 합니다.

**탄력적 IP(Elastic IP)는 필수가 아닙니다.** 며칠 전 미리 셋업해두고 비용을 아끼려 인스턴스를 껐다 켜는 경우에만, IP를 고정하려고 씁니다(EC2 콘솔 → 탄력적 IP → 할당 → 인스턴스에 연결). 참고로 2024년 2월부터 자동 IP·탄력적 IP 모두 실행 중이면 요금이 같으니(시간당 약 $0.005), "탄력적 IP라서 더 비싸다"는 아닙니다 — 다만 **할당만 해놓고 안 붙이거나 인스턴스가 꺼져 있으면** 그 시간은 과금되니, 안 쓸 거면 할당하지 마세요.

## 4. DNS A 레코드

가비아(또는 도메인 관리 페이지)에서:

| 타입 | 이름(호스트) | 값 |
|---|---|---|
| A | `bomb` | 인스턴스의 퍼블릭 IPv4 (탄력적 IP를 붙였다면 그 IP) |

반영 확인 (몇 분 후): 로컬에서 `nslookup bomb.doublejeong.com` → 그 IP가 나와야 함.

> **미리 셋업 후 인스턴스를 껐다 켤 계획이라면**, 지금 이 A 레코드의 **TTL을 300초(5분)로 낮춰두세요.** 이유와 대회날 절차는 아래 [셋업 후 Stop → 대회날 Start](#셋업-후-stop--대회날-start-선택) 절 참고.

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

## 셋업 후 Stop → 대회날 Start (선택)

며칠 전 미리 셋업·리허설을 끝내고 비용을 아끼려 인스턴스를 **Stop** 해두었다가, 대회 당일 **Start** 하는 경우입니다. 자동 퍼블릭 IP는 Stop→Start 하면 **바뀌지만**, IP에 묶인 건 **가비아 A 레코드 하나뿐**입니다. 나머지는 전부 도메인 이름이나 localhost 기반이라 그대로 돌아갑니다.

### 바뀌는 것 / 안 바뀌는 것

| 구성 요소 | Stop→Start 후 |
|---|---|
| **가비아 A 레코드** | **새 IP로 수정 필요** |
| nginx (`server_name`, `127.0.0.1:8080`) | 그대로 |
| `bomblab.ini` (`public_host`, socket, db) | 그대로 |
| **TLS 인증서** (도메인에 발급됨) | **그대로 유효** — 재발급 불필요 |
| 참가자 계정·DB·시드·폭탄 | 그대로 |
| 배부한 카드(`cards.html`의 `ssh …@bomb.doublejeong.com`) | 그대로 유효 |
| 보안 그룹, SSH 호스트 키 | 그대로 (호스트 키 경고 없음) |
| systemd 서비스 3종(reportd·web·scheduler) | 부팅 시 **자동 시작** |

즉 재프로비저닝·인증서 재발급·서비스 수동 재시작 **모두 불필요**합니다.

### ⚠️ 미리 해둘 것 — TTL 낮추기

A 레코드를 새 IP로 바꿔도, 참가자의 DNS 캐시가 **옛 IP를 붙들고** 있으면 TTL이 만료될 때까지 접속이 안 됩니다. 가비아 기본 TTL이 3600초면 최대 1시간 먹통일 수 있습니다.

→ **셋업 단계(며칠 전)에 미리 A 레코드 TTL을 300초로 낮춰두세요.** 그러면 대회날 IP를 바꿔도 5분이면 퍼집니다. (TTL 변경 자체도 옛 TTL만큼 걸리므로 반드시 *미리* 낮춰야 합니다.)

### 대회날 Start 체크리스트

1. 인스턴스 **Start** → 세부 정보에서 **새 퍼블릭 IPv4** 확인
2. 가비아 A 레코드 값을 **새 IP로 수정** (TTL은 이미 300초로 낮춰둔 상태)
3. 5~10분 후 `nslookup bomb.doublejeong.com` → 새 IP가 나오는지 확인
   - 급하면 관리자는 도메인 대신 **새 IP로 바로** SSH 접속해 점검 가능: `ssh -i bomblab-key.pem ubuntu@<새 IP>`
4. `https://bomb.doublejeong.com` 열어 리더보드가 뜨는지, `bomblabctl status`로 상태 확인
5. 시작 시각이 되면 자동 개방 (또는 `sudo bomblabctl start`)

### 이 번거로움을 피하려면

- **(a)** 셋업 후 끄지 말고 대회까지 그냥 켜둔다 — 비용이 조금 더 들지만 IP가 안 바뀜.
- **(b)** [탄력적 IP](#3-퍼블릭-ip-확인-탄력적-ip는-선택)를 붙여둔다 — IP가 고정되어 A 레코드를 아예 안 건드림. (단 Stop 동안에도 소액 과금)

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
- 탄력적 IP를 **썼다면**, Terminate 후 할당 해제(release)까지 하세요 — 인스턴스가 없는데 할당만 남은 탄력적 IP는 계속 소액 과금됩니다. (안 썼으면 신경 쓸 것 없음)
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
