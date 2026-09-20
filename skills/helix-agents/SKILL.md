---
name: helix-agents
description: Use when defining, deploying, chatting with or testing a Helix agent (app) — applying agent YAML, wiring API/OpenAPI tools, MCP servers or knowledge into one, granting team or user access, running YAML-defined evaluations, or registering models and provider endpoints.
---

# Helix agents

An **agent** (an "app" in the API, `app_…`) is a configured assistant: a model, a system prompt,
and optionally tools, MCP servers, knowledge, and tests. Agents back both plain chat and the
coding agents that run spec tasks.

`helix agent` aliases to `app`, `apps`, `agents`, and `a` — all four appear in the wild.

> **Auth.** `export HELIX_URL=… HELIX_API_KEY=hl-…`, then `helix organization list` to verify.
> Inside a Helix sandbox this is already configured — see [helix-session](../helix-session/SKILL.md).

## Define an agent

Agents are declared in YAML and applied with `helix apply -f agent.yaml`. The schema covers the
model and system prompt, API/OpenAPI tools, MCP servers, knowledge and tests:
[reference/agent-yaml.md](reference/agent-yaml.md).

## Manage agents

```bash
helix agent list -o acme
helix agent inspect app_01xxx --output json      # or yaml (default)
helix agent remove app_01xxx                     # --knowledge=false keeps the knowledge

helix agent grant-access app_01xxx --user dev@acme.com --roles read
helix agent grant-access app_01xxx --team platform --roles write
helix agent list-access-grants app_01xxx
helix agent remove-access app_01xxx grant_01xxx
```

Use `helix roles list -o acme` to see the role names your deployment defines before granting.

## Chat with an agent

```bash
helix chat --agent app_01xxx "Summarise the release notes"
helix chat --agent app_01xxx --session ses_01xxx "and what changed in auth?"    # continue
helix chat --agent app_01xxx --model claude-opus-4-6 "explain this trace"       # override model
helix chat --agent app_01xxx --stream "write me a haiku"
helix chat --agent app_01xxx -v "help me debug"                                 # verbose
helix chat --agent app_01xxx --timeout 300 "long analysis"
```

`--agent` is required. `--session` continues an existing conversation — grab the session id from
the first response and thread it through for multi-turn work.

This is for **chat** agents. To talk to a *coding* agent working on a spec task, use
`helix spectask send` / `helix spectask interact` — see
[helix-spec-tasks](../helix-spec-tasks/SKILL.md). To talk to a helix-org bot, use
`helix org agents chat <bot-id>`.

## Test an agent

```bash
helix test -f agent.yaml
```

Runs the `tests:` blocks in the YAML — each step sends `prompt` and grades the reply against
`expected_output` with an LLM judge. `helix evals` provides the heavier evaluation harness for
fine-tuned models.

## MCP

Expose an agent's tools to an external MCP client (an IDE, another agent):

```bash
helix mcp run --app-id app_01xxx --url "$HELIX_URL" --api-key "$HELIX_API_KEY"
```

This runs a stdio MCP proxy — point your MCP client's command at it.

To go the other way and give an agent MCP servers, declare them under `mcps:` in the YAML as
above. Inside spec-task desktops, prefer invoking pre-installed servers by binary name
(`mcp-server-github`) over `npx -y …`: parallel `npx` invocations race on the shared npm cache
and time out.

## Models and providers

Register models, and attach any OpenAI-compatible endpoint (OpenAI, Together, a self-hosted
vLLM): [reference/models-and-providers.md](reference/models-and-providers.md).

Secrets referenced as `${VAR}` in agent YAML are created with `helix secret` — see
[helix-cli/reference/secrets-and-providers.md](../helix-cli/reference/secrets-and-providers.md).
That command creates and lists them; it never reads a value back. An agent that needs the value
at runtime uses [helix-session](../helix-session/SKILL.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `selected agent not found` on a spec task | Wrong `app_…` id, or the agent is in a different org |
| `spec tasks requires agent kind "coding_agent", got …` | The agent's `agent_kind` is `helix_agent` or `org_agent`. `agent_type: zed_external` is not enough — kind is a separate field, and `spectask list-agents` does not print it. Agents from a project YAML `agent:` block are classified `coding_agent`. |
| `helix spectask start` won't launch an agent | Only `zed_external` assistants launch — check `helix spectask list-agents` |
| `500 … error running LLM: … 502 … upstream unavailable` | The agent and CLI are fine — its **provider endpoint** is down. Check `helix provider list` and the base URL it points at, especially for self-hosted vLLM/Ollama boxes. |
| Tools never fire | Check the OpenAPI `schema:` path resolves and the endpoint is reachable from the control plane |
| `${VAR}` arrives empty in an MCP env | No matching Helix secret in scope — create it with `helix secret create` |
