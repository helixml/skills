---
name: helix-spec-tasks
description: Start, watch, steer and stop Helix spec tasks — launch a coding agent in its own sandbox, chat with it, send prompts, read its conversation history, exec commands and copy files into its container, take screenshots, stream its desktop, and drive standalone sandboxes. Use when the user wants to run a Helix coding agent, dispatch work to a spec task, talk to a running task, debug a stuck agent, or work with Helix sandboxes.
---

# Running and steering Helix spec tasks

A spec task is a unit of work that gets its own isolated sandbox — a full Ubuntu container, with
a GNOME desktop by default, running a coding agent (Claude Code, Codex, Gemini CLI, Qwen Code,
Goose, or Zed's agent) against the project's repositories.

Read [helix-cli](../helix-cli/SKILL.md) for auth and [helix-board](../helix-board/SKILL.md) for
creating and moving the cards themselves. This skill is about the *running* task.

> **Version note.** Addressing a task by its `spt_…` id in `send`/`interact` (instead of looking
> up its session id) landed in helixml/helix#3033 — merged to main, shipping in the first release after 2.12.3. On older binaries resolve it first:
> `SES=$(helix api /spec-tasks/spt_01xxx | jq -r .planning_session_id)`.

## Identifiers

| Prefix | Thing |
|---|---|
| `prj_` | project |
| `spt_` | spec task (a card on the board) |
| `ses_` | session — the conversation + container behind a task |
| `app_` | agent (an "app" in the API) |
| `sbx_` | standalone sandbox (Sandboxes API, not tied to a task) |

A task has at most one session at a time (`planning_session_id`), and it is reused for the whole
lifecycle — planning *and* implementation. Switching agents mid-task keeps the same session, so
context carries over.

## Pick an agent

```bash
helix spectask list-agents -o acme            # every agent you can see, with its assistant type
helix spectask list-agents -o acme --zed-external-only
```

Only `zed_external` agents can be launched by `spectask start`. The unfiltered list shows the
type so you can tell why a given agent won't launch.

## Start a task

```bash
# create and start in one step
helix spectask start --project prj_01xxx --agent app_01yyy \
  -n "Add dark mode" --prompt "Users want a dark theme across the app"

# start a card that already exists on the board
helix spectask start spt_01xxx

# dispatch a full brief without committing it to the repo
helix spectask start --project prj_01xxx --agent app_01yyy -n "Investigate flaky login" \
  --prompt "Work through the brief below end to end." \
  --prompt-file ./brief.md \
  --attach ./failing-run.log --attach ./trace.txt

# cheap and fast: no compositor, no streaming, agent only
helix spectask start --project prj_01xxx --runtime headless-ubuntu -n "Bump deps" --prompt "…"
```

Behaviour worth knowing:

- **It returns immediately.** The sandbox provisions in the background; the printed task URL
  shows it booting. `--wait` blocks (up to 3 minutes) and then prints session-level connect info.
- A `--wait` timeout is **not** a failure — the task exists and is still provisioning. The CLI
  exits 0 and prints the task id.
- `--prompt-file` is appended after `--prompt` when both are given. Use it for design docs and
  briefs — nothing needs to be committed.
- `--attach` uploads files as task attachments; the agent reads them inside the sandbox at
  `design/tasks/<task>/attachments/<name>`. Put logs and large context there, not in the prompt.
- `--runtime` is fixed for the life of the task. `ubuntu-desktop` (default) gives a streamable
  GNOME desktop with screenshots; `headless-ubuntu` is agent-only.
- `-q` prints only the task id (or the session id with `--wait`) — use it in scripts.

## Chat with a running task

```bash
# send one message, return immediately
helix spectask send spt_01xxx "List the files you've changed so far"

# send and block until the agent finishes the turn
helix spectask send spt_01xxx "Run the test suite and fix what fails" --wait --max-wait 600

# machine-readable
helix spectask send spt_01xxx "What is the current branch?" --wait --json
```

`--wait` polls (default every 2s, up to `--max-wait` seconds, default 300) until the agent stops
working. Without it you've only queued the message.

Read and follow the conversation:

```bash
helix spectask interact spt_01xxx                       # session info + recent history
helix spectask interact spt_01xxx --history --count 20  # last 20 turns
helix spectask interact spt_01xxx --send "status?"      # send and watch it stream back
helix spectask interact spt_01xxx --watch --interval 5  # live status refresh
```

Run with no flags, `interact` drops into an interactive chat loop — avoid that in a
non-interactive context; use `--send`/`--history` instead.

For structured access to the conversation, the session MCP tools are exposed directly:

```bash
helix spectask mcp session ses_01xxx current_session         # overview, turn count
helix spectask mcp session ses_01xxx session_toc            # numbered table of contents
helix spectask mcp session ses_01xxx get_turn --turn 3
helix spectask mcp session ses_01xxx search_session --query "database migration"
helix spectask mcp list ses_01xxx                           # what's available
```

These take a **session** id. Get it with `helix spectask get spt_01xxx --json | jq -r
.planning_session_id`.

## Look at what the agent is doing

```bash
helix spectask list                     # active sessions with external agents
helix spectask screenshot ses_01xxx     # also the quickest RevDial connectivity check
helix spectask live ses_01xxx           # stream stats + recent activity + send commands
helix spectask health                   # API health, active agent sessions, MCP endpoint
```

`spectask health` does **not** check the sandbox hosts. If tasks aren't getting sandboxes at all,
that's `helix api /sandboxes` — see [helix-deploy](../helix-deploy/SKILL.md).

`spectask screenshot` writes `screenshot-<timestamp>.jpg` into the current directory and prints
the filename — it does not write to stdout, so don't redirect it. (`helix sandbox screenshot`
does the opposite: stdout by default, `-o` for a file.)

Desktop control (desktop runtimes only):

```bash
helix spectask mcp desktop ses_01xxx take_screenshot
helix spectask mcp desktop ses_01xxx list_windows
helix spectask mcp desktop ses_01xxx type_text --text "hello"
helix spectask mcp desktop ses_01xxx mouse_click --x 640 --y 480
```

## Work inside the task's container

```bash
helix spectask exec ses_01xxx ls -la /home/retro/work
helix spectask exec ses_01xxx bash -c "cd repo && git status && git log --oneline -5"
helix spectask exec ses_01xxx --env FOO=bar printenv FOO
helix spectask exec ses_01xxx --background python3 server.py
helix spectask exec ses_01xxx --timeout 300 bash -c "go test ./..."

helix spectask copy ses_01xxx ./patch.diff                          # → ~/work/incoming/patch.diff
helix spectask copy ses_01xxx ./config.json --dest /home/retro/work/config.json
helix spectask copy ses_01xxx ./data.txt --no-file-manager          # don't pop the file manager
```

Note the argument order: session **first**, then the local file.

`--timeout` defaults to 30 seconds — raise it for builds and test runs or the command is cut off
mid-flight.

## Stop and resume

```bash
helix spectask stop ses_01xxx
helix spectask resume ses_01xxx      # verifies session restore
```

Do **not** run `helix spectask stop --all` on a shared instance — it stops every external-agent
session, including other people's work.

To free resources while keeping the card, prefer `helix spectask archive spt_01xxx`
(see [helix-board](../helix-board/SKILL.md)) — it stops the agent *and* takes the card off the
board.

## Standalone sandboxes

`helix sandbox` is a separate, lighter-weight API: a container with no board card and no coding
agent. Good for one-off compute, reproducing a build, or scripted environments.

```bash
helix sandbox runtimes                                  # what the server offers
helix sandbox create --runtime headless-ubuntu --size medium --ttl 1800 --name scratch
# also the cheapest end-to-end proof that the Hydra container runner is healthy
# small=1CPU/2GB, medium=4CPU/8GB, large=8CPU/16GB; --ttl seconds (default 600)
# --persistent mounts a workspace volume that survives restarts
# --project prj_01xxx associates it with a project

helix sandbox list --org acme
helix sandbox wait sbx_01xxx --timeout 3m
helix sandbox exec sbx_01xxx -- bash -lc "uname -a"
helix sandbox exec sbx_01xxx --detached -- ./long-job.sh     # prints a command id
helix sandbox logs sbx_01xxx cmd_01xxx --follow
helix sandbox commands sbx_01xxx
helix sandbox kill sbx_01xxx cmd_01xxx --signal TERM

helix sandbox ls sbx_01xxx --path /root
helix sandbox read sbx_01xxx /root/out.txt
echo "hello" | helix sandbox write sbx_01xxx /root/in.txt --mode 644
helix sandbox screenshot sbx_01xxx -o shot.jpg          # desktop runtimes only
helix sandbox terminal sbx_01xxx                        # interactive; avoid in scripts

helix sandbox delete sbx_01xxx
```

Sandboxes expire at their TTL. Set one long enough for the job, and delete explicitly when done
rather than relying on expiry.

**`--org` is per-command, not sticky.** If you create a sandbox in one org and then omit `--org`
on `exec`/`delete`, the CLI resolves your *first* org and the API answers `404 sandbox not found`
— which reads like the sandbox died, but is really "wrong org". Export `HELIX_ORG`, or pass
`--org` to every sandbox subcommand in a script.

The runtime list is deployment config (`HELIX_SANDBOX_RUNTIMES` on the API), not a fixed set —
`helix sandbox runtimes` is the only reliable answer for a given deployment. `--image` needs
`HELIX_SANDBOX_ALLOW_CUSTOM_IMAGE=true` on the server and is rejected otherwise.

Each sandbox runs under its own Docker daemon inside the Hydra runner, so containers you start
inside one are invisible to every other session. See
[helix-deploy](../helix-deploy/SKILL.md) for what that means operationally.

## Testing and diagnostics

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
| Screenshot 503s | The container is up but RevDial hasn't connected yet. Wait and retry before assuming it's broken. |
| Task sits in `spec_review` forever | It's waiting on a human. `helix spectask approve spt_01xxx`. |
| Task sits queued with `⏳` | A WIP limit or a dependency. Raise the limit in the project YAML or finish the blocker. |
| Agent stops responding | `helix spectask interact spt_01xxx --history` to see the last turn, then `helix spectask exec` to inspect the container. |
| Screenshot/stream fails on a headless task | Expected — `headless-ubuntu` has no compositor. |
