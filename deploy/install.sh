#!/usr/bin/env bash
# Idempotent fresh-Pi bootstrap. Run on a clean Raspberry Pi OS Bookworm 64-bit.
# Re-running upgrades safely.

set -euo pipefail

echo "== Updating apt =="
sudo apt-get update -qq
sudo apt-get upgrade -y

echo "== Installing system deps (Postgres client, I2C tools, build deps, Docker) =="
sudo apt-get install -y --no-install-recommends \
  build-essential \
  curl ca-certificates gnupg \
  i2c-tools libi2c-dev \
  python3-pip python3-venv python3-libgpiod python3-picamera2 \
  postgresql-client \
  ufw

echo "== Enabling I2C, camera, hardware watchdog =="
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_camera 0 || true   # already enabled on Bookworm
if ! grep -q '^dtparam=watchdog=on' /boot/firmware/config.txt; then
  echo 'dtparam=watchdog=on' | sudo tee -a /boot/firmware/config.txt
fi

echo "== Installing Docker (rootless, official convenience script) =="
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
fi

echo "== Creating wallgarden user and dirs =="
if ! id wallgarden >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash wallgarden
  sudo usermod -aG i2c,gpio,video,dialout wallgarden
fi
sudo install -d -o wallgarden -g wallgarden -m 0755 \
  /var/lib/wallgarden \
  /var/lib/wallgarden/photos \
  /etc/wallgarden

echo "== Firewall (LAN-only) =="
sudo ufw allow from 192.168.0.0/16 to any port 3100 proto tcp || true
sudo ufw --force enable

echo "== Done. Next steps =="
cat <<'EOF'

  1. Copy .env to /etc/wallgarden/daemon.env and edit DATABASE_URL etc.
  2. Configure Kamal on your dev machine pointing at this Pi:
       cd web && kamal setup
  3. Or use the systemd fallback under deploy/systemd/.

EOF
