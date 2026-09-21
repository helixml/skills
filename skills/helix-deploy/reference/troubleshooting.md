# Deployment troubleshooting

| Symptom | Cause and fix |
|---|---|
| `localhost:8080` refuses connections right after start | Still booting. Poll for several minutes. |
| API restarting in a loop | Postgres not ready or wrong credentials — `docker compose logs api`. |
| Login redirects somewhere broken | `SERVER_URL` / `KEYCLOAK_FRONTEND_URL` don't match how you reach it. |
| `401` on every CLI call | Runner token instead of a user `hl-` key. |
| **Spec task never gets a sandbox** | No sandbox node. `helix api /sandboxes` — empty means none registered. |
| Node `online` but nothing ever places on it | Check `gpu_vendor` / `render_node`. Before #3035, `none`/`SOFTWARE` was excluded from placement even for headless work. |
| `no sandbox host with a display/render node` | Working as intended on a CPU-only fleet — use a headless runtime, or add a host with a GPU. |
| Node registered but `status` not `online` | Heartbeat stopped; check `docker logs helix-sandbox`. |
| Node never appears | `RUNNER_TOKEN` mismatch, or it can't reach `HELIX_API_URL`. |
| `sandbox create` hangs then fails | Nested dockerd not up. `docker exec helix-sandbox docker info`. |
| Node healthy but builds crawl and disk fills | Nested dockerd fell back to `vfs` because `/hydra-data` is on overlay. Check `docker info \| grep "Storage Driver"` — it will be *running*, so liveness tells you nothing. |
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

Deeper detail per area: [controlplane.md](controlplane.md), [sandbox-node.md](sandbox-node.md),
[hydra.md](hydra.md), [gpu.md](gpu.md), [kubernetes.md](kubernetes.md),
[diagnostics.md](diagnostics.md) for the log and database commands behind each row.
