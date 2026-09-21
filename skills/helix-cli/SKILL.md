---
name: helix-cli
description: Use when installing or upgrading the `helix` binary, when a `helix` command fails to authenticate or hangs on an organization prompt, when no first-class subcommand exists for an endpoint, or when managing Helix organizations, teams, members, secrets or provider endpoints.
---

# Helix CLI

`helix` is a single Go binary that talks to a Helix control plane's REST API. Everything the
web UI does — projects, the Kanban board, spec tasks, agents, knowledge, sandboxes, orgs — is
reachable from it.

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

```bash
export HELIX_URL=http://localhost:8080     # control plane
export HELIX_API_KEY=hl-...                # user API key, from the web UI under Account → API Keys
export HELIX_ORG=my-org                    # optional default org (name or org_… id)
helix organization list                    # verify before anything else
```

**Inside a Helix sandbox, skip all of that.** The platform exports `HELIX_API_URL` and
`USER_API_TOKEN`; every subcommand falls back to those names, so the CLI already works. See
[helix-session](../helix-session/SKILL.md) for the full in-container contract.

- **There are no global `--url` / `--api-key` flags.** Environment variables are the only way to
  point the CLI at a control plane, so in a script export them explicitly — on a host with more
  than one Helix reachable, a defaulted URL silently talks to the wrong one.
- The key **must** be a user key (`hl-…`). `oh-hallo-insecure-token` is the *runner* token — it
  authenticates runners to the control plane, not you, and most endpoints will reject it.
- Most org-scoped commands accept `--org`/`--organization` by **name or id**. Omit it and, if you
  belong to several orgs, the CLI prompts — which blocks forever in a non-interactive context.

## Command map

| Area | Commands | Where |
|---|---|---|
| Projects, Kanban board | `project`, `spectask` | [helix-board](../helix-board/SKILL.md) |
| Running/steering agents, sandboxes | `spectask`, `sandbox` | [helix-spec-tasks](../helix-spec-tasks/SKILL.md) |
| Filestore, knowledge/RAG, attachments | `upload`, `filesystem`, `knowledge` | [helix-files](../helix-files/SKILL.md) |
| Agents (apps), chat, models, tests | `agent`/`app`, `apply`, `chat`, `model`, `mcp`, `test` | [helix-agents](../helix-agents/SKILL.md) |
| Published pages, reports, PDFs, images | `artifact` | [helix-artifacts](../helix-artifacts/SKILL.md) |
| Install, upgrade, debug a deployment | — | [helix-deploy](../helix-deploy/SKILL.md) |
| Credentials from inside a container | — | [helix-session](../helix-session/SKILL.md) |
| Orgs, teams, members, roles, users | `organization`, `team`, `member`, `roles`, `user`, `system` | [reference/orgs-teams-members.md](reference/orgs-teams-members.md) |
| Secrets and provider endpoints | `secret`, `provider` | [reference/secrets-and-providers.md](reference/secrets-and-providers.md) |
| Anything without a subcommand | `api` | [reference/api.md](reference/api.md) |
| helix-org bot graph | `org` | not covered here — the `helix-org-cli` skill lives in the helix repo, not this one |

Note the two similarly-named groups: **`helix organization`** (alias `orgs`) manages Helix
organizations, while **`helix org`** (alias `helix-org`, `ho`) drives the separate *helix-org*
bot graph. They are different features.

## When something fails

`401`, `403 record not found`, a hang on an org list, `connection refused`, or
`project has no default coding agent` — see [reference/troubleshooting.md](reference/troubleshooting.md).
