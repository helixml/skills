---
name: helix-agents
description: Define, deploy, chat with and test Helix agents (apps) from the CLI — apply agent YAML with system prompts, API/OpenAPI tools, MCP servers and knowledge; grant team/user access; chat with an agent or an external Zed agent; run YAML-defined evaluations; and register models and provider endpoints. Use when the user wants to create or update a Helix agent/app, talk to a Helix agent, wire tools or MCP servers into one, or manage Helix models.
---

# Helix agents

An **agent** (an "app" in the API, `app_…`) is a configured assistant: a model, a system prompt,
and optionally tools, MCP servers, knowledge, and tests. Agents back both plain chat and the
coding agents that run spec tasks.

Read [helix-cli](../helix-cli/SKILL.md) for auth first.

`helix agent` aliases to `app`, `apps`, `agents`, and `a` — all four appear in the wild.

## Define an agent

```yaml
# agent.yaml
name: support-bot
description: Answers product support questions from the docs
assistants:
  - name: Helix
    model: claude-sonnet-4-6
    provider: anthropic
    system_prompt: |
      You answer support questions using only the indexed documentation.
      If the docs don't cover it, say so and suggest opening a ticket.

    knowledge:
      - name: docs
        source:
          web:
            urls:
              - https://docs.example.com/getting-started

    apis:
      - name: Hiring Pipeline API
        description: List job vacancies, filter by title or candidate
        url: https://demos.helix.ml
        schema: ./openapi/jobvacancies.yaml     # local path or URL

    mcps:
      - name: github
        transport: stdio
        command: mcp-server-github
        env:
          GITHUB_TOKEN: "${GITHUB_TOKEN}"       # resolved from Helix secrets

    tests:
      - name: in-scope
        steps:
          - prompt: How do I rotate my API key?
            expected_output: A procedure referencing the docs
```

Apply it:

```bash
helix apply -f agent.yaml -o acme          # helix agent apply is the same command
helix apply -f agent.yaml --global         # available to every org (admin)
helix apply -f https://example.com/agent.yaml
cat agent.yaml | helix apply -f -
```

`helix apply` dispatches on the YAML's `kind`: `kind: Project` applies a project (see
[helix-board](../helix-board/SKILL.md)); anything else is treated as an agent config. Apply is
idempotent — same `name`, same org updates in place.

For knowledge sync flags (`--rsync`, `--wait-knowledge`, `--refresh-knowledge`) see
[helix-files](../helix-files/SKILL.md).

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

```bash
helix model list                              # --runtime vllm --type chat --enabled true
helix model list -q                           # ids only
helix model inspect llama3.1:8b --format json
helix model apply -f model.yaml
helix model delete my-model --force
```

```yaml
# model.yaml
apiVersion: model.aispec.org/v1alpha1
kind: Model
metadata:
  name: llama3.1:8b
spec:
  id: llama3.1:8b
  name: Llama 3.1 8B
  type: chat            # chat | image | embed
  runtime: ollama       # ollama | vllm | diffusers
  memory: "8GB"
  context_length: 8192
  enabled: true
```

You only declare total memory — Helix picks the GPUs, sets tensor-parallel size for vLLM, and
computes memory ratios itself.

To attach a hosted or self-hosted OpenAI-compatible endpoint instead of running models locally:

```bash
helix provider create -n my-vllm -u https://vllm.internal/v1 -f ./key.txt -m qwen3-32b
helix provider list
```

Secrets referenced as `${VAR}` in agent YAML come from `helix secret` — see
[helix-cli](../helix-cli/SKILL.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `selected agent not found` on a spec task | Wrong `app_…` id, or the agent is in a different org |
| Agent rejected for a spec task | Spec tasks need a **coding** agent; chat agents can't run them |
| `helix spectask start` won't launch an agent | Only `zed_external` assistants launch — check `helix spectask list-agents` |
| Tools never fire | Check the OpenAPI `schema:` path resolves and the endpoint is reachable from the control plane |
| `${VAR}` arrives empty in an MCP env | No matching Helix secret in scope — create it with `helix secret create` |
