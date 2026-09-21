---
name: helix-spec-tasks
description: Use when running, watching or steering a Helix coding agent — starting a spec task, chatting with a running task, reading its conversation, exec'ing or copying files into its container, screenshotting or streaming its desktop, debugging a stuck agent, or driving standalone Helix sandboxes.
---

# Running and steering Helix spec tasks

A spec task is a unit of work that gets its own isolated sandbox — a full Ubuntu container, with
a GNOME desktop by default, running a coding agent (Claude Code, Codex, Gemini CLI, Qwen Code,
Goose, or Zed's agent) against the project's repositories. This skill is about the *running*
task; for the cards themselves see [helix-board](../helix-board/SKILL.md).

> **Auth.** `export HELIX_URL=… HELIX_API_KEY=hl-…`, then `helix organization list` to verify.
> Inside a Helix sandbox this is already configured — see [helix-session](../helix-session/SKILL.md).

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
context carries over. Session-scoped commands want the `ses_…`:

```bash
SES=$(helix spectask get spt_01xxx --json | jq -r .planning_session_id)
```

## The common path

```bash
helix spectask start --project prj_01xxx --agent app_01yyy \
  -n "Add dark mode" --prompt "Users want a dark theme across the app"

helix spectask send spt_01xxx "Run the test suite and fix what fails" --wait --max-wait 600
helix spectask interact spt_01xxx --history --count 20
helix spectask screenshot "$SES"
helix spectask stop "$SES"
```

**`start` returns immediately** — the sandbox provisions in the background, and a `--wait`
timeout is not a failure. **`send` without `--wait` only queues the message.**

**`helix spectask exec` is not a shell.** It enforces a server-side allowlist (`ls`, `cat`,
`echo`, `pkill`, `npm`, `claude`, a few graphics benchmarks) and has no `bash`, no pipes and no
redirection. To run arbitrary commands, ask the agent — it has a real shell — or use a
standalone sandbox, where `helix sandbox exec` *is* general-purpose.

## Detail

| You want to | Read |
|---|---|
| Choose a launchable agent, decode `agent_kind` vs `agent_type` vs `runtime` | [reference/agents.md](reference/agents.md) |
| Every `start` flag: prompts, briefs, attachments, runtimes | [reference/starting.md](reference/starting.md) |
| Chat, history, and the session MCP tools | [reference/conversation.md](reference/conversation.md) |
| Watch a desktop, exec, copy files, stop and resume | [reference/container.md](reference/container.md) |
| Standalone sandboxes (`helix sandbox`) | [reference/sandboxes.md](reference/sandboxes.md) |
| Tests, benchmarks, and a symptom table | [reference/diagnostics.md](reference/diagnostics.md) |
