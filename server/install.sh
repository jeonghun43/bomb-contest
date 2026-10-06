#!/usr/bin/env bash
#
# install.sh - Set up the Bomb Lab practice server on Ubuntu 22.04 / 24.04
# (an EC2 instance, or WSL2 Ubuntu with systemd enabled on a laptop).
#
#   sudo ./server/install.sh
#
# Idempotent: safe to re-run. It installs packages (including docker),
# builds the original toolchain image (GCC 4.8.1, toolchain/Dockerfile),
# creates the service account and student group, copies the repo to
# /opt/bomblab, installs the student CLI, systemd units, nginx site and the
# student isolation settings, then prints a self-check. It does NOT create
# students - use `bomblabctl provision` for that.
#
# The toolchain image is built from Ubuntu 12.04 archives that may disappear
# one day. Keep a copy:  docker save bomblab-gcc48 | gzip > bomblab-gcc48.tar.gz
# If that file sits next to this repo (../bomblab-gcc48.tar.gz) or at
# /opt/bomblab-gcc48.tar.gz, install.sh loads it instead of rebuilding.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "root로 실행하세요: sudo ./server/install.sh" >&2
    exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)"   # repo root
DEST=/opt/bomblab

# A freshly booted cloud instance runs unattended-upgrades / cloud-init, which
# holds the apt lock. Wait for it to finish instead of failing or hanging
# silently. (If `fuser` isn't installed the loop just exits and we proceed;
# the DPkg::Lock::Timeout below is the belt-and-suspenders fallback.)
wait_apt() {
    local waited=0
    while fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock \
                /var/lib/apt/lists/lock /var/cache/apt/archives/lock \
                >/dev/null 2>&1; do
        [ "$waited" -eq 0 ] && \
            echo "   다른 apt 작업(부팅 직후 자동 업데이트 등)이 끝나길 기다리는 중..."
        waited=$((waited + 1))
        sleep 3
    done
}

# Ask apt itself to wait up to 10 min for the lock, and keep normal output so
# download progress is visible.
APT_OPTS="-o DPkg::Lock::Timeout=600"

echo "== 1. 패키지 설치 =="
export DEBIAN_FRONTEND=noninteractive
wait_apt
apt-get $APT_OPTS update
wait_apt
apt-get $APT_OPTS install -y \
    build-essential binutils gdb python3 nginx sqlite3 rsync fail2ban
echo "   build-essential binutils gdb python3 nginx sqlite3 rsync fail2ban"
# docker: Docker Desktop (WSL) or an existing engine is fine; else Ubuntu's.
if ! command -v docker >/dev/null 2>&1; then
    wait_apt
    apt-get $APT_OPTS install -y docker.io
fi
systemctl enable --now docker >/dev/null 2>&1 || true
echo "   docker $(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ,)"
# The box is internet-exposed with password logins, so throttle SSH brute force.
cat > /etc/fail2ban/jail.d/bomblab.conf <<'F2B'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
findtime = 10m
F2B
systemctl enable --now fail2ban >/dev/null 2>&1 || true

echo "== 2. 계정/그룹 =="
id bomblab >/dev/null 2>&1 || useradd --system --home /opt/bomblab \
    --shell /usr/sbin/nologin bomblab
getent group contestants >/dev/null || groupadd contestants
echo "   user=bomblab group=contestants"

echo "== 3. 파일 배치 =="
mkdir -p "$DEST"
# Copy the whole repo except build artefacts and any local secrets.
# ref/ holds the original CMU bomb for calibration: it never goes to a server.
# previous/ is the archived contest version; the practice server does not use it.
rsync -a --delete \
    --exclude 'build/' --exclude 'dist/' --exclude 'ref/' --exclude 'previous/' \
    --exclude '*.log' \
    --exclude '__pycache__/' --exclude 'credentials.csv' --exclude 'cards.html' \
    --exclude '.git/' \
    "$SRC/" "$DEST/"
chown -R root:bomblab "$DEST"
chmod -R o-rwx "$DEST"           # contestants cannot read the generator/source
chmod 0750 "$DEST"

install -d -o bomblab -g bomblab -m 0700 /var/lib/bomblab
install -d -o bomblab -g bomblab -m 0700 /var/lib/bomblab/bombs
install -d -o root   -g bomblab -m 0750 /etc/bomblab
if [ ! -f /etc/bomblab/bomblab.ini ]; then
    install -o root -g bomblab -m 0640 \
        "$DEST/server/etc/bomblab.ini.example" /etc/bomblab/bomblab.ini
    echo "   /etc/bomblab/bomblab.ini 생성됨 (값을 채우세요)"
else
    echo "   /etc/bomblab/bomblab.ini 유지"
fi
ln -sf "$DEST/server/bin/bomblabctl" /usr/local/sbin/bomblabctl
chmod 0755 "$DEST/server/bin/bomblabctl"
# Student CLI: a copy, because students cannot read /opt/bomblab.
install -o root -g root -m 0755 "$DEST/server/bin/bomblab" /usr/local/bin/bomblab
echo "   bomblabctl (운영자), /usr/local/bin/bomblab (학생)"

echo "== 4. 툴체인 이미지 (GCC 4.8.1) =="
IMAGE=bomblab-gcc48
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "   $IMAGE 이미 있음"
else
    for tarball in "$SRC/../bomblab-gcc48.tar.gz" /opt/bomblab-gcc48.tar.gz; do
        if [ -f "$tarball" ]; then
            echo "   $tarball 에서 불러오는 중"
            gunzip -c "$tarball" | docker load >/dev/null && break
        fi
    done
    if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "   빌드 중 (Ubuntu 12.04 + gcc-4.8 4.8.1, 몇 분 걸림)"
        docker build -q -t "$IMAGE" "$DEST/toolchain" >/dev/null
    fi
fi
docker run --rm "$IMAGE" gcc --version | head -1 | sed 's/^/   /'

echo "== 5. systemd 유닛 =="
cp "$DEST"/server/systemd/*.service "$DEST"/server/systemd/*.timer \
    /etc/systemd/system/
systemctl daemon-reload
for unit in bomblab-reportd.service bomblab-web.service \
            bomblab-builder.service bomblab-scheduler.timer; do
    systemctl enable "$unit" >/dev/null 2>&1
done
# restart (not just start) so re-running install.sh after a code update
# actually reloads the new Python code into the running daemons.
systemctl restart bomblab-reportd.service
systemctl restart bomblab-web.service
systemctl restart bomblab-builder.service
systemctl start bomblab-scheduler.timer >/dev/null 2>&1
echo "   reportd / web / builder / scheduler.timer 활성화·재시작"

echo "== 6. nginx =="
# Only install the site config on first setup. certbot edits this file to add
# the HTTPS (443) server block, so re-running install.sh must NOT clobber it.
if [ ! -f /etc/nginx/sites-available/bomblab ]; then
    cp "$DEST/server/nginx/bomblab.conf" /etc/nginx/sites-available/bomblab
    echo "   nginx 사이트 설정 생성"
else
    echo "   기존 nginx 사이트 설정 유지 (certbot HTTPS 변경 보존)"
fi
ln -sf /etc/nginx/sites-available/bomblab /etc/nginx/sites-enabled/bomblab
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 && systemctl reload nginx
echo "   HTTPS는 certbot으로 설정: sudo certbot --nginx -d <도메인>"

echo "== 7. 학생 격리 =="
cp "$DEST/server/etc/sshd_config.d/bomblab.conf" /etc/ssh/sshd_config.d/
systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
mkdir -p /etc/systemd/system/user-.slice.d
cp "$DEST/server/etc/system/bomblab-contestant.slice" \
    /etc/systemd/system/user-.slice.d/50-bomblab.conf
systemctl daemon-reload
# New users get a private home and umask 077.
sed -i 's/^UMASK.*/UMASK 077/' /etc/login.defs 2>/dev/null || true
grep -q 'HOME_MODE' /etc/login.defs || echo 'HOME_MODE 0700' >> /etc/login.defs
# Hide other users' processes (pid namespaces would be heavier; hidepid is enough).
if ! grep -q 'hidepid=' /etc/fstab; then
    echo 'proc /proc proc defaults,hidepid=invisible,gid=0 0 0' >> /etc/fstab
    mount -o remount,hidepid=invisible,gid=0 /proc 2>/dev/null || true
    echo "   /proc hidepid=invisible 적용 (재부팅 후 영구)"
fi
echo "   sshd 포워딩 차단, 사용자 슬라이스 자원 제한, /home 0700"

echo
echo "== 자체 점검 =="
systemctl is-active bomblab-reportd.service && echo "  reportd: active" || echo "  reportd: FAILED"
systemctl is-active bomblab-web.service && echo "  web: active" || echo "  web: FAILED"
systemctl is-active bomblab-builder.service && echo "  builder: active" || echo "  builder: FAILED"
[ -S /run/bomblab/report.sock ] && \
    echo "  socket: $(stat -c '%a %U:%G' /run/bomblab/report.sock)" || \
    echo "  socket: 아직 없음 (reportd 로그 확인)"
echo
echo "다음 단계:"
echo "  1) sudo nano /etc/bomblab/bomblab.ini   (운영 기간·public_host·admin 해시)"
echo "     admin 해시:  bomblabctl hash-password"
echo "  2) sudo bomblabctl provision roster.csv   (학생 1명당 폭탄 12개 빌드)"
echo "  3) 운영 기간이 되면 자동 개방 (즉시 열기: sudo bomblabctl open)"
echo "  4) 이미지 백업:  docker save bomblab-gcc48 | gzip > ~/bomblab-gcc48.tar.gz"
