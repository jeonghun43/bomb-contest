# previous/ — 1판: 대회용 자체제작 폭탄 + 대회 서버 (보관용)

2026-09에 만든 **대회용** 버전입니다. 2026-10-05에 대회를 열지 않기로 하면서, 저장소 루트는 **연습 서버**(개념 드릴 + CMU 구조 폭탄, [specs/003](../specs/003-practice-bank/spec.md))로 바뀌었고, 이전 것은 모두 이 폴더로 옮겼습니다.

**이 폴더는 실서버에 올리지 않습니다.** `server/install.sh`(루트의 것)는 `previous/`를 복사 대상에서 제외합니다.

## 무엇이 들어 있나

| 경로 | 내용 |
|---|---|
| `src/` | 자체제작 폭탄 C 소스 (회전·XOR, LFSR, 토러스, 모듈러 역원, 트리 경로, 마스크 사슬, 비트 역순 secret) |
| `tools/gen_bomb.py` | 시드별 상수·정답·해설 생성기 |
| `tools/bombcheck.py`, `fuzz_checker.py`, `check_secret_unique.py`, `verify.sh` | 서버 재채점기, 판정 일치 퍼저, 유일해 검사, 오프라인 검증 |
| `tools/server_selftest.sh` | 대회 서버 셀프테스트 |
| `server/` | 대회 서버: 시작·프리즈·종료 상태 기계, 리더보드, `bomblabctl start/freeze/stop` |
| `docs/` | 참가자 안내(대회 규칙), 개념 정리(자체제작 폭탄 기준) |
| `specs/001-new-bomb/` | 대회용 폭탄 spec·plan·tasks |
| `specs/002-contest-server/` | 대회 서버 spec·plan·tasks (1판) |
| `Makefile` | 호스트 gcc 빌드 (`make SEED=n`, `make verify FROM=1 TO=20`) |

커밋된 1판(`first commit`)에, 커밋 전이던 운영자 수정 세 가지를 반영해 두었습니다: `bomblabctl`의 `own_by_invoker`(provision 산출물을 sudo 실행자 소유로), 참가자 안내의 WSL 접속 주의, AWS 배포를 합친 운영자 매뉴얼(`server/README.md`, 그래서 `DEPLOY-AWS.md`는 없음).

## 지금 버전과 같이 쓰는 것

**코드끼리 서로 불러 쓰는 것은 없습니다.** 지금 버전(`bank/`, `toolchain/`, 새 `tools/`)은 이 폴더의 어떤 파일도 import하거나 빌드에 쓰지 않고, 이 폴더도 바깥을 참조하지 않습니다. 각각 단독으로 동작합니다.

지금 버전의 서버(`server/`)는 이 폴더의 서버를 **고쳐서** 만든 것입니다. 아래 5개만 내용이 완전히 같고, 각 폴더에 한 부씩 들어 있습니다.

| 파일 | 역할 |
|---|---|
| `server/bomblab/__init__.py` | 패키지 표시 |
| `server/etc/sshd_config.d/bomblab.conf` | 학생 그룹만 비밀번호 로그인, 포워딩 차단 |
| `server/etc/system/bomblab-contestant.slice` | 학생별 CPU·메모리·프로세스 상한 |
| `server/nginx/bomblab.conf` | 80번 → 웹 서버 프록시 |
| `server/systemd/bomblab-scheduler.timer` | 15초마다 로그인 열기/닫기 |

설계도 이어집니다: 접속 uid(`SO_PEERCRED`)로 신원 확인, 폭탄의 해제 보고를 서버가 다시 판정, 보고 프로토콜(`HELLO`/`EVENT`), 학생 격리.

## 아직 돌려 볼 수 있나

네. 이 폴더 안에서 단독으로 빌드·검증됩니다(호스트 gcc, Linux/WSL).

```bash
cd previous
make SEED=3                      # build/seed-3/bomb, 정답은 build/seed-3/solution.txt
make verify FROM=1 TO=20         # 유일해 + 판정 일치 퍼징
```

2026-10-06에 `make SEED=3`과 `make verify FROM=1 TO=2`(52/52 통과)로 확인했습니다. 이 폴더의 `server/install.sh`는 같은 경로(`/opt/bomblab`, 같은 서비스 이름)를 쓰므로, 지금 버전이 설치된 서버에서 실행하면 안 됩니다.
