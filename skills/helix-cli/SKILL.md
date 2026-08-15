---
name: helix-cli
description: Install, authenticate and navigate the Helix CLI (`helix`) against a Helix control plane. Start here for any Helix task — it covers HELIX_URL/HELIX_API_KEY/HELIX_ORG setup, the full command map, organization/team/member/secret/provider management, and the `helix api` escape hatch for endpoints without a first-class command. Use when the user mentions helix, helixml, a Helix control plane, spec tasks, the Helix Kanban board, Helix agents, or `helix` commands.
---

# Helix CLI

`helix` is a single Go binary that talks to a Helix control plane's REST API. Everything the
web UI does — projects, the Kanban board, spec tasks, agents, knowledge, sandboxes, orgs — is
reachable from it.

Related skills: [helix-board](../helix-board/SKILL.md) (projects and the Kanban board),
[helix-spec-tasks](../helix-spec-tasks/SKILL.md) (run and steer coding agents),
[helix-files](../helix-files/SKILL.md) (uploads, knowledge, attachments),
[helix-agents](../helix-agents/SKILL.md) (agent YAML, chat, models),
[helix-deploy](../helix-deploy/SKILL.md) (install and debug a deployment),
[helix-e2e](../helix-e2e/SKILL.md) (end-to-end smoke test).

## Install

Release binaries are published per platform on every tag:

```bash
OS=linux ARCH=amd64          # darwin/arm64, darwin/amd64, linux/arm64, windows/amd64 also published
curl -fsSL -o helix "https://github.com/helixml/helix/releases/latest/download/helix-${OS}-${ARCH}"
chmod +x helix && sudo mv helix /usr/local/bin/helix
helix version
```

From a source checkout (this is also how you test unreleased commands):

```bash
cd api && CGO_ENABLED=0 go build -o /tmp/helix .
```

## Authenticate

Two environment variables do all the work:

```bash
export HELIX_URL=http://localhost:8080     # control plane; defaults to http://localhost:8080
export HELIX_API_KEY=hl-...                # user API key, created in the web UI under Account → API Keys
export HELIX_ORG=my-org                    # optional default org (name or org_… id)
```

- **There are no global `--url` / `--api-key` flags.** `helix --help` has only `--help`.
  Environment variables are the only way to point the CLI at a control plane, so in a script
  export them explicitly rather than relying on the `http://localhost:8080` default — on a host
  with more than one Helix reachable, a defaulted `HELIX_URL` silently talks to the wrong one.
- The key **must** be a user key (`hl-…`). `oh-hallo-insecure-token` is the *runner* token — it
  authenticates runners to the control plane, not you, and most endpoints will reject it.
- Most org-scoped commands accept `--org`/`--organization` by **name or id**. If you omit it and
  belong to exactly one org, that one is used; if you belong to several, the CLI prompts. In a
  non-interactive context always pass it explicitly or export `HELIX_ORG`, or the command blocks
  on a prompt.
- Verify the key works before anything else: `helix organization list`.

## Command map

| Area | Commands | Skill |
|---|---|---|
| Projects, Kanban board, spec tasks | `project`, `spectask` | [helix-board](../helix-board/SKILL.md) |
| Running/steering coding agents, sandboxes | `spectask`, `sandbox` | [helix-spec-tasks](../helix-spec-tasks/SKILL.md) |
| Filestore, knowledge/RAG, attachments | `upload`, `filesystem`, `knowledge` | [helix-files](../helix-files/SKILL.md) |
| Agents (apps), chat, models, providers, secrets | `agent`/`app`, `apply`, `chat`, `model`, `provider`, `secret`, `mcp`, `test` | [helix-agents](../helix-agents/SKILL.md) |
| Orgs, teams, members, roles, users, system settings | `organization`, `team`, `member`, `roles`, `user`, `system` | this skill, below |
| helix-org bot graph (agents, topics, processors, assets) | `org` | see the `helix-org-cli` skill in the helix repo |
| Anything else | `api` | this skill, below |

Note the two similarly-named groups: **`helix organization`** (alias `orgs`) manages Helix
organizations, while **`helix org`** (alias `helix-org`, `ho`) drives the separate *helix-org*
bot graph. They are different features.

## Organizations, teams, members

```bash
helix organization list
helix organization create -n acme -d "Acme Corp"        # -n slug, -d display name
helix organization delete acme                          # accepts id or name

helix team list -o acme
helix team create -o acme -n platform
helix team inspect -o acme -t platform
helix team delete -o acme -t team_01xxx

helix member list -o acme                               # add -t platform for one team
helix member add -o acme -u dev@acme.com -r member      # roles: owner | member
helix member add -o acme -t platform -u dev@acme.com    # add to a team
helix member remove -o acme -u dev@acme.com -f

helix roles list -o acme
```

Admin-only:

```bash
helix user list
helix user reset-password
helix system settings get
```

## Secrets and provider endpoints

Secrets are injected as environment variables into project sessions, so this is how an agent
gets a `GITHUB_TOKEN` or an API key without it landing in a prompt or the repo:

```bash
helix secret list                          # personal; --org for org-owned
helix secret create -n GITHUB_TOKEN -v ghp_xxx -p prj_01xxx    # -p scopes it to a project
helix secret create -n OPENAI_API_KEY -v sk-xxx -a app_01xxx   # -a scopes it to an agent
helix secret update -n GITHUB_TOKEN -v ghp_yyy
helix secret delete -n GITHUB_TOKEN
```

Provider endpoints attach any OpenAI-compatible API (OpenAI, Together, a self-hosted vLLM):

```bash
helix provider list
helix provider create -n my-vllm -u https://vllm.internal/v1 -k sk-xxx -m qwen3-32b,qwen3-8b
helix provider update prov_01xxx -m qwen3-32b
helix provider delete prov_01xxx
```

`-f/--api-key-file` reads the key from a file instead of argv, which keeps it out of your shell
history and the process table. Prefer it in scripts.

## `helix api` — the escape hatch

Not every endpoint has a first-class command. `helix api` is `gh api` for Helix: same
credentials, any path, any method.

```bash
helix api /projects?organization_id=org_01xxx
helix api /spec-tasks?project_id=prj_01xxx
helix api -X PUT /spec-tasks/spt_01xxx --input '{"priority":"critical"}'
helix api -X POST /orgs/acme/bots/chief-of-staff/activate
echo '{"label":"bug"}' | helix api -X POST /spec-tasks/spt_01xxx/labels --input -
helix api -X POST /projects --input @project.json
```

- Path may be `/projects`, `/api/v1/projects`, or `projects` — all resolve.
- `--input` takes a JSON string, `@file`, or `-` for stdin. `-f key=value` sets a single string
  field when there's no body.
- `--timeout` is in seconds (default 120).

When you find yourself scripting the same `helix api` call repeatedly, that's a missing CLI
command — the CLI lives in `api/pkg/cli/` in the helix repo and new commands are small cobra
files.

## Output and scripting

Most commands print human-readable tables. For scripting, prefer:

- `--json` where offered (`spectask board`, `spectask get`, `org agents list`, …)
- `helix agent inspect <id> --output json`
- `helix api <path>` — always raw JSON, always parseable

```bash
# every task id on a board
helix spectask board --project prj_01xxx --json | jq -r '.[].id'

# the session behind a task
helix api /spec-tasks/spt_01xxx | jq -r '.planning_session_id'
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `401 unauthorized` | `HELIX_API_KEY` missing/expired, or you used the runner token |
| `403 ... record not found` | The key's user isn't a member of that project's org — this is authz, not a missing row |
| Command hangs printing an org list | Interactive org prompt; pass `--org`/`-o` or set `HELIX_ORG` |
| `connection refused` | Wrong `HELIX_URL`, or the control plane is still starting — see [helix-deploy](../helix-deploy/SKILL.md) |
| `project has no default coding agent` | The project has no agent attached; pass `--agent app_…` or set one on the project |
