---
name: helix-deploy
description: Install, configure, upgrade and debug a Helix deployment — Docker Compose via the quickstart installer, Kubernetes via the helix-controlplane and helix-sandbox Helm charts, and the local dev stack driven by ./stack. Covers LLM provider and GPU/sandbox configuration, health checks, container and API logs, database access, and a symptom-to-cause troubleshooting table. Use when the user wants to install or self-host Helix, deploy it to Kubernetes, upgrade it, or debug a Helix control plane, sandbox or runner that isn't working.
---

# Installing and debugging Helix

Helix runs as a **control plane** (API + frontend + Postgres + supporting services) plus, for
coding agents, a **sandbox** host that runs each agent's isolated desktop container. GPU
**runners** are optional — you can point Helix at any OpenAI-compatible API instead.

Once it's up, drive it with [helix-cli](../helix-cli/SKILL.md); to prove it works end to end, use
[helix-e2e](../helix-e2e/SKILL.md).

## Docker Compose (quickest)

```bash
curl -sL -O https://get.helixml.tech/install.sh
chmod +x install.sh
sudo ./install.sh          # --help for DNS/TLS options
```

The installer prompts before changing anything and serves the dashboard on
`http://localhost:8080` by default. The first registered account is promoted to admin.

Manual Compose install:

```bash
git clone https://github.com/helixml/helix.git && cd helix
cp .env.example-prod .env
# edit .env: KEYCLOAK_ADMIN_PASSWORD, POSTGRES_ADMIN_PASSWORD, RUNNER_TOKEN, SERVER_URL
docker compose up -d
docker compose ps
```

Settings in `.env` that matter most:

| Variable | Purpose |
|---|---|
| `SERVER_URL` | Public URL of the deployment — must match how users reach it, or OAuth and links break |
| `KEYCLOAK_FRONTEND_URL` | `${SERVER_URL}/auth/` |
| `POSTGRES_ADMIN_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD` | Set real values |
| `RUNNER_TOKEN` | Shared secret between control plane and runners/sandboxes. **Never leave it as `oh-hallo-insecure-token` in production.** |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `INFERENCE_PROVIDER` | Hosted inference |
| `DYNAMIC_PROVIDERS` | Bulk-register providers: `groq:gsk_xxx:https://api.groq.com/openai/v1,…` |
| `GPU_VENDOR` | `nvidia` \| `amd` \| `intel` \| `none` — picks the video encoder |
| `COMPOSE_PROFILES` | `code` (NVIDIA), `code-amd`, `code-software` — **must match `GPU_VENDOR`** |
| `HELIX_VERSION` | Pin the image tag; latest is at `https://get.helixml.tech/latest.txt` |
| `API_PORT` | Host port for the API (default 8080) |

Upgrade:

```bash
# in .env: HELIX_VERSION=2.12.3
docker compose pull && docker compose up -d
```

`docker compose restart` does **not** pick up `.env` or image changes — you need `pull` + `up -d`
(or `down` + `up -d`). Snapshot or `pg_dump` the database before a version bump.

## Kubernetes

Two published charts. Do **not** install from a git clone — `Chart.yaml` is generated at release
time and a clone produces a sentinel version.

```bash
helm repo add helix https://charts.helixml.tech
helm repo update

curl -o values.yaml \
  https://raw.githubusercontent.com/helixml/helix/main/charts/helix-controlplane/values-example.yaml
# set global.serverUrl to your public URL; configure ingress, storageClass, postgresql

helm upgrade --install helix helix/helix-controlplane -f values.yaml \
  --set image.tag=$(curl -s https://get.helixml.tech/latest.txt)

kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=helix-controlplane --timeout=300s
kubectl port-forward svc/helix-controlplane 8080:80
```

External Postgres instead of the bundled one:

```bash
helm upgrade --install helix helix/helix-controlplane -f values.yaml \
  --set postgresql.enabled=false \
  --set postgresql.external.existingSecret=my-pg-secret \
  --set postgresql.external.existingSecretHostKey=host \
  --set postgresql.external.existingSecretPortKey=port \
  --set postgresql.external.existingSecretUserKey=user \
  --set postgresql.external.existingSecretDatabaseKey=dbname \
  --set postgresql.external.existingSecretPasswordKey=password
```

Sandbox (needed for spec tasks / coding agents):

```bash
helm upgrade --install helix-sandbox helix/helix-sandbox \
  --set sandbox.apiUrl=http://helix-controlplane:80 \
  --set sandbox.runnerToken=$RUNNER_TOKEN \
  --set gpu.vendor=nvidia
```

Per-cloud starting points live in the repo as `charts/helix-sandbox/values-{gke,eks,aks,bare-metal}.yaml`.

`scripts/kind_helm_install.sh` in the helix repo stands the whole thing up on a local kind
cluster — the fastest way to rehearse a Kubernetes install. `USE_LOCAL_HELM_CHART=1`,
`USE_EXTERNAL_POSTGRES=1` and `INSTALL_SANDBOX=1` toggle the variants. Check
`charts/helix-controlplane/UPGRADE.md` before bumping a chart version.

## Local development stack

From a checkout, for hacking on Helix itself:

```bash
cp .env.example-prod .env
./stack start                     # docker-compose.dev.yaml: api, frontend, postgres, kodit, chrome, searxng
docker compose -f docker-compose.dev.yaml ps
```

Ready means `helix-api-1`, `helix-frontend-1` and `helix-postgres-1` all `Up` and
`curl -s -o /dev/null -w '%{http_code}' http://localhost:8080` returning `200`. **Full bring-up
can take 5–10 minutes** on a cold cache — connection-refused or `Restarting` early on means "still
coming up", not "broken". Poll rather than concluding it failed.

```bash
./stack stop                      # STOP_POSTGRES=1 / STOP_PGVECTOR=1 to stop data services too
./stack up <service>
./stack rebuild <service>
./stack lint
./stack test [./path/...]
./stack psql
./stack update_openapi
./stack build-sandbox             # Hydra + DinD image
./stack build-ubuntu              # desktop image (GNOME + Zed + streaming)
./stack build-zed release         # Zed binary; must be `release` on ARM
./stack help
```

Hot reload: the API rebuilds on save via `air`; the frontend is Vite HMR on port 8081 proxied
behind 8080. The settings-sync-daemon and desktop images do **not** hot reload — they need
`./stack build-ubuntu` and a fresh session.

Avoid `./stack start-tmux` in non-interactive contexts (it needs a terminal), and never
`docker builder prune` / `docker system prune` on a Helix dev machine — it destroys hours of
build cache. If disk is full, delete old image tags instead.

## Inference backend

Pick one:

**A — external provider (no GPU).** Set `INFERENCE_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
in `.env` (any OpenAI-compatible endpoint: OpenAI, Together, a self-hosted vLLM), then restart
the api service. Or register it after the fact:

```bash
helix provider create -n my-vllm -u https://vllm.internal/v1 -f ./key.txt -m qwen3-32b
```

**B — GPU runner.** Run `docker-compose.runner.yaml` on the GPU box with `API_HOST` pointing at
the control plane and a `RUNNER_TOKEN` that matches it. No GPU locally? Run the runner remotely
and reverse-tunnel it: `ssh -R 8080:localhost:8080 user@gpu-box`. Confirm it appears under
`/dashboard`.

## Health checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' $HELIX_URL      # 200 = up
helix version
helix organization list                                   # auth works end to end
helix spectask health                                     # sandbox + container status
docker compose ps                                         # or: kubectl get pods
docker ps | grep helix-sandbox
```

## Logs

```bash
docker compose logs --tail 100 api | grep -iE "error|failed|panic"
docker compose -f docker-compose.dev.yaml logs --tail 50 frontend | grep -i error
docker compose logs --tail 100 sandbox-nvidia 2>&1 | grep -iE "error|failed"

# inside the sandbox: the per-session desktop containers
docker compose exec -T sandbox-nvidia docker ps --format "{{.Names}}" | grep ubuntu-external
docker compose exec -T sandbox-nvidia docker logs <container> 2>&1 | tail -100

# kubernetes
kubectl logs -l app.kubernetes.io/name=helix-controlplane --tail=200
kubectl describe pod -l app.kubernetes.io/name=helix-controlplane
```

Sandbox service names differ by hardware: `sandbox-nvidia` (Linux GPU), `sandbox` (Linux no GPU),
`sandbox-macos`.

## Database

```bash
docker exec helix-postgres-1 psql -U postgres -d postgres -c "SELECT count(*) FROM users;"
docker exec helix-postgres-1 psql -U postgres -d postgres -c \
  "SELECT id, name, status FROM spec_tasks ORDER BY created_at DESC LIMIT 10;"
```

Database `postgres`, user `postgres`. Git repositories live at `/filestore/git-repositories/`
inside the API container. Order spec tasks by `created_at` (there is no `created` column).

Treat direct SQL as read-only diagnostics — mutate through the API so orchestrator state stays
consistent.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `localhost:8080` refuses connections right after start | Still booting. Poll for several minutes before concluding failure. |
| API restarting in a loop | Postgres not ready or wrong credentials — check `docker compose logs api` for connection errors. |
| Login redirects to a broken URL | `SERVER_URL` / `KEYCLOAK_FRONTEND_URL` don't match how you reach the deployment. |
| `401` from every CLI call | Using the runner token instead of a user `hl-` key. |
| Spec task never gets a sandbox | Sandbox container not running, or `RUNNER_TOKEN` differs between control plane and sandbox. |
| Screenshots 503 | Container is up but RevDial hasn't connected yet — retry before treating it as broken. |
| Video stream black or 0 FPS | `GPU_VENDOR` and `COMPOSE_PROFILES` disagree; use `code-software` if there's no GPU. |
| No models to select | No provider configured — set `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` or `helix provider create`. |
| Upgrade didn't change anything | `docker compose restart` doesn't reload `.env`/images; use `pull` + `up -d`. |
| Helm install has a sentinel version | You installed from a clone. Use `helm repo add helix https://charts.helixml.tech`. |
| Disk full on a dev box | Delete old image tags. Do **not** prune the build cache. |
