---
name: helix-board
description: Manage Helix projects and the spec-task Kanban board from the CLI — create/fork projects, apply project YAML, list the board, create and move cards between columns, set priority/labels/assignees, approve specs and implementations, archive and delete tasks, and set WIP limits. Use when the user talks about the Helix board, backlog, columns, spec tasks, kanban, WIP limits, or Helix projects.
---

# Helix board and projects

Work in Helix lives in **projects**. Each project attaches one or more git repositories and owns
a **Kanban board** of **spec tasks**. A task moves left to right:

**Backlog → Planning → (Spec Review) → Implementation → Pull Request → Done**

Read [helix-cli](../helix-cli/SKILL.md) first for auth. To actually *run* a task's agent — watch
it, chat with it, exec in its sandbox — see [helix-spec-tasks](../helix-spec-tasks/SKILL.md).

> **Version note.** The board/task-management verbs (`board`, `get`, `create`, `update`, `move`,
> `label`, `attach`, `attachments`, `approve`, `archive`, `delete`, `progress`) landed in
> helixml/helix#3033 (merged to main; ships in the first release after 2.12.3). On an older binary, use the `helix api` equivalents given inline below —
> the REST endpoints have been there all along. `helix project` and `helix spectask start` work
> on every version.

## Projects

```bash
helix project list -o acme                      # -o org name or id; omit to use $HELIX_ORG
helix project samples                           # --category web --difficulty beginner
helix project fork modern-todo-app -n "My App" -o acme
helix project tasks prj_01xxx                   # board grouped by column (also: helix spectask board)
```

Create or update a project declaratively — this is the reliable path, because it also attaches
repos, sets the startup script, seeds the board, and creates the project's coding agent in one
apply:

```yaml
# project.yaml
apiVersion: helix.ml/v1alpha1
kind: Project
metadata:
  name: my-fullstack-app
spec:
  description: "Full-stack web application"
  technologies: [React, Go, PostgreSQL]
  guidelines: |
    Use conventional commits. All PRs require tests.

  repositories:
    - url: "https://github.com/org/my-api"
      branch: main
      primary: true                    # exactly one primary when there are several
    - url: "https://github.com/org/my-frontend"
      branch: main

  startup:
    script: |
      #!/bin/bash
      set -e
      go mod download
      go run ./cmd/server

  auto_start_backlog_tasks: true       # orchestrator pulls from backlog when there's capacity

  kanban:
    wip_limits:                        # 0 = unlimited
      planning: 5
      implementation: 3
      review: 3

  tasks:                               # seeds cards on the board; omit in production
    - title: "Set up CI pipeline"
      description: "Configure GitHub Actions for build, test, and deploy"

  agent:                               # creates/updates the project's coding agent
    name: "Project Assistant"
    runtime: claude_code               # claude_code (default) | zed | qwen_code | gemini_cli | codex_cli | goose
    model: claude-sonnet-4-6
    provider: anthropic
    credentials: api_key               # api_key (default, routes via the Helix LLM proxy) | subscription
    tools:
      web_search: true
      browser: true
    display:
      resolution: 1080p                # 1080p | 4k | 5k
      desktop_type: ubuntu             # ubuntu (GNOME) | sway
```

The project `agent:` block is deliberately small — `name`, `runtime`, `model`, `provider`,
`credentials`, `tools`, `display`, `goose`. Anything else (system prompts, MCP servers, OpenAPI
tools, knowledge) belongs on a full agent YAML applied separately — see
[helix-agents](../helix-agents/SKILL.md). Unknown keys here are silently ignored, so a
`system_prompt:` under `agent:` will not do what it looks like it does; put standing instructions
in `spec.guidelines` instead.

```bash
helix apply -f project.yaml -o acme
helix apply -f https://example.com/project.yaml     # URL and - (stdin) also work
```

`kanban.wip_limits` is the only way to set WIP limits from the CLI — there is no
`board-settings` command; the limits live in the project and are re-applied on every
`helix apply`.

## Read the board

```bash
helix spectask board --project prj_01xxx
helix spectask board --project prj_01xxx --status spec_review
helix spectask board --project prj_01xxx --label bug --label ui        # AND semantics
helix spectask board --project prj_01xxx --assignee usr_01xxx
helix spectask board --project prj_01xxx --include-archived
helix spectask board --project prj_01xxx --json | jq -r '.[] | "\(.id) \(.status) \(.name)"'
```

Older binaries: `helix project tasks prj_01xxx`, or
`helix api "/spec-tasks?project_id=prj_01xxx"`.

One card:

```bash
helix spectask get spt_01xxx            # --json for the full record
helix spectask progress spt_01xxx       # spec + implementation phase timings
```

### Columns and statuses

The board collapses several statuses into one column. This mapping is what both the web board
and `helix spectask board` use — match it when filtering by `--status`:

| Column | Statuses |
|---|---|
| backlog | `backlog`, `spec_failed` |
| planning | `queued_spec_generation`, `spec_generation`, `spec_review`, `spec_revision`, `spec_approved` |
| implementation | `queued_implementation`, `implementation_queued`, `implementation`, `implementation_review`, `implementation_failed` |
| pull_request | `pull_request` |
| done | `done` |

A task showing `⏳` on the board is queued behind a WIP limit or a dependency — the reason is in
`queue_reason`, and it clears on its own as the queue drains.

## Create a card

```bash
# card only — no sandbox, stays in backlog
helix spectask create --project prj_01xxx -n "Add dark mode" \
  --prompt "Users want a dark theme across the app"

# from a written brief, high priority, picked up automatically when there's capacity
helix spectask create --project prj_01xxx --prompt-file ./brief.md --priority high --auto-start

# with context files the agent can read without bloating the prompt
helix spectask create --project prj_01xxx --prompt "Fix the flaky login test" \
  --attach ./failing-run.log --attach ./screenshot.png

# skip planning entirely and go straight to implementation
helix spectask create --project prj_01xxx --prompt "Bump the linter" --just-do-it
```

Flags worth knowing: `--agent app_…` (defaults to the project's coding agent), `--priority`
(`low|medium|high|critical`), `--type` (`feature|bug|refactor`), `--runtime`
(`ubuntu-desktop` for a streamable GNOME desktop, `headless-ubuntu` for agent-only — cheaper and
faster; **immutable once the task exists**), `-q` to print only the task id.

To create *and* start it in one step, use `helix spectask start --project … --prompt …` instead
(see [helix-spec-tasks](../helix-spec-tasks/SKILL.md)).

Older binaries:

```bash
helix api -X POST /spec-tasks/from-prompt \
  --input '{"project_id":"prj_01xxx","name":"Add dark mode","prompt":"…","priority":"high"}'
```

## Edit and move cards

```bash
helix spectask update spt_01xxx --priority critical
helix spectask update spt_01xxx -n "Add dark mode (v2)" --description "…"
helix spectask update spt_01xxx --assignee usr_01xxx      # must be an org member
helix spectask update spt_01xxx --unassign
helix spectask update spt_01xxx --agent app_01yyy         # switch harness mid-task; context carries over
helix spectask update spt_01xxx --keep-alive              # don't release the sandbox when idle/done

helix spectask move spt_01xxx done
helix spectask move spt_01xxx backlog
helix spectask move spt_01xxx implementation
```

`move` accepts the column names `backlog`, `planning`, `review`, `implementation`,
`pull_request`, `done`, or any raw status.

**`move` rewrites state; it does not run the workflow.** Dropping a card into `planning` does not
make an agent plan it — `helix spectask start` does. Dropping it into `implementation` does not
make it code. Use `start` and `approve` to drive the workflow, and `move` for the bookkeeping
(reprioritising, marking something done by hand, resetting a stuck card).

**Moving to `backlog` is destructive by design**: the server clears the task's specs, approvals,
branch, PR list, and session so it starts genuinely fresh. That is the intended "reset this
task" action — don't reach for it just to reorder the board.

Older binaries: `helix api -X PUT /spec-tasks/spt_01xxx --input '{"status":"done"}'`.

## Labels

```bash
helix spectask label list prj_01xxx          # every label used in the project
helix spectask label add spt_01xxx bug       # idempotent
helix spectask label remove spt_01xxx bug
```

Older binaries: `helix api -X POST /spec-tasks/spt_01xxx/labels --input '{"label":"bug"}'`.

## Review gates

A task in `spec_review` is waiting on a human. Nothing progresses until you approve or send it
back:

```bash
helix spectask approve spt_01xxx                     # approve the specs → implementation begins
helix spectask approve spt_01xxx --reject \
  --comments "Reuse the existing auth middleware" \
  --change "Drop the new session table"              # --change repeatable
helix spectask approve spt_01xxx --implementation    # approve the finished work → PR
```

Approving specs requires the approver to have git provider OAuth connected, because their
credentials sign the commits and push. If it fails with `oauth_required`, connect the provider in
the web UI first.

Older binaries:

```bash
helix api -X POST /spec-tasks/spt_01xxx/approve-specs --input '{"approved":true}'
helix api -X POST /spec-tasks/spt_01xxx/approve-implementation --input '{}'
```

## Clean up

```bash
helix spectask archive spt_01xxx        # hides it from the board and stops its agent
helix spectask archive spt_01xxx --undo
helix spectask delete spt_01xxx -f      # permanent; without -f it just describes the task
```

Archive is the safe default — it stops the sandbox and frees resources while keeping the history.
Reach for `delete` only when the card was a mistake.

Older binaries: `helix api -X PATCH /spec-tasks/spt_01xxx/archive --input '{"archived":true}'`.

## Recipes

Move everything merged into Done:

```bash
helix spectask board --project prj_01xxx --status pull_request --json \
  | jq -r '.[] | select(.merged_to_main) | .id' \
  | xargs -rn1 -I{} helix spectask move {} done
```

Triage: label every failed task and bump it:

```bash
helix spectask board --project prj_01xxx --json \
  | jq -r '.[] | select(.status | endswith("_failed")) | .id' \
  | while read id; do
      helix spectask label add "$id" needs-triage
      helix spectask update "$id" --priority high
    done
```

Archive everything done older than 30 days:

```bash
cutoff=$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)
helix spectask board --project prj_01xxx --status done --json \
  | jq -r --arg c "$cutoff" '.[] | select(.updated_at < $c) | .id' \
  | xargs -rn1 helix spectask archive
```
