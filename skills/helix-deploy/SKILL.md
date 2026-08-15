---
name: helix-deploy
description: Install, configure, upgrade and debug a Helix deployment — control plane via Docker Compose or the helix-controlplane Helm chart, and the sandbox node (Hydra container runner) that actually runs spec-task desktops and sandboxes. Covers install.sh flags, Hydra per-session Docker isolation and its host requirements, runtime configuration, LLM/GPU setup, health checks, logs, database access, and a symptom-to-cause troubleshooting table. Use when the user wants to install or self-host Helix, deploy to Kubernetes, set up a sandbox/Hydra runner, upgrade, or debug a control plane, sandbox or agent desktop that isn't working.
---

# Installing and debugging Helix

A Helix deployment is two pieces:

1. **Control plane** — API, frontend, Postgres, vectorchord-kodit (RAG), searxng, chrome.
   Runs from Docker Compose or the `helix-controlplane` Helm chart.
2. **Sandbox node** — one privileged container per host running **Hydra**, the container
   runner that spawns every agent desktop and every user sandbox. Without it, spec tasks are
   created but never get a sandbox.

GPU **runners** are a third, optional piece — only needed if you want Helix to serve models
itself instead of calling an OpenAI-compatible API.

**Do you need a GPU?** Only for streamed agent *desktops*. See
[GPU: what actually needs one](#gpu-what-actually-needs-one) before buying hardware.

Once it's up, drive it with [helix-cli](../helix-cli/SKILL.md); prove it works with
[helix-e2e](../helix-e2e/SKILL.md).

## Install: control plane

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

## Install: sandbox node (Hydra)

This is the piece people forget, and the reason spec tasks sit forever with
`sandbox_state: absent`.

```bash
# same machine as the control plane, with streamed desktops (needs a GPU)
sudo ./install.sh --controlplane --sandbox --code \
  --api-host https://helix.example.com --runner-token "$RUNNER_TOKEN"

# no GPU on this host: drop --code and stay on headless runtimes
sudo ./install.sh --controlplane --sandbox \
  --api-host https://helix.example.com --runner-token "$RUNNER_TOKEN"

# dedicated GPU box joining an existing control plane
sudo ./install.sh --sandbox \
  --api-host https://helix.example.com --runner-token "$RUNNER_TOKEN"
```

The installer detects the GPU (NVIDIA / AMD / Intel / AWS Neuron / none), installs the NVIDIA
container runtime if needed, and writes `$INSTALL_DIR/sandbox.sh` — a plain `docker run` of
`ghcr.io/helixml/helix-sandbox:<tag>` that you re-run to restart or upgrade the node.

What that container gets, and why:

| Setting | Why |
|---|---|
| `--privileged` | Docker-in-Docker. Non-negotiable. |
| `--network helix_default` | Reaches the API as `http://api:8080` when co-located |
| `HYDRA_ENABLED=true` | Always on in production |
| `HYDRA_PRIVILEGED_MODE_ENABLED` | From `--privileged-docker`; **off** by default |
| `RUNNER_TOKEN` | Must match the control plane exactly |
| `SANDBOX_INSTANCE_ID` | `$(hostname)` — how the node identifies itself |
| `MAX_SANDBOXES` | Concurrent desktops on this host (installer writes 10) |
| `-v sandbox-storage:/var/lib/docker` | Nested dockerd image layers |
| `-v hydra-storage:/hydra-data` | Per-session dockerd data + shared BuildKit cache |
| `-v sandbox-data:/data` | Session workspaces |
| `-v /var/run/sandbox:/var/run/sandbox` | Socket the API shares with the node |
| `--device /dev/uinput --device /dev/uhid` + cgroup rules `c 13:*`, `c 226:*` | Virtual HID and DRI for the streamed desktop |

Host prerequisites the installer handles for you — replicate them if you deploy by hand:

- `uhid` kernel module loaded and persisted in `/etc/modules-load.d/helix.conf` (with `--code`).
- inotify limits raised to `fs.inotify.max_user_watches=1048576`,
  `fs.inotify.max_user_instances=1024` in `/etc/sysctl.d/99-helix-inotify.conf`. Zed burns
  thousands of watches per instance; the defaults run out after a couple of desktops.
- `/hydra-data` on a **real filesystem, not an overlay** — Docker's overlay2 cannot mount on top
  of overlay, so a bind mount into an overlay directory makes every nested dockerd fail to start.

## How Hydra works

Hydra gives each agent session its own Docker daemon, so two tasks on the same host cannot see
or reach each other's containers.

```
helix API ──RevDial──▶ hydra (in helix-sandbox)
                          │  docker exec / cp / inspect
                          ▼
              per-session dockerd  /var/run/hydra/{session}/docker.sock
                          │  own bridge hydra{N} → 10.200.N.0/24
                          │  own DNS server on the bridge gateway
                          ▼
              desktop container ◀─veth pair─▶ user's containers
              eth0 = streaming net          10.200.N.x
              eth1 = 10.200.N.254
```

Consequences worth knowing:

- An agent running `docker compose up` inside its desktop starts containers on *its* isolated
  bridge, and `http://webapp:3000` resolves in that desktop's browser because Hydra runs a DNS
  server per bridge that queries that session's dockerd.
- Unknown names fall through to the sandbox's `/etc/resolv.conf`, so corporate DNS, private TLDs
  and VPN-reachable services keep working inside agent desktops.
- Session A has no route to session B's subnet. That's the isolation guarantee.

**Privileged mode (`HYDRA_PRIVILEGED_MODE_ENABLED=true`, `--privileged-docker`)** replaces all of
that with the host's own Docker socket, bind-mounted at `/var/run/host-docker.sock`. Every
session then shares one daemon and one network. It exists for Helix-in-Helix development — an
agent that needs to run Helix itself, or `k3s`, or anything else wanting a real Docker. **It
removes tenant isolation: every user can see and control every other user's containers.** Only
enable it on single-tenant or development hosts.

### GPU: what actually needs one

The GPU is for **video encoding and rendering a streamed desktop**, nothing else. Split the
question by workload:

| Workload | Needs a render node? |
|---|---|
| Control plane (API, Postgres, RAG, frontend) | No |
| Headless sandboxes (`headless-ubuntu`, `node22`, `python313`, custom images) | No — no compositor, no encoder, just a container |
| Spec tasks with `--runtime headless-ubuntu` | No |
| `ubuntu-desktop` runtime — streamed GNOME, screenshots, video | **Yes** |
| Serving models on Helix's own runners | Yes (that's a runner, not a sandbox) |

So a CPU-only box is enough to run coding agents, provided you keep them headless. You lose the
streamed desktop, `spectask screenshot`, `spectask stream` and the desktop MCP tools; the agent
itself, its repo, its shell and the whole spec-task workflow are unaffected.

**Current caveat — a CPU-only sandbox host is scheduled as if it can host nothing.** The node
reports `gpu_vendor: "none"` and `render_node: "SOFTWARE"` in its heartbeat, and
`SandboxInstance.CanHostSandbox()` excludes both, so the placement logic skips it for *headless*
work too. Symptom: the node shows `status: online` in `helix api /sandboxes` while every sandbox
and spec task fails to place. The exclusion was written to keep sandboxes off inference-only
Neuron/inf2 hosts and catches CPU-only hosts as collateral. Until that is split, a sandbox node
needs a render node even for headless workloads.

Check what a node reports:

```bash
helix api /sandboxes | jq -r '.[] | "\(.id) gpu=\(.gpu_vendor) render=\(.render_node) status=\(.status)"'
```

`install.sh --code` is documented as requiring a GPU, and the sandbox installer prints
`Warning: No GPU detected. Sandbox may not work correctly.` before setting `GPU_VENDOR=none`.
For a GPU-less host use `code-software` in the dev stack (software rendering via `x264enc`) and
expect low frame rates; the desktop path is not the reason to run Helix on such a host.

### Sandbox runtimes

The catalogue of images the Sandboxes API can start is control-plane config, not code:

| Env (on the API) | Default |
|---|---|
| `HELIX_SANDBOX_RUNTIMES` | `headless-ubuntu=ubuntu:22.04\|sleep infinity,node22=node:22-bookworm-slim\|tail -f /dev/null,python313=python:3.13-slim\|tail -f /dev/null` |
| `HELIX_SANDBOX_DEFAULT_RUNTIME` | `headless-ubuntu` |
| `HELIX_SANDBOX_ALLOW_CUSTOM_IMAGE` | `false` — set `true` to let callers pass an arbitrary `image` |

Format is `name=image[|keep-alive-command]`, comma-separated. Adding Go or Rust runtimes is a
config change, no rebuild. Spec-task desktop runtimes (`ubuntu-desktop`, `headless-ubuntu`) are
separate and versioned by the node's heartbeat.

### Hydra knobs

| Env (on the sandbox node) | Purpose |
|---|---|
| `HYDRA_ENABLED` | Per-session dockerd isolation (default true) |
| `HYDRA_PRIVILEGED_MODE_ENABLED` | Share the host Docker socket instead (see warning) |
| `MAX_SANDBOXES` | Concurrent desktops on this host |
| `HELIX_DISK_PRESSURE_PATHS` | Filesystems watched for admission control (default `/var/lib/docker,/hydra-data`) |
| `HELIX_DISK_PRESSURE_REFUSE_FREE_PCT` | Refuse new sessions below this free % (default 2.0) |
| `HELIX_DISK_PRESSURE_STOP_FREE_PCT` | Stop running sessions below this free % (default 1.0) |
| `HELIX_SANDBOX_APT_MIRROR` | Internal APT mirror for air-gapped hosts |
| `HELIX_EXPERIMENTAL_DESKTOPS` | Space-separated extra desktops to pre-pull (`sway`, `zorin`, …) |
| `GPU_VENDOR` | `nvidia` \| `amd` \| `intel` \| `neuron` \| `virtio` \| `none` |

"Sandbox refused: /var/lib/docker at 1.3% free" is disk-pressure admission control doing its job,
not a bug — free space or raise the threshold.

### Verify Hydra end to end

```bash
# 1. Is a node registered, online and heartbeating?
helix api /sandboxes | jq -r '.[] | "\(.id) \(.status) gpu=\(.gpu_vendor) active=\(.active_sandboxes)/\(.max_sandboxes) privileged=\(.privileged_mode) seen=\(.last_seen)"'

# 2. Does the API know about runtimes?
helix sandbox runtimes

# 3. The real test — API → RevDial → hydra → nested dockerd → container
export HELIX_ORG=acme          # or pass --org to every command below
helix sandbox create --name hydra-smoke --runtime headless-ubuntu --ttl 300
helix sandbox exec sbx_01xxx -- bash -lc "uname -a && cat /etc/os-release | head -2"
helix sandbox delete sbx_01xxx
```

Keep the org consistent: `--org` is resolved per command, so creating in one org and exec'ing
without `--org` gives a misleading `404 sandbox not found` rather than an authz error.

Step 3 passing means Hydra is healthy. If step 1 shows nothing, the node never connected — check
`RUNNER_TOKEN` and the node's logs for `RevDial control connection established`.

`helix spectask health` checks the **API**, active agent sessions and the MCP endpoint. It does
not check sandbox hosts — use `helix api /sandboxes` for that.

## Kubernetes

Two published charts. Do **not** install from a git clone — `Chart.yaml` is generated at release
time and a clone produces a sentinel version.

```bash
helm repo add helix https://charts.helixml.tech
helm repo update

curl -o values.yaml \
  https://raw.githubusercontent.com/helixml/helix/main/charts/helix-controlplane/values-example.yaml
# set global.serverUrl, ingress, storageClass, postgresql

helm upgrade --install helix helix/helix-controlplane -f values.yaml \
  --set image.tag=$(curl -s https://get.helixml.tech/latest.txt)

kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=helix-controlplane --timeout=300s
```

External Postgres:

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

Sandbox chart — this is the Hydra node on Kubernetes:

```bash
helm upgrade --install helix-sandbox helix/helix-sandbox \
  --set sandbox.apiUrl=http://helix-controlplane:80 \
  --set sandbox.runnerTokenExistingSecret=helix-runner-token \
  --set sandbox.maxSandboxes=10 \
  --set gpu.vendor=nvidia \
  --set hydra.enabled=true
```

Chart specifics that bite:

- `securityContext.privileged: true` is required (DinD). On OpenShift you also need the
  privileged SCC — see the `openshift:` block in `values.yaml`.
- Three PVCs are provisioned: `dockerStorage` → `/var/lib/docker` (50Gi), `hydraData` →
  `/hydra-data` (20Gi), `workspaceData` → `/data` (100Gi). `hydraData` **must** be a real volume;
  overlay-on-overlay breaks nested dockerd.
- Disk-pressure admission only watches the first two by default. To cover `/data` too:
  ```yaml
  sandbox:
    extraEnv:
      - name: HELIX_DISK_PRESSURE_PATHS
        value: "/var/lib/docker,/hydra-data,/data"
  ```
- Default probes `exec` into the nested dockerd. On AKS with cgroup v2 they fail spuriously —
  disable them (`--set probes.liveness.enabled=false`) or override via a **values file**. Using
  `--set` to add an `httpGet` merges rather than replaces and yields an invalid spec.
- `hydra.privilegedMode: true` disables tenant isolation. Dev only.
- Per-cloud starting points ship as `charts/helix-sandbox/values-{gke,eks,aks,bare-metal}.yaml`.

`scripts/kind_helm_install.sh` stands the whole thing up on kind — the cheapest rehearsal.
`USE_LOCAL_HELM_CHART=1`, `USE_EXTERNAL_POSTGRES=1` and `INSTALL_SANDBOX=1` toggle the variants.
Read `charts/helix-controlplane/UPGRADE.md` before bumping a chart version.

## Local development stack

```bash
cp .env.example-prod .env
./stack start                     # docker-compose.dev.yaml
docker compose -f docker-compose.dev.yaml ps
```

Ready means `helix-api-1`, `helix-frontend-1` and `helix-postgres-1` all `Up` and
`curl -s -o /dev/null -w '%{http_code}' http://localhost:8080` returning `200`. **Cold bring-up
takes 5–10 minutes** — connection-refused or `Restarting` early on means "still coming up". Poll;
don't conclude failure.

The dev stack's sandbox is a compose profile, unlike production:

```bash
COMPOSE_PROFILES=code-nvidia ./stack start     # or code-amd-intel / code-software / code-macos
```

```bash
./stack stop                      # STOP_POSTGRES=1 / STOP_PGVECTOR=1 for data services too
./stack up <service>
./stack rebuild <service>
./stack lint
./stack test [./path/...]
./stack psql
./stack update_openapi
./stack build-sandbox             # Hydra + DinD image
./stack build-ubuntu              # desktop image (GNOME + Zed + streaming)
./stack build-zed release         # must be `release` on ARM
./stack help
```

Hot reload: the API rebuilds on save via `air`; the frontend is Vite HMR on 8081 behind 8080.
**Hydra does not hot reload** — Air doesn't rebuild the binary that lives inside the sandbox
container:

```bash
cd api && CGO_ENABLED=0 GOOS=linux go build -o /tmp/hydra-linux ./cmd/hydra
docker cp /tmp/hydra-linux helix-sandbox-nvidia-1:/usr/local/bin/hydra
docker compose -f docker-compose.dev.yaml exec -T sandbox-nvidia pkill -TERM hydra
docker logs helix-sandbox-nvidia-1 | grep "RevDial control connection established"
```

Desktop images and the settings-sync-daemon need `./stack build-ubuntu` plus a **new** session.

Avoid `./stack start-tmux` non-interactively, and never `docker builder prune` /
`docker system prune` on a Helix dev machine — delete old image tags instead if disk is full.

## Inference backend

**A — external provider (no GPU).** Set `INFERENCE_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
in `.env` (any OpenAI-compatible endpoint), restart the api service. Or register it live:

```bash
helix provider create -n my-vllm -u https://vllm.internal/v1 -f ./key.txt -m qwen3-32b
```

**B — GPU runner.** `./install.sh --runner --api-host <url> --runner-token <tok>`, or run
`docker-compose.runner.yaml` on the GPU box. No GPU locally? Run it remotely and reverse-tunnel:
`ssh -R 8080:localhost:8080 user@gpu-box`. Confirm it appears under `/dashboard`.

## Health checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' $HELIX_URL      # 200 = up
helix version
helix organization list                                   # auth works end to end
helix api /sandboxes                                      # sandbox/Hydra nodes
helix sandbox runtimes
helix spectask health                                     # API + agent sessions + MCP
docker compose ps                                         # or: kubectl get pods
docker ps | grep helix-sandbox
```

## Logs

```bash
docker compose logs --tail 100 api | grep -iE "error|failed|panic"
docker logs -f helix-sandbox                              # production sandbox node
docker logs helix-sandbox 2>&1 | grep -iE "revdial|hydra|dockerd"

# the per-session desktop containers live inside the sandbox's nested docker
docker exec helix-sandbox docker ps --format "{{.Names}}\t{{.Image}}"
docker exec helix-sandbox docker logs <container> 2>&1 | tail -100

# hydra itself, and the per-session dockerd sockets it hands out
docker exec helix-sandbox ps aux | grep -E "hydra|dockerd"
docker exec helix-sandbox ls -la /var/run/hydra/active/
docker logs helix-sandbox 2>&1 | grep "RevDial control connection established"

# kubernetes
kubectl logs -l app.kubernetes.io/name=helix-controlplane --tail=200
kubectl logs -l app.kubernetes.io/name=helix-sandbox --tail=200
```

In the dev stack the sandbox service is `sandbox-nvidia` (Linux GPU), `sandbox` (Linux no GPU) or
`sandbox-macos`; in production it's a plain container named `helix-sandbox`.

Reading the output: `hydra --socket /var/run/hydra/hydra.sock --socket-dir /var/run/hydra/active
--data-dir /hydra-data` is the runner itself. One `dockerd` on `/var/run/docker.sock` is the
node's own nested daemon; additional `[INNER-DOCKERD]` processes are per-session daemons. In
isolation mode each live session also has a socket under `/var/run/hydra/active/` — **in
privileged mode that directory stays empty**, because sessions share the host daemon instead.
Desktop containers are named `ubuntu-external-<session>` or `headless-external-<session>`.

## Database

```bash
docker exec helix-postgres-1 psql -U postgres -d postgres -c "SELECT count(*) FROM users;"
docker exec helix-postgres-1 psql -U postgres -d postgres -c \
  "SELECT id, name, status FROM spec_tasks ORDER BY created_at DESC LIMIT 10;"
```

Database `postgres`, user `postgres`. Git repositories live at `/filestore/git-repositories/`
inside the API container. Order spec tasks by `created_at` — there is no `created` column.

Treat direct SQL as read-only diagnostics; mutate through the API so orchestrator state stays
consistent.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `localhost:8080` refuses connections right after start | Still booting. Poll for several minutes. |
| API restarting in a loop | Postgres not ready or wrong credentials — `docker compose logs api`. |
| Login redirects somewhere broken | `SERVER_URL` / `KEYCLOAK_FRONTEND_URL` don't match how you reach it. |
| `401` on every CLI call | Runner token instead of a user `hl-` key. |
| **Spec task never gets a sandbox** | No sandbox node. `helix api /sandboxes` — empty means none registered. |
| Node `online` but nothing ever places on it | Check `gpu_vendor` / `render_node` — `none`/`SOFTWARE` is currently excluded from placement even for headless work. |
| Node registered but `status` not `online` | Heartbeat stopped; check `docker logs helix-sandbox`. |
| Node never appears | `RUNNER_TOKEN` mismatch, or it can't reach `HELIX_API_URL`. |
| `sandbox create` hangs then fails | Nested dockerd not up. `docker exec helix-sandbox docker info`. |
| Nested dockerd won't start | `/hydra-data` is on an overlay filesystem — give it a real volume. |
| "refused: /var/lib/docker at N% free" | Disk-pressure admission control. Free space or raise the threshold. |
| Agent's `docker compose up` works but the browser can't reach the service | Desktop not bridged to the Hydra network — check hydra logs for veth/bridge errors. |
| Container names don't resolve inside a desktop | Hydra's per-bridge DNS server isn't answering; check hydra logs. |
| Users can see each other's containers | `HYDRA_PRIVILEGED_MODE_ENABLED=true`. Turn it off for multi-tenant. |
| Desktop dies after a few sessions | inotify limits — raise `max_user_watches` / `max_user_instances`. |
| Screenshots 503 | Container up, RevDial not connected yet. Retry before treating it as broken. |
| Video stream black or 0 FPS | `GPU_VENDOR` and the compose profile disagree; use software rendering if there's no GPU. |
| No models to select | No provider — set the API keys or `helix provider create`. |
| Upgrade changed nothing | `docker compose restart` doesn't reload `.env`/images; use `pull` + `up -d`. |
| Helm chart has a sentinel version | Installed from a clone. Use the published repo. |
| Sandbox pod CrashLoopBackOff on AKS | Default exec probes vs cgroup v2 — disable probes or override in a values file. |
