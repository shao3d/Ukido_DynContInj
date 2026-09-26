# Ukido deployment on Beyond Horizon

The `beyondhorizon.dev` name is the public brand. After the September 2026
outage of the original VPS (`vps78876`, `91.200.41.59`), the production
runtime of Ukido lives on Andrey's Oracle website VM — the same host that
serves `visual.beyondhorizon.dev` and `rnd.beyondhorizon.dev`. This runbook
describes the current deployment; the historical Beyond Horizon VPS is
retained in the last section for context only.

## Runtime contract

- Public URL: `https://ukido.beyondhorizon.dev`
- Host: OCI `oracle-marseille-micro-2`, Linux `oracle-micro-2`,
  `84.235.231.179`, region `eu-marseille-1` (1 GiB class VM)
- Admin SSH: `ubuntu@84.235.231.179` with the Mac key (`~/.ssh/id_ed25519`,
  `IdentitiesOnly=yes`, strict host-key checking). The pinned ED25519
  fingerprint is `SHA256:7AaVqarbZzzCNO6SNEgnOI3i46Q5JQ3MVl6QdpOBgps` — see
  the Infrastructure runbook `homeland-rnd-production.md`.
- CI identity: `ukido-deploy` (no sudo; owns `/srv/bh/ukido`; runs the
  user-scoped service; lingering enabled)
- Application directory: `/srv/bh/ukido/app`
- Virtual environment: `/srv/bh/ukido/.venv` (system Python 3.12)
- Persistent conversation state: `/srv/bh/ukido/data/persistent_states`
- Secrets: `/srv/bh/ukido/.env.production`, mode `600`, owner `ukido-deploy`
- Service: user-scoped `ukido.service` under `ukido-deploy`, listener
  `127.0.0.1:8102`
- Edge: Caddy vhost `ukido.beyondhorizon.dev` reverse-proxies to
  `127.0.0.1:8102` and appends `X-Forwarded-For`; per-IP rate limiting reads
  the last hop
- DNS: the `ukido` A record in the `beyondhorizon.dev` zone is managed by
  Sasha
- Source of truth: private GitHub repository `shao3d/Ukido_DynContInj`,
  branch `main`.
- A successful push to `main` automatically deploys through
  `.github/workflows/tests.yml` after both test jobs pass.

## Normal deployment

Do not edit `/srv/bh/ukido/app` manually. It is deployment output. The normal
production path is:

1. Commit the approved change.
2. Push it to `main`.
3. GitHub Actions runs Python tests and the Docker build.
4. The deploy job uploads `/srv/bh/ukido/app.next`.
5. `ops/activate-release.sh` installs dependencies only when
   `requirements.txt` changed, swaps the candidate into `/srv/bh/ukido/app`,
   restarts `ukido.service` and checks the private `/health` endpoint.
6. GitHub Actions checks the public HTTPS `/health` endpoint.

The previous application tree is retained as `/srv/bh/ukido/app.previous`.
If the private health check fails, it is restored automatically. Production
secrets and conversation state live outside all application releases and are
never uploaded by GitHub Actions.

Required GitHub Actions repository secrets are `BH_DEPLOY_HOST`,
`BH_DEPLOY_USER`, `BH_DEPLOY_KEY` and `BH_KNOWN_HOSTS`; they point at the
website VM and the `ukido-deploy` key (created 2026-09-26). Never print their
values or store them in repository files.

## Server preparation (reference)

The 2026-09-26 migration set the host up as follows; repeat only for a
disaster rebuild:

```bash
sudo useradd -m -s /bin/bash ukido-deploy
sudo mkdir -p /srv/bh/ukido/{app,app.next,data/persistent_states}
sudo chown -R ukido-deploy:ukido-deploy /srv/bh/ukido
sudo chmod 755 /srv/bh/ukido
sudo chmod 700 /srv/bh/ukido/data /srv/bh/ukido/data/persistent_states
sudo loginctl enable-linger ukido-deploy
sudo apt-get install -y python3.12-venv
sudo -u ukido-deploy python3 -m venv /srv/bh/ukido/.venv
sudo chmod 600 /srv/bh/ukido/.env.production
```

`.env.production` holds the runtime settings (`PORT=8102`,
`PERSISTENCE_BASE_PATH=/srv/bh/ukido/data/persistent_states`,
`CORS_ALLOW_ORIGINS=https://shao3d.github.io,https://ukido.beyondhorizon.dev`,
`DETERMINISTIC_MODE=false`) plus the OpenRouter and HubSpot credentials.
Never commit it or paste its values into documentation. `ADMIN_API_TOKEN` is
unset, so the admin endpoints stay disabled.

The Caddy block (with the HTTP→HTTPS redirect kept explicit for consistency
with the other sites):

```caddyfile
http://ukido.beyondhorizon.dev {
    redir https://ukido.beyondhorizon.dev{uri} 301
}

ukido.beyondhorizon.dev {
    reverse_proxy 127.0.0.1:8102
}
```

Validate with `sudo caddy validate --config /etc/caddy/Caddyfile` before
`sudo systemctl reload caddy`. A pre-migration backup is kept as
`/etc/caddy/Caddyfile.bak-ukido-migration`.

## Shared infrastructure coordination

LaneHub connects the `shao3d` lane to the shared Beyond Horizon Telegram group
(Homeland's coordination procedure). Read the current feed before host-level
work, but do not use the group as a step-by-step deploy log.

- Routine pushes, test results, candidate activation and successful deploys to
  the existing Ukido service stay in GitHub Actions and need no chat message.
- Write when administrator action is required (for Ukido: the `ukido` DNS A
  record is managed by Sasha), when there is an outage or risk to neighbouring
  services, or when shared infrastructure changes: DNS, vhost, port,
  certificate, `sudo`, or meaningful disk/CPU/RAM consumption.
- Before provisioning another `*.beyondhorizon.dev` certificate, send one
  advance line because the Let's Encrypt rate limit is shared across the
  domain.
- After relevant infrastructure work, send at most one concise final result.
  Keep commands, detailed evidence and rollback notes in this repository or the
  task tracker.

## Verification

```bash
dig +short ukido.beyondhorizon.dev A          # 84.235.231.179
curl -fsSI --max-time 15 https://ukido.beyondhorizon.dev/health
curl -sSI --max-time 15 http://ukido.beyondhorizon.dev/health   # 301 -> HTTPS
```

Expected: the IP above, HTTPS `200` with `"status":"healthy"`, HTTP `301` to
the HTTPS URL. The SSE response uses an explicit 15-second comment heartbeat
so proxies do not close an idle stream. For a full check also load the web
chat and confirm `/chat/stream` emits metadata, message chunks and `done`.

## Rollback

A failed private health check restores `/srv/bh/ukido/app.previous`
automatically. For a manual rollback, re-run the deploy workflow for the last
known-good commit. Direct SSH/rsync is an explicitly authorized emergency
procedure only. The historical Railway deployment is no longer maintained as a
rollback target for the new host.

## History: the original Beyond Horizon VPS

Ukido originally ran on the VPS `vps78876` (`91.200.41.59`, user `andrey`,
aliases `sasha-visual`/`vps-andreys`), served by Apache via
`sudo bh-proxy ukido 8102`. That host became unreachable during the
September 24, 2026 outage and has not recovered. Only the `visual` and `rnd`
websites were migrated at first; the Ukido chatbot was migrated to
`oracle-micro-2` on 2026-09-26 by the same A-record/Caddy/CI pattern. Do not
use the legacy SSH aliases as deployment targets.
