# Ukido deployment on Beyond Horizon

## Runtime contract

- Public URL: `https://ukido.beyondhorizon.dev`
- Local listener: `127.0.0.1:8102`
- Application directory: `/srv/bh/ukido/app`
- Virtual environment: `/srv/bh/ukido/.venv`
- Persistent conversation state: `/srv/bh/ukido/data/persistent_states`
- Secrets: `/srv/bh/ukido/.env.production` with mode `600`
- Service: user-scoped `ukido.service`
- Apache and Let's Encrypt are managed by the Beyond Horizon administrator.
  Do not run `sudo bh-cert ukido` for this reverse-proxy deployment.

Railway remains the rollback target until the public HTTPS, SSE and HubSpot
smoke checks pass on Beyond Horizon.

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

If `CPUQuota=50%` is not accepted in the user-scoped unit, contact the Beyond
Horizon administrator so the CPU controller can be delegated. Do not remove
the memory limits to hide a startup problem.

## Private smoke check and proxy handoff

Before asking the administrator to enable the public reverse proxy:

```bash
curl -sS http://127.0.0.1:8102/health
journalctl --user -u ukido.service -n 100 --no-pager
```

The expected health response has `"status":"healthy"`. The SSE response uses
an explicit 15-second comment heartbeat so Apache and client proxies do not
close an idle stream.

After the private health check succeeds, ask the administrator to configure
Apache and HTTPS for `ukido.beyondhorizon.dev -> 127.0.0.1:8102`.

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
