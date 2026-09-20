---
name: helix-deploy
description: Use when installing, self-hosting or upgrading Helix, deploying it to Kubernetes, or setting up a sandbox/Hydra runner node; and when a deployment misbehaves — spec tasks stuck without a sandbox, a node online but never placed on, desktops black or dying, builds crawling, or pods in CrashLoopBackOff.
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

## Start here

| You want to | Read |
|---|---|
| Install or upgrade the control plane | [reference/controlplane.md](reference/controlplane.md) |
| Install the sandbox node, or spec tasks never get a sandbox | [reference/sandbox-node.md](reference/sandbox-node.md) |
| Understand session isolation, runtimes, privileged mode | [reference/hydra.md](reference/hydra.md) |
| Decide whether you need a GPU | [reference/gpu.md](reference/gpu.md) |
| Deploy to Kubernetes | [reference/kubernetes.md](reference/kubernetes.md) |
| Run the local dev stack, or configure inference | [reference/local-dev.md](reference/local-dev.md) |
| Read health, logs, or the database | [reference/diagnostics.md](reference/diagnostics.md) |
| Match a symptom to a cause | [reference/troubleshooting.md](reference/troubleshooting.md) |

**Do you need a GPU?** Only for streamed agent *desktops*. A CPU-only box runs coding agents
fine, provided you keep them headless. Check [reference/gpu.md](reference/gpu.md) before buying
hardware.

## Quickest install

```bash
curl -sL -O https://get.helixml.tech/install.sh
chmod +x install.sh
sudo ./install.sh --controlplane --sandbox \
  --api-host https://helix.example.com --runner-token "$RUNNER_TOKEN"
```

`--sandbox` is the piece people forget, and the reason spec tasks sit forever with
`sandbox_state: absent`. Add `--code` only if this host has a GPU and you want streamed
desktops.

## Is it up?

```bash
curl -s -o /dev/null -w '%{http_code}\n' $HELIX_URL   # 200 = up
helix organization list                                # auth works end to end
helix api /sandboxes                                   # sandbox nodes; [] means none registered
```

Cold bring-up takes minutes, and a fresh sandbox node pre-pulls multi-GB images before Hydra
starts. Connection-refused or an empty node list early on means "still coming up" — poll before
concluding failure.

Once it's up, drive it with [helix-cli](../helix-cli/SKILL.md); prove the whole loop works with
[helix-e2e](../helix-e2e/SKILL.md).
