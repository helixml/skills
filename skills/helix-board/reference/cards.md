# Working with cards

## Contents
- Create a card
- Edit and move
- Labels
- Review gates
- Clean up

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
(`low|medium|high|critical`), `--type` (`feature|bug|refactor`; forked samples also use `task`, so the set is not closed), `--runtime`
(`ubuntu-desktop` for a streamable GNOME desktop, `headless-ubuntu` for agent-only — cheaper and
faster; **immutable once the task exists**), `-q` to print only the task id.

To create *and* start it in one step, use `helix spectask start --project … --prompt …` instead
(see [helix-spec-tasks](../../helix-spec-tasks/SKILL.md)).

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

## Old patterns

<details>
<summary>Before helixml/helix#3033: no board/task-management verbs</summary>

The verbs `board`, `get`, `create`, `update`, `move`, `label`, `attach`, `attachments`,
`approve`, `archive`, `delete` and `progress` landed in helixml/helix#3033. On a binary
predating it, use the `helix api` equivalents given inline in each section above — the REST
endpoints have been there all along. `helix project` and `helix spectask start` work on every
version.

</details>
