# Conversation: chat, history, session MCP

```bash
# send one message, return immediately
helix spectask send spt_01xxx "List the files you've changed so far"

# send and block until the agent finishes the turn
helix spectask send spt_01xxx "Run the test suite and fix what fails" --wait --max-wait 600

# machine-readable
helix spectask send spt_01xxx "What is the current branch?" --wait --json
```

`--wait` polls (default every 2s, up to `--max-wait` seconds, default 300) until the agent stops
working. Without it you've only queued the message.

Read and follow the conversation:

```bash
helix spectask interact spt_01xxx                       # session info + recent history
helix spectask interact spt_01xxx --history --count 20  # last 20 turns
helix spectask interact spt_01xxx --send "status?"      # send and watch it stream back
helix spectask interact spt_01xxx --watch --interval 5  # live status refresh
```

Run with no flags, `interact` drops into an interactive chat loop — avoid that in a
non-interactive context; use `--send`/`--history` instead.

For structured access to the conversation, the session MCP tools are exposed directly:

```bash
helix spectask mcp session ses_01xxx current_session         # overview, turn count
helix spectask mcp session ses_01xxx session_toc            # numbered table of contents
helix spectask mcp session ses_01xxx get_turn --turn 3
helix spectask mcp session ses_01xxx search_session --query "database migration"
helix spectask mcp list ses_01xxx                           # what's available
```

These take a **session** id. Get it with `helix spectask get spt_01xxx --json | jq -r
.planning_session_id`.

## Old patterns

<details>
<summary>Before helixml/helix#3033: <code>send</code> and <code>interact</code> needed a session id</summary>

Addressing a task by its `spt_…` id landed in helixml/helix#3033. On older binaries resolve the
session first:

```bash
SES=$(helix api /spec-tasks/spt_01xxx | jq -r .planning_session_id)
helix spectask send "$SES" "…"
```

</details>
