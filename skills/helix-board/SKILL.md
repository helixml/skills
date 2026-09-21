---
name: helix-board
description: Use when working with a Helix project or its Kanban board — creating or forking a project, applying project YAML, listing or filtering the board, creating cards, moving them between columns, setting priority, labels or assignees, approving specs, archiving tasks, or setting WIP limits.
---

# Helix board and projects

Work in Helix lives in **projects**. Each project attaches one or more git repositories and owns
a **Kanban board** of **spec tasks**. A task moves left to right:

**Backlog → Planning → (Spec Review) → Implementation → Pull Request → Done**

> **Auth.** `export HELIX_URL=… HELIX_API_KEY=hl-…`, then `helix organization list` to verify.
> Inside a Helix sandbox this is already configured — see [helix-session](../helix-session/SKILL.md).

## Common operations

```bash
helix project list -o acme                          # -o org name or id; omit to use $HELIX_ORG
helix spectask board --project prj_01xxx            # the board, grouped by column
helix spectask get spt_01xxx                        # one card; --json for the full record

helix spectask create --project prj_01xxx -n "Add dark mode" --prompt "Users want a dark theme"
helix spectask update spt_01xxx --priority critical
helix spectask move spt_01xxx done
helix spectask approve spt_01xxx                    # approve specs → implementation begins
helix spectask archive spt_01xxx                    # stops the agent, keeps the history
```

**`move` rewrites state; it does not run the workflow.** Dropping a card into `planning` does not
make an agent plan it — `helix spectask start` does. Use `start` and `approve` to drive the
workflow, and `move` for bookkeeping. Moving to `backlog` is destructive by design: the server
clears specs, approvals, branch, PR list and session so the task starts genuinely fresh.

## Columns and statuses

The board collapses several statuses into one column. This mapping is what both the web board
and `helix spectask board` use — match it when filtering by `--status`:

| Column | Statuses |
|---|---|
| backlog | `backlog`, `spec_failed` |
| planning | `queued_spec_generation`, `spec_generation`, `spec_review`, `spec_revision`, `spec_approved` |
| implementation | `queued_implementation`, `implementation_queued`, `implementation`, `implementation_review`, `implementation_failed` |
| pull_request | `pull_request` |
| done | `done` |

A task showing `⏳` is queued behind a WIP limit or a dependency, and it clears on its own as the
queue drains. `queue_reason` explains which — it is a free-text string recomputed on every read
and never persisted, so only the **list** endpoint returns it:

```bash
helix spectask board --project prj_01xxx --json | jq -r '.[] | select(.queue_reason) | "\(.id) \(.queue_reason)"'
```

Two project settings decide whether a card moves at all: `auto_start_backlog_tasks` (defaults to
**false** — without it, nothing leaves the backlog by itself) and `kanban.wip_limits`. Both live
in the project YAML: [reference/projects.md](reference/projects.md).

## Detail

| You want to | Read |
|---|---|
| Create a project, write project YAML, pick a runtime, set WIP limits | [reference/projects.md](reference/projects.md) |
| Every flag for create/update/move/label/approve/archive | [reference/cards.md](reference/cards.md) |
| Filter the board, script it, understand `board` vs `get` | [reference/queries.md](reference/queries.md) |
| Bulk operations over a board | [reference/recipes.md](reference/recipes.md) |

To actually *run* a task's agent — watch it, chat with it, exec in its sandbox — see
[helix-spec-tasks](../helix-spec-tasks/SKILL.md).
