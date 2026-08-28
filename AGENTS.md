# Ukido — project rules

## Start here

- This directory is the Git root. Canonical repository: `shao3d/Ukido_DynContInj`, branch `main`.
- Development happens on Andrey's Mac. The Beyond Horizon VPS is production only: do not edit code or run AI agents there.
- At the start of a session, inspect Git status, remotes, branch and upstream yourself. Do not ask Andrey to run routine Git checks.
- Read the relevant project files before editing. For runtime or deployment work, also read `docs/deployment-beyondhorizon.md`.

## Safety and scope

- Never print, copy or commit secrets, `.env` values, customer data or persistent conversation state.
- Keep changes inside the requested scope. Do not change tests, fixtures or runtime behavior merely to make checks pass.
- Do not edit `/srv/bh/ukido/app` manually. It is deployment output, not a development checkout.
- Production secrets and persistent state must remain outside releases in `/srv/bh/ukido/.env.production` and `/srv/bh/ukido/data/persistent_states`.
- Direct SSH deployment is emergency recovery only.

## Checks

- Normal offline check: `python3 -m pytest -q`.
- Run the closest relevant tests after code changes. Live scripts that need real APIs are not routine checks and must not expose credentials.
- Deployment gates are defined by `.github/workflows/tests.yml` and `ops/activate-release.sh`; do not weaken them.

## Release

- A push to `main` deploys production. After pushing, wait for GitHub Actions and verify the private and public health endpoints.

## Production map

- URL: `https://ukido.beyondhorizon.dev`.
- SSH alias: `sasha-visual`.
- Service: user-scoped `ukido.service`.
- Runtime: `/srv/bh/ukido/app`, listening on `127.0.0.1:8102`.
- Deployment: push to `main` -> tests and Docker build -> candidate release -> activation and health checks.
- A failed private health check automatically restores the previous application release.

## Shared VPS coordination

- Routine application releases use GitHub Actions and need no Telegram message.
- Read the LaneHub feed before host-level work. Use the shared Telegram group only for administrator action, outage risk, or changes to shared DNS, proxy, certificate, port, `sudo` or material resource use.
