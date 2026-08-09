#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=/srv/bh/ukido
readonly CANDIDATE="$ROOT/app.next"
readonly CURRENT="$ROOT/app"
readonly PREVIOUS="$ROOT/app.previous"
readonly VENV="$ROOT/.venv"
readonly SERVICE=ukido.service
readonly PRIVATE_HEALTH=http://127.0.0.1:8102/health

if [[ ! -f "$CANDIDATE/requirements.txt" || ! -f "$CANDIDATE/ops/ukido.service" ]]; then
  echo "Candidate release is incomplete" >&2
  exit 1
fi

candidate_requirements="$(sha256sum "$CANDIDATE/requirements.txt" | awk '{print $1}')"
installed_requirements="$(cat "$ROOT/.requirements.sha256" 2>/dev/null || true)"

if [[ "$candidate_requirements" != "$installed_requirements" ]]; then
  "$VENV/bin/pip" install --disable-pip-version-check -r "$CANDIDATE/requirements.txt"
  printf '%s\n' "$candidate_requirements" > "$ROOT/.requirements.sha256.next"
fi

rm -rf "$PREVIOUS"
if [[ -d "$CURRENT" ]]; then
  mv "$CURRENT" "$PREVIOUS"
fi
mv "$CANDIDATE" "$CURRENT"

mkdir -p "$HOME/.config/systemd/user"
cp "$CURRENT/ops/ukido.service" "$HOME/.config/systemd/user/ukido.service"
systemctl --user daemon-reload

if ! systemctl --user restart "$SERVICE"; then
  health_ok=false
else
  health_ok=false
  for _ in {1..15}; do
    if curl --fail --silent --show-error "$PRIVATE_HEALTH" >/dev/null; then
      health_ok=true
      break
    fi
    sleep 2
  done
fi

if [[ "$health_ok" != true ]]; then
  echo "New release failed its private health check; restoring previous release" >&2
  systemctl --user stop "$SERVICE" || true
  rm -rf "$CURRENT"
  if [[ -d "$PREVIOUS" ]]; then
    mv "$PREVIOUS" "$CURRENT"
    cp "$CURRENT/ops/ukido.service" "$HOME/.config/systemd/user/ukido.service"
    systemctl --user daemon-reload
    systemctl --user start "$SERVICE"
  fi
  rm -f "$ROOT/.requirements.sha256.next"
  exit 1
fi

if [[ -f "$ROOT/.requirements.sha256.next" ]]; then
  mv "$ROOT/.requirements.sha256.next" "$ROOT/.requirements.sha256"
fi

printf '%s\n' "${1:-unknown}" > "$ROOT/DEPLOYED_COMMIT"
systemctl --user is-active --quiet "$SERVICE"
curl --fail --silent --show-error "$PRIVATE_HEALTH"
