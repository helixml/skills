# Picking a launchable agent

```bash
helix spectask list-agents -o acme            # every agent you can see, with its assistant type
helix spectask list-agents -o acme --zed-external-only
```

**`agent_type: zed_external` is necessary but not sufficient**, and `list-agents` does not print
the field that decides it. Three orthogonal attributes are in play:

| Attribute | Values | Spec tasks need |
|---|---|---|
| `agent_kind` | `helix_agent` (default) · `coding_agent` · `org_agent` | **`coding_agent`** |
| `agent_type` | `zed_external`, … | `zed_external` |
| `code_agent_runtime` | `claude_code`, `codex_cli`, `zed_agent`, … | any |

`list-agents` shows the *type* and happily prints a copy-paste `spectask start` line for an
agent that `start` will then refuse:

```
Error: failed to create spec task: API returned 400:
spec tasks requires agent kind "coding_agent", got "org_agent"
```

That happens with helix-org bots (a chief-of-staff, say): they are `zed_external`, so they look
launchable, but the helix-org runtime reclassifies them to `org_agent` after apply. Check kind
directly before trusting the list:

```bash
helix api /apps | jq -r '.[] | "\(.id) kind=\(.agent_kind) name=\(.config.helix.name)"'
```

Agents created from a project YAML `agent:` block are classified `coding_agent`, so those are
always launchable whatever their `runtime:` — see [helix-board](../../helix-board/SKILL.md).

