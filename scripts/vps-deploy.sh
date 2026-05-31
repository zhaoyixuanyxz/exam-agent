#!/bin/bash
# Ubuntu 22.04+ on cloud VPS (run as root or with sudo)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y docker.io docker-compose-v2 git
  systemctl enable --now docker
fi

if [ ! -f .env.deploy ]; then
  cp .env.deploy.example .env.deploy
  echo "Edit .env.deploy and set DEEPSEEK_API_KEY, then run this script again."
  exit 1
fi

if ! grep -qE '^DEEPSEEK_API_KEY=sk-' .env.deploy 2>/dev/null; then
  echo "DEEPSEEK_API_KEY missing in .env.deploy"
  exit 1
fi

docker compose up -d --build
echo ""
echo "Done. Open http://$(curl -sS ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):80"
echo "Ensure cloud security group allows TCP 80."
