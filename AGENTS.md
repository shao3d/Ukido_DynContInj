# Ukido Codex Notes

## Production

- Canonical repository: private GitHub repository `shao3d/Ukido_DynContInj`.
- Canonical production branch: `main`.
- Production URL: `https://ukido.beyondhorizon.dev`.
- Production host: Beyond Horizon VPS, user `andrey`.
- Runtime service: user-scoped systemd unit `ukido.service` on port `8102`.
- Production secrets live only in `/srv/bh/ukido/.env.production` on the VPS.
- Persistent conversation state lives outside releases in
  `/srv/bh/ukido/data/persistent_states`.

## Deployment contract

- A push to `main` runs tests and, only after they pass, deploys that commit through
  `.github/workflows/tests.yml`.
- The deploy uploads a candidate release, activates it, restarts `ukido.service`,
  checks the private health endpoint and then verifies the public HTTPS endpoint.
- A failed private health check restores the previous application release.
- Never print, request, edit or commit GitHub Actions secrets or production API keys.
- Do not edit `/srv/bh/ukido/app` manually during normal work. It is deployment output.
- Direct SSH deployment is emergency recovery only and requires an explicit request.
- Keep Railway available as rollback until Andrey explicitly approves its removal.

## Collaboration phrases

- `подготовь`, `покажи`, `проверь`: local changes and QA only, no commit or deploy.
- `зафиксируй`: local commit only.
- `выкатывай Ukido`, `опубликуй`, `закоммить и пушни main`: commit approved files,
  push `main`, watch GitHub Actions and verify production.
- `закоммить, но не выкатывай`: use a `work/...` branch, never `main`.

The human-facing runbook is `docs/deployment-beyondhorizon.md`.
