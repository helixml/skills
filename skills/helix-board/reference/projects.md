# Projects and project YAML

## Contents
- Creating and forking
- project.yaml
- `runtime` vs agent_type vs agent_kind
- A project needs a repository
- WIP limits

## Creating and forking

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
                                       # OMITTED = false: nothing leaves the backlog by itself

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
    runtime: claude_code               # see the runtime table below
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
[helix-agents](../../helix-agents/SKILL.md). Unknown keys here are silently ignored, so a
`system_prompt:` under `agent:` will not do what it looks like it does; put standing instructions
in `spec.guidelines` instead.

## `runtime` vs "only zed_external agents can run spec tasks"

These are two different axes and it's easy to read them as contradictory:

- **`agent_type`** is the *container* kind. Spec tasks need `zed_external` — an agent desktop.
- **`runtime`** is the *code agent running inside* that desktop.

Every `runtime` a project YAML accepts maps to `agent_type: zed_external`, so any agent created
from a project `agent:` block is launchable by `helix spectask start`:

| `runtime:` | code agent inside the desktop |
|---|---|
| `claude_code` (default, also used for empty/unrecognised values) | Claude Code CLI |
| `zed` / `zed_agent` | Zed's built-in agent panel |
| `codex_cli` | OpenAI Codex CLI |
| `gemini_cli` | Gemini CLI |
| `qwen_code` | Qwen Code |
| `goose_code` | Goose (pair with the `goose:` block) |
| `opencode` | OpenCode |

An unrecognised value silently becomes `claude_code` rather than erroring — check
`helix spectask list-agents` afterwards to confirm you got what you meant.

There is a **third** attribute, `agent_kind`, and it is the one `spectask start` actually
enforces (`coding_agent`). An agent applied from a project `agent:` block is classified
`coding_agent` automatically, so this section's promise holds — but agents created elsewhere can
be `zed_external` and still be refused. See the agent-kind table in
[helix-spec-tasks](../../helix-spec-tasks/SKILL.md).

```bash
helix apply -f project.yaml -o acme
helix apply -f https://example.com/project.yaml     # URL and - (stdin) also work
```

## A project needs a repository

**`helix apply` with no `repository:` / `repositories:` block creates a project with no repo at
all**, and every spec task on it dies during workspace setup:

```
Workspace setup failed (exit code 1): No primary repository specified
  HELIX_REPOSITORIES not set
```

The task looks like it's planning for several minutes first, so this is easy to misread as a
hung agent. Confirm with `helix api /projects/<id>/repositories` — `[]` means this is your
problem.

Attaching an external repo needs the git provider connected via OAuth. If you just need *a* repo
— a scratch project, a smoke test, somewhere for an agent to write a report — create a
Helix-hosted one instead, which needs no external credentials:

```bash
helix api -X POST /git/repositories --input '{
  "name": "scratch",
  "repo_type": "code",
  "owner_id": "usr_01xxx",
  "organization_id": "org_01xxx",
  "project_id": "prj_01xxx",
  "is_external": false,
  "default_branch": "main",
  "initial_files": {"README.md": "# scratch\n"}
}'
helix api -X PUT /projects/prj_01xxx/repositories/code-scratch-01xxx/primary
```

Then reset and re-run the task: `helix spectask move <task> backlog && helix spectask start <task>`.

`kanban.wip_limits` is the only way to set WIP limits from the CLI — there is no
`board-settings` command; the limits live in the project and are re-applied on every
`helix apply`.
