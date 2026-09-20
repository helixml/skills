# How Hydra works

## Contents
- Per-session Docker isolation
- Privileged mode and what it costs
- Sandbox runtimes
- Hydra knobs

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

## Sandbox runtimes

The catalogue of images the Sandboxes API can start is control-plane config, not code:

| Env (on the API) | Default |
|---|---|
| `HELIX_SANDBOX_RUNTIMES` | `headless-ubuntu=ubuntu:22.04\|sleep infinity,node22=node:22-bookworm-slim\|tail -f /dev/null,python313=python:3.13-slim\|tail -f /dev/null` |
| `HELIX_SANDBOX_DEFAULT_RUNTIME` | `headless-ubuntu` |
| `HELIX_SANDBOX_ALLOW_CUSTOM_IMAGE` | `false` — set `true` to let callers pass an arbitrary `image` |

Format is `name=image[|keep-alive-command]`, comma-separated. Adding Go or Rust runtimes is a
config change, no rebuild. Spec-task desktop runtimes (`ubuntu-desktop`, `headless-ubuntu`) are
separate and versioned by the node's heartbeat.

## Hydra knobs

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

