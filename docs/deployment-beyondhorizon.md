# Ukido deployment on Beyond Horizon

## Runtime contract

- Public URL: `https://ukido.beyondhorizon.dev`
- Local listener: `127.0.0.1:8102`
- Application directory: `/srv/bh/ukido/app`
- Virtual environment: `/srv/bh/ukido/.venv`
- Persistent conversation state: `/srv/bh/ukido/data/persistent_states`
- Secrets: `/srv/bh/ukido/.env.production` with mode `600`
- Service: user-scoped `ukido.service`
- Source of truth: private GitHub repository `shao3d/Ukido_DynContInj`, branch
  `main`.
- A successful push to `main` automatically deploys through
  `.github/workflows/tests.yml` after both test jobs pass.
- Apache and Let's Encrypt are provisioned by the self-service helper
  `sudo bh-proxy ukido 8102`. Do not run `sudo bh-cert ukido` for this
  reverse-proxy deployment.

Railway remains the external rollback target until Andrey explicitly approves
its removal.

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
`BH_DEPLOY_USER`, `BH_DEPLOY_KEY` and `BH_KNOWN_HOSTS`. Never print their
values or store them in repository files.

## Shared infrastructure coordination

LaneHub connects the `shao3d` lane to the shared Beyond Horizon Telegram group.
Read the current feed before host-level work, but do not use the group as a
step-by-step deploy log.

- Routine pushes, test results, candidate activation and successful deploys to
  the existing Ukido service stay in GitHub Actions and need no chat message.
- Write when administrator action is required, when there is an outage or risk
  to neighbouring services, or when shared infrastructure changes: DNS, vhost,
  port, certificate, `sudo`, or meaningful disk/CPU/RAM consumption.
- Before provisioning another `*.beyondhorizon.dev` certificate, send one
  advance line because the Let's Encrypt rate limit is shared across the
  domain.
- After relevant infrastructure work, send at most one concise final result.
  Keep commands, detailed evidence and rollback notes in this repository or the
  task tracker.

## Server preparation

```bash
mkdir -p /srv/bh/ukido/{app,public,data/persistent_states}
python3 -m venv /srv/bh/ukido/.venv
/srv/bh/ukido/.venv/bin/pip install --upgrade pip
/srv/bh/ukido/.venv/bin/pip install -r /srv/bh/ukido/app/requirements.txt
chmod 755 /srv/bh/ukido /srv/bh/ukido/public
chmod 700 /srv/bh/ukido/data /srv/bh/ukido/data/persistent_states
chmod 600 /srv/bh/ukido/.env.production
```

The environment file contains the production API credentials and runtime
settings. Never commit it or paste its values into documentation. Required
non-secret settings for this host include:

```dotenv
PORT=8102
PERSISTENCE_BASE_PATH=/srv/bh/ukido/data/persistent_states
CORS_ALLOW_ORIGINS=https://shao3d.github.io,https://ukido.beyondhorizon.dev
DETERMINISTIC_MODE=false
```

## Service installation

```bash
mkdir -p ~/.config/systemd/user
cp /srv/bh/ukido/app/ops/ukido.service ~/.config/systemd/user/ukido.service
systemctl --user daemon-reload
systemctl --user enable --now ukido.service
systemctl --user status ukido.service
```

`MemoryHigh=256M`, `MemoryMax=384M` and `TasksMax=128` are enforced by the
service cgroup. The effective CPU ceiling is enforced for all Andrey's
processes by the system-level `user-1004.slice` with `CPUQuota=50%`; the same
line in the user service is retained as documentation but is not the enforcing
control on this systemd 249 host.

## Private smoke check and proxy handoff

Before asking the administrator to enable the public reverse proxy:

```bash
curl -sS http://127.0.0.1:8102/health
journalctl --user -u ukido.service -n 100 --no-pager
```

The expected health response has `"status":"healthy"`. The SSE response uses
an explicit 15-second comment heartbeat so Apache and client proxies do not
close an idle stream.

For initial proxy provisioning or an intentional port change, run:

```bash
sudo bh-proxy ukido 8102
```

The command provisions Apache and HTTPS for
`ukido.beyondhorizon.dev -> 127.0.0.1:8102`. It is idempotent. Normal
application deployments do not need to call it again.

## Public verification

Verify all of the following before retiring Railway:

1. `https://ukido.beyondhorizon.dev/health` returns HTTP 200.
2. The web chat loads without browser console errors.
3. `/chat/stream` emits metadata, message chunks and `done` through HTTPS.
4. A trial signup reaches HubSpot without exposing credentials or contact IDs.
5. `systemctl --user status ukido.service` is healthy after an SSH logout.
6. The service returns after a controlled restart.

## Rollback

If the VPS deployment fails, keep or restore the Railway deployment at
`https://ukidoschool.up.railway.app`. Do not delete Railway variables or the
Railway service until the Beyond Horizon deployment has passed all public
checks and remained stable through the agreed observation period.
