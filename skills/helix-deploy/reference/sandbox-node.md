# Sandbox node (Hydra): install and verify

## Contents
- Install
- What the container gets, and why
- Host prerequisites
- Verify end to end

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
| `-v /run/udev:/run/udev:rw` | Device enumeration; the Helm chart mounts it too and the pod won't start without it |
| `--restart=always` | The node comes back with the host |
| `SANDBOX_DATA_PATH`, `XDG_RUNTIME_DIR`, `HELIX_FRAME_EXPORT_PORT` | Set by the generated script; rarely changed |

`MAX_SANDBOXES` is what the node is *told*; the capacity the API reports back can differ (a node
started with `MAX_SANDBOXES=10` reported `"max_sandboxes": 20`). Read the reported value from
`helix api /sandboxes`, not from your own env.

Host prerequisites the installer handles for you — replicate them if you deploy by hand:

- `uhid` kernel module loaded and persisted in `/etc/modules-load.d/helix.conf` (with `--code`).
  This is a **host** operation. Running it inside a container fails with
  `FATAL: Module uhid not found in directory /lib/modules/<kernel>` because there is no
  `/lib/modules` tree there — load it on the host, then pass the device in.
- inotify limits raised to `fs.inotify.max_user_watches=1048576`,
  `fs.inotify.max_user_instances=1024` in `/etc/sysctl.d/99-helix-inotify.conf`. Zed burns
  thousands of watches per instance; the defaults run out after a couple of desktops. (The
  sandbox image's own init sets a lower 524288 — the installer's host-level value is the one
  that matters.)
- `/hydra-data` on a **real filesystem, not an overlay**. Docker's overlay2 cannot mount on top of
  overlay — but the failure is silent, not loud: the nested daemon logs
  `failed to mount overlay: invalid argument`, falls back to the `vfs` storage driver, and then
  reports `Daemon has completed initialization`. It *starts*. You get a node that looks healthy
  while burning disk at a multiple of normal and building at a fraction of normal speed. Liveness
  is the wrong check:
  ```bash
  docker exec helix-sandbox docker info | grep "Storage Driver"   # want overlay2, not vfs
  ```

## Verify end to end

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

Read the outcomes as three cases, not two:

- **Step 1 empty** (literal `[]`, exit 0 — it exits 0 whether or not a node exists, so
  `if helix api /sandboxes; then` always passes; test the payload, e.g.
  `[ "$(helix api /sandboxes | jq 'length')" -gt 0 ]`): no node
  registered. Check `RUNNER_TOKEN` and the node's logs for `RevDial control connection
  established`. Also just wait: a fresh node pre-pulls the multi-GB desktop image before hydra
  starts, which took ~10 minutes in one measured run, and the pod reads `READY 1/1` throughout
  because the probe only checks dockerd.
- **Step 3 passes**: Hydra is healthy end to end.
- **Step 1 shows an `online` node but step 3 fails** — the case people misdiagnose. The error
  reads `no available sandbox host with the requested runtime`, which sounds like "no node" and
  sends you back to the token you just verified. It usually means the node has not got the
  runtime's *image*: the catalogue in `HELIX_SANDBOX_RUNTIMES` is control-plane config, and what
  the node pulled is independent of it. A node that pre-pulled only desktop images has no
  `ubuntu:22.04`, `node:22-bookworm-slim` or `python:3.13-slim`. Check with:
  ```bash
  docker exec helix-sandbox docker images
  ```

`helix spectask health` checks the **API**, active agent sessions and the MCP endpoint. It does
not check sandbox hosts — use `helix api /sandboxes` for that.

On 2.12.3 its API line is a **false negative**: it probes `/api/v1/health`, which 404s, so it
prints `⚠️ Status: 404` against a perfectly healthy control plane — and exits 0 regardless. The
paths that do answer are `/health`, `/healthz` and `/api/health`. Trust
`curl -s -o /dev/null -w '%{http_code}' $HELIX_URL/health` over that line.

