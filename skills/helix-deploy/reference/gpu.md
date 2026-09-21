# GPU: what actually needs one

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

Check what a node reports, and what the deployment can therefore run:

```bash
helix api /sandboxes | jq -r '.[] | "\(.id) gpu=\(.gpu_vendor) render=\(.render_node) status=\(.status)"'
helix sandbox runtimes          # marks desktop runtimes unavailable when no host can stream
```

On a deployment with no render-capable host, `helix sandbox runtimes` says so, and asking for a
desktop runtime — via `helix sandbox create --runtime ubuntu-desktop` or a spec task pinned with
`--runtime ubuntu-desktop` — is rejected immediately rather than failing at placement.

`install.sh --code` is documented as requiring a GPU, and the sandbox installer prints
`Warning: No GPU detected. Sandbox may not work correctly.` before setting `GPU_VENDOR=none`.
For a GPU-less host use `code-software` in the dev stack (software rendering via `x264enc`) and
expect low frame rates; the desktop path is not the reason to run Helix on such a host.

## Old patterns

<details>
<summary>Before helixml/helix#3035: a render node was required even for headless work</summary>

A CPU-only node reporting `gpu_vendor: "none"` / `render_node: "SOFTWARE"` was skipped by
placement for *headless* work too, because one predicate gated both. The symptom is a node
that shows `status: online` while nothing ever lands on it and every sandbox fails to place.
On those binaries a sandbox node needs a render node whatever the workload.

</details>
