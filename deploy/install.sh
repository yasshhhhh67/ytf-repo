#!/bin/bash
# Install/refresh server-side pieces from the synced app folder. Run on the controller as a sudo user.
set -euo pipefail
A=/srv/ytf/app
sudo install -d -m 755 /usr/local/libexec
sudo install -m 755 -o root -g root $A/deploy/libexec/ytf-agy /usr/local/libexec/ytf-agy
sudo install -m 755 -o root -g root $A/deploy/bin/ytf /usr/local/bin/ytf
sudo install -m 755 -o root -g root $A/deploy/bin/ytf-llm-run /usr/local/bin/ytf-llm-run
sudo install -m 440 -o root -g root $A/deploy/sudoers/ytf-agy /tmp/ytf-agy.sudoers
sudo visudo -cf /tmp/ytf-agy.sudoers >/dev/null && sudo mv /tmp/ytf-agy.sudoers /etc/sudoers.d/ytf-agy
sudo -u ytf /srv/ytf/venv/bin/pip install -q --no-cache-dir -r $A/requirements.txt
(cd $A/engine && sudo -u ytf -H npm install --silent --no-fund --no-audit)
echo installed
