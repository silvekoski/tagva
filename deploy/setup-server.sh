#!/usr/bin/env bash
set -euo pipefail

host=${1:?usage: setup-server.sh HOST DEPLOY_PUBLIC_KEY_FILE}
deploy_key=${2:?usage: setup-server.sh HOST DEPLOY_PUBLIC_KEY_FILE}
here=$(cd "$(dirname "$0")" && pwd)

apt-get update
apt-get install -y caddy rsync curl libgomp1 libgl1
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

id tagva >/dev/null 2>&1 || useradd --system --create-home --home-dir /srv/tagva --shell /bin/bash tagva
install -d -o tagva -g tagva /srv/tagva/app /srv/tagva/data /srv/tagva/data/tags
chmod 711 /srv/tagva
install -d -m 700 -o tagva -g tagva /srv/tagva/.ssh
install -m 600 -o tagva -g tagva "$deploy_key" /srv/tagva/.ssh/authorized_keys

echo "tagva ALL=(root) NOPASSWD: /usr/bin/systemctl restart tagva-api" > /etc/sudoers.d/tagva
chmod 440 /etc/sudoers.d/tagva
visudo -cf /etc/sudoers.d/tagva

install -m 644 "$here/tagva-api.service" /etc/systemd/system/tagva-api.service
install -m 644 "$here/caddyfile" /etc/caddy/Caddyfile
install -d /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironment=TAGVA_HOST=%s\n' "$host" > /etc/systemd/system/caddy.service.d/tagva.conf

systemctl daemon-reload
systemctl enable tagva-api caddy
systemctl restart caddy
