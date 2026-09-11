#!/usr/bin/env bash
#
# install.sh - Set up the Bomb Lab contest server on Ubuntu 22.04 / 24.04.
#
#   sudo ./server/install.sh
#
# Idempotent: safe to re-run. It installs packages, creates the service
# account and contestant group, copies the repo to /opt/bomblab, installs
# systemd units, nginx site, and the contestant isolation settings, then
# prints a self-check. It does NOT start the contest or create contestants -
# use bomblabctl for that.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "root로 실행하세요: sudo ./server/install.sh" >&2
    exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)"   # repo root
DEST=/opt/bomblab

echo "== 1. 패키지 설치 =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential gdb python3 nginx sqlite3 rsync fail2ban >/dev/null
echo "   build-essential gdb python3 nginx sqlite3 rsync fail2ban"
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
rsync -a --delete \
    --exclude 'build/' --exclude 'dist/' --exclude '*.log' \
    --exclude '__pycache__/' --exclude 'credentials.csv' --exclude 'cards.html' \
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

echo "== 4. systemd 유닛 =="
cp "$DEST"/server/systemd/*.service "$DEST"/server/systemd/*.timer \
    /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bomblab-reportd.service >/dev/null 2>&1
systemctl enable --now bomblab-web.service >/dev/null 2>&1
systemctl enable --now bomblab-scheduler.timer >/dev/null 2>&1
echo "   reportd / web / scheduler.timer 활성화"

echo "== 5. nginx =="
cp "$DEST/server/nginx/bomblab.conf" /etc/nginx/sites-available/bomblab
ln -sf /etc/nginx/sites-available/bomblab /etc/nginx/sites-enabled/bomblab
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 && systemctl reload nginx
echo "   사이트 활성화, HTTPS는 certbot으로 별도 설정"

echo "== 6. 참가자 격리 =="
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
[ -S /run/bomblab/report.sock ] && \
    echo "  socket: $(stat -c '%a %U:%G' /run/bomblab/report.sock)" || \
    echo "  socket: 아직 없음 (reportd 로그 확인)"
echo
echo "다음 단계:"
echo "  1) sudo nano /etc/bomblab/bomblab.ini   (시각·점수·public_host·admin 해시)"
echo "     admin 해시:  bomblabctl hash-password"
echo "  2) sudo bomblabctl provision roster.csv"
echo "  3) 시작 시각이 되면 자동 개방 (또는 sudo bomblabctl start)"
