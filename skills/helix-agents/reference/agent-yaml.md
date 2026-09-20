# Agent YAML

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
[helix-board](../../helix-board/SKILL.md)); anything else is treated as an agent config. Apply is
idempotent — same `name`, same org updates in place.

For knowledge sync flags (`--rsync`, `--wait-knowledge`, `--refresh-knowledge`) see
[helix-files](../../helix-files/SKILL.md).

