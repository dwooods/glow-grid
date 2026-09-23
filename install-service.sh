#!/usr/bin/env bash
# Install (or update) the glow-grid-web systemd service so the web control
# starts at boot. Run from the repo folder:
#   sudo bash install-service.sh
# Remove it with:
#   sudo bash install-service.sh --remove
set -e

SERVICE=glow-grid-web
UNIT=/etc/systemd/system/$SERVICE.service

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo bash install-service.sh"
    exit 1
fi

if [ "$1" = "--remove" ]; then
    systemctl disable --now "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT"
    systemctl daemon-reload
    echo "Removed $SERVICE."
    exit 0
fi

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
RUN_USER="${SUDO_USER:-$(stat -c %U "$DIR")}"

if [ ! -x "$DIR/venv/bin/python" ]; then
    echo "No venv yet. Run ./run.sh once first (as $RUN_USER, not root), then re-run this."
    exit 1
fi

cat > "$UNIT" << UNITEOF
[Unit]
Description=Glow Grid web control (16x16 LED panel)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 1
systemctl --no-pager --lines=5 status "$SERVICE" || true
echo
echo "Glow Grid web control: http://$(hostname).local:8080"
