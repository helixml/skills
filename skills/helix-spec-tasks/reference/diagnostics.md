# Diagnostics and troubleshooting

## Contents
- Tests and benchmarks
- Troubleshooting

## Tests and benchmarks

```bash
helix spectask test --session ses_01xxx --all --json    # --mcp --desktop --chat individually
helix spectask e2e --project prj_01xxx --agent app_01yyy --prompt "List files" --cleanup
helix spectask benchmark ses_01xxx --duration 30        # video FPS under load
helix spectask latency ses_01xxx                        # key-to-eyeball input latency
helix spectask stream ses_01xxx --duration 30 -v        # raw H.264/HEVC/AV1 frame stats
```

`spectask e2e` is the fastest end-to-end confidence check: it creates a task, boots the sandbox,
cancels a live turn, sends a follow-up, screenshots, and exercises the session MCP tools.

When benchmarking video, never measure on a static desktop — it idles at ~10 FPS by design.
Expected: static ≈10, terminal activity 15–35, `vkcube` 55–60.

## Troubleshooting

| Symptom | What it means |
|---|---|
| `start` seems to hang or times out | Normal — the task was created; the sandbox is still provisioning. Check `helix spectask get spt_01xxx`. |
| `task … has no session yet` | The task was created but never started. `helix spectask start spt_01xxx`. |
| **No task on the board ever gets a sandbox** | Infrastructure, not the task. Almost always no sandbox node registered: `helix api /sandboxes` returning `[]` confirms it. See [helix-deploy](../../helix-deploy/SKILL.md). |
| Sandboxes stop being granted after a while | The fleet is at capacity. Compare `active_sandboxes` against `max_sandboxes` in `helix api /sandboxes` — read the API's reported value, not the node's own `MAX_SANDBOXES`. |
| Cards sit in `backlog` and never start on their own | `auto_start_backlog_tasks` defaults to **false**. Without it the orchestrator never pulls from backlog — start them explicitly, or set it in the project YAML. |
| Screenshot 503s | The container is up but RevDial hasn't connected yet. Wait and retry before assuming it's broken. |
| Task sits in `spec_review` forever | It's waiting on a human. `helix spectask approve spt_01xxx`. |
| Task sits queued with `⏳` | A WIP limit or a dependency. Raise the limit in the project YAML or finish the blocker. |
