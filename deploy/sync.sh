#!/bin/bash
# Sync this working copy to the controller (code only; never data or secrets).
set -euo pipefail
cd "$(dirname "$0")/.."
rsync -az --delete --exclude .git --exclude node_modules --exclude __pycache__ \
  -e "ssh -i $HOME/Downloads/ssh-key-2026-10-28.key" --rsync-path="sudo -u ytf rsync" \
  ./ ubuntu@137.23.53.173:/srv/ytf/app/
