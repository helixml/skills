# Troubleshooting bots and instances

Start with `botctl doctor <bot> [<session_id>]`. It lints the config (harness traps,
profile/tool mismatches, prompt vs profile) and, with a session, checks the sandbox. Then
narrow down with the workflow below.

## Workflow

1. **Is it the config?** Run `botctl get <bot>`. Check the harness, model, provider,
   `instance_profile`, and whether `restart_required` is set.
2. **Did the turn happen?** Run `botctl turns <sid>`. For each turn you get its state, the
   error, every tool call with its status, and the final text.
   - `waiting` for a long time: the agent is working or stuck. Run `botctl watch <sid>`.
   - `error`: the error string is in the header line. Match it against the table below.
   - `complete` but the answer is wrong: read the tool calls. Did it open the right page, did
     the login fail, did it guess? That is usually a prompt problem, not a platform one.
3. **Is the sandbox healthy?** Run `botctl logs <sid>`. It shows processes, the browser MCP
   count, workspace and `incoming/`, `AGENTS.md`, skills, the setup log, Zed errors, and the
   opencode and Chrome logs.
4. **What is on screen?** For desktop runtimes, run `botctl shot <sid>`. For headless ones, ask
   the bot to `take_snapshot` and report.
5. **Reproduce on a fresh instance** with `botctl ask <bot> "<the failing request>" --tools`.
   If it only fails on the old instance, the cause is state: an old prompt snapshot, an expired
   login, a browser lock, or an idle-terminated sandbox.
6. **Make it permanent.** Add the failing request to the eval suite before you fix it, then
   confirm the suite passes afterwards.

## Symptoms

| Symptom | Likely cause | Fix |
|---|---|---|
| Prompt change has no effect | Instances snapshot the prompt at creation. Main session: the change lands at the next activation or restart | New instance. `botctl restart <bot>` or `apply-config` for the main session |
| Profile change has no effect | Applies at the instance's next sandbox start | New instance |
| New tool not visible to a running main session | Harness caches `tools/list` at startup | Restart the sandbox |
| Instance has no `get_secret` or other helix tools | Default profile `tools: []`; served = `profile.tools ∩ bot.tools` | `botctl profile <bot> --tools get_secret` (owner/admin), and the bot itself must have the tool |
| 403 "this bot instance has no helix-org tools" | Same as above | Same as above |
| Bot says "there is no Acme CRM in this workspace", with zero browser calls | `zed_agent` harness lost AGENTS.md after a clear or new thread (open bug) | Use `opencode` or `deepseek_harness` |
| Answers fast and confidently with no tool calls | Instructions missing, or the model is guessing | Check `logs` for AGENTS.md. Add "Never guess; if you can't find it, say so" and near-miss eval cases |
| Uses `curl` or `bash` instead of the browser | Browser MCP missing or broken (headless without Chrome), or the prompt allows it | Check `mcp_servers` has `chrome-devtools`. Add "use the browser tools, not curl". Add `tools_forbid: ["bash"]` to evals |
| "The browser is already running for …/.chrome-state" | Several browser MCP servers on one Chrome profile (older images; DeepSeek Harness or Goose threads) | Newer images share one Chrome (`--browserUrl`). New instance. The prompt should say: on 2 browser errors, open `new_page`, retry once, then stop. Never kill Chrome |
| `Target closed` / no browser on headless | Old image launched Chrome with the Wayland flag | Update the image. Workaround: `ubuntu-desktop` |
| DSH turn fails instantly: `agent session creation failed … mcp-client(helix-desktop) … failed` | DeepSeek Harness refuses `session/new` if any MCP server fails | Drop the failing server from the profile (`helix-desktop` on headless) |
| opencode: "Model tried to call unavailable tool" | MCP servers unreachable at opencode start, so tools were dropped for the session | Restart the sandbox or use a new instance |
| `OpenCode service failure: {"service":"session"}` | Bad or unavailable model | Check `llm-calls` for the provider error. Fix the model |
| `500 … 502 upstream unavailable` / thread load failed | Provider endpoint down, or a stale runtime binding after a harness switch | `helix provider list`. Restart the bot |
| Chat hangs about 5 min, then "external agent not ready" | Sandbox never connected. On billing stacks, often a wallet or subscription problem on a new org | `botctl doctor`, `sandbox_status_message`, org billing |
| "helix: desktop quota reached" | Too many desktop sandboxes | Use headless, or stop idle ones: `botctl rm <bot> --all --idle` |
| Instance `terminated_idle`, bot "forgot" it was logged in | Idle timeout (`HELIX_DESKTOP_IDLE_TIMEOUT`, default 1h). Browser state lost | Expected. The runbook should re-check login at the start of each run |
| Customer file "Access denied" or 403 inside the instance | Filestore and artifact URLs need API access the instance key doesn't have. Private networks are unreachable | `botctl put <sid> file` or gateway attachments |
| 403 "this bot instance key is scoped to its own sandbox…" (server log "Bot instance key denied") | The agent tried the Helix API from an instance | By design. Don't design instance flows that call the Helix API |
| Git push fails from an instance | Instance keys are fetch-only on their project's repos | Push from a main session or a human key |
| 403 "this app API key may only chat in sessions of its own app" | Gateway key used on another bot's session | Use that bot's key |
| 403 "path not allowed for app API keys" | App keys only reach `/sessions/chat` and `/v1/chat/completions` | Use a user key for everything else |
| 400 "a new bot chat requires exactly one message" / "attachment … must be a base64 data: URL" | Gateway validation | One message; inline `data:` URLs only |
| 400 `cannot unmarshal string into … MessageContent` | `content` sent as a plain string | `{"content_type":"text","parts":[…]}` |
| 400 "invalid instance profile" | Bad `sandbox_runtime`, `helix` in `mcp_servers`, or an unknown tool | Fix the profile |
| 403 "only organization owners and administrators can …" | Non-default tools, instance tools, secrets, assets or org settings | Needs an org owner or admin key |
| Duplicate or out-of-order replies in operator channels | `preserve_context:false` bots re-run on re-delivered events | Tell the bot to ACK duplicates. Don't loop two bots on one channel |
| Eval judge always fails with an empty reason | Judge pointed at the bot's app (its prompt replaced the grading instructions), or a reasoning-only reply | Use the neutral judge app (`assets/judge-agent.yaml`) |

## Where things live inside a sandbox

| What | Path |
|---|---|
| Instructions | `~/work/AGENTS.md`, `~/work/CLAUDE.md` (root-owned; rewritten on activation) |
| Customer files | `~/work/incoming/` |
| Bot repo | `~/work/<bot>-<project>/`; repo skills in `.agents/skills/` |
| Skills linked | `~/.agents/skills/`, `~/.claude/skills/`; `HELIX_SKILLS` env |
| Setup | `~/.helix-setup.log`; failure marker `~/.helix-setup-failed` |
| Zed / ACP | `~/.local/share/zed/logs/Zed.log` (routine lines contain "error"; look for patterns, not counts) |
| opencode | `~/work/.opencode-state/opencode/log/*.log` |
| Chrome | `/tmp/helix-chrome.log`; profile `~/work/.chrome-state`; debug port 9222 |
| Env | `HELIX_API_URL`, `USER_API_TOKEN` (the sandbox key), `HELIX_SESSION_ID`, `HELIX_WORKER_ID`, `HELIX_PROJECT_ID` |

## Measuring speed

- Per turn: `botctl turns` gives the wall time and tool count.
- Cost and latency split: `GET /api/v1/agents/<legacy_app_id>/llm-calls?session=<sid>`
  (prompt tokens, `time_to_first_token_ms`, `duration_ms`).
- A warm turn splits roughly into prefill 38%, decode 27%, tools/harness 30% and Helix 5%.
  Turn time is set by the number of LLM round trips, so cut round trips first: direct URLs,
  one `fill_form`, scripted `evaluate_script` fetch loops. Trimming the prompt barely helps
  once it's prefix-cached.
