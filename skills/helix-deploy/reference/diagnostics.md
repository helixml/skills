# Diagnostics: health, logs, database

## Contents
- Health checks
- Logs
- Database

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

Credentials differ by install method: Docker Compose uses database `postgres`, user `postgres`;
the **Helm chart uses database `helix`, user `helix`** (`psql -U postgres` there fails with
`FATAL: role "postgres" does not exist`). Git repositories live at `/filestore/git-repositories/`
inside the API container. Order spec tasks by `created_at` — there is no `created` column.

Treat direct SQL as read-only diagnostics; mutate through the API so orchestrator state stays
consistent.

