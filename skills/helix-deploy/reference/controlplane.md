# Control plane: install, configure, upgrade

## Contents
- Install
- Manual Compose install and `.env`
- Upgrade
- Inference backend

```bash
curl -sL -O https://get.helixml.tech/install.sh
chmod +x install.sh
sudo ./install.sh --controlplane --api-host https://helix.example.com
```

Useful flags (`./install.sh --help` for the full list):

| Flag | Effect |
|---|---|
| `--controlplane` | API + Postgres + friends in `$INSTALL_DIR` (default `~/helix`) via Docker Compose |
| `--sandbox` | Sandbox/Hydra node — see below |
| `--runner` | GPU runner container |
| `--cli` | Just the `helix` binary |
| `--code` | Enable Helix Code (agent desktops, streaming). Loads the `uhid` kernel module. Documented as needing a GPU and `--api-host` — omit it if you only want headless sandboxes |
| `--api-host <url>` | Public URL. HTTPS on Ubuntu also installs and configures Caddy |
| `--runner-token <tok>` | Shared secret joining runners/sandboxes to the control plane |
| `--privileged-docker` | Hydra privileged mode — see the warning below |
| `--openai-api-key` / `--anthropic-api-key` / `--together-api-key` | Inference credentials |
| `--vhost-tls-mode auto` + `--letsencrypt-email` | Built-in TLS for project web services and sandbox previews |
| `--helix-version <v>` / `--upgrade` | Pin or bump the version |
| `-y` | Non-interactive |

Manual Compose install:

```bash
git clone https://github.com/helixml/helix.git && cd helix
cp .env.example-prod .env
# edit: SERVER_URL, KEYCLOAK_FRONTEND_URL, POSTGRES_ADMIN_PASSWORD,
#       KEYCLOAK_ADMIN_PASSWORD, RUNNER_TOKEN, inference keys
docker compose up -d && docker compose ps
```

`.env` settings that matter most:

| Variable | Purpose |
|---|---|
| `SERVER_URL` | Public URL — must match how users reach it, or OAuth and generated links break |
| `KEYCLOAK_FRONTEND_URL` | `${SERVER_URL}/auth/` |
| `RUNNER_TOKEN` | Joins runners and sandboxes. **Never ship `oh-hallo-insecure-token`.** |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `INFERENCE_PROVIDER` | Hosted inference |
| `DYNAMIC_PROVIDERS` | Bulk-register providers: `groq:gsk_x:https://api.groq.com/openai/v1,…` |
| `HELIX_VERSION` | Image tag; latest at `https://get.helixml.tech/latest.txt` |
| `API_PORT` | Host port for the API (default 8080) |
| `HELIX_SANDBOX_RUNTIMES` | Sandbox runtime catalogue — see Hydra below |

**The production `docker-compose.yaml` deliberately has no sandbox service.** Sandbox nodes are
run standalone by `install.sh --sandbox`. `COMPOSE_PROFILES` only selects a sandbox in the *dev*
compose file, where the profiles are `code-nvidia`, `code-amd-intel`, `code-software` and
`code-macos` — the `code`/`code-amd` names in the `.env.example-prod` comments are stale.

Upgrade:

```bash
sudo ./install.sh --controlplane --upgrade --helix-version 2.12.3
# or by hand: set HELIX_VERSION in .env, then
docker compose pull && docker compose up -d
```

`docker compose restart` does **not** pick up `.env` or image changes — use `pull` + `up -d`.
Snapshot or `pg_dump` the database before a version bump.

## Inference backend

**A — external provider (no GPU).** Set `INFERENCE_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
in `.env` (any OpenAI-compatible endpoint), restart the api service. Or register it live:

```bash
helix provider create -n my-vllm -u https://vllm.internal/v1 -f ./key.txt -m qwen3-32b
```

**B — GPU runner.** `./install.sh --runner --api-host <url> --runner-token <tok>`, or run
`docker-compose.runner.yaml` on the GPU box. No GPU locally? Run it remotely and reverse-tunnel:
`ssh -R 8080:localhost:8080 user@gpu-box`. Confirm it appears under `/dashboard`.

