# Troubleshooting bots and instances

Start with `helix org bots doctor <bot> [<session_id>]`. It lints the config (harness traps,
profile/tool mismatches, prompt vs profile) and, with a session, checks the sandbox (AGENTS.md,
linked skills, browser processes, last turn). Then narrow down with the workflow below.

## Workflow

1. **Is it the config?** Run `helix org bots get <bot>`. Check the harness, model, provider,
   `instance_profile`, and whether `restart_required` is set.
2. **Did the turn happen?** Run `helix session turns <sid>`. For each turn you get its state, the
   error, every tool call with its status, and the final text.
   - `waiting` for a long time: the agent is working or stuck. Run `helix session watch <sid>`.
   - `error`: the error string is in the header line. Match it against the table below.
   - `complete` but the answer is wrong: read the tool calls. Did it open the right page, did
     the login fail, did it guess? That is usually a prompt problem, not a platform one.
3. **Is the sandbox healthy?** Run `helix session logs <sid>`. It shows processes, the browser MCP
   count, workspace and `incoming/`, `AGENTS.md`, skills, the setup log, Zed errors, and the
   opencode and Chrome logs.
4. **What is on screen?** For desktop runtimes, run `helix session screenshot <sid>`. For headless ones, ask
   the bot to `take_snapshot` and report.
5. **Reproduce on a fresh instance** with `helix org instances ask <bot> "<the failing request>" --tools`.
   If it only fails on the old instance, the cause is state: an old prompt snapshot, an expired
   login, a browser lock, or an idle-terminated sandbox.
6. **Make it permanent.** Add the failing request to the eval suite before you fix it, then
   confirm the suite passes afterwards.

## Symptoms

| Symptom | Likely cause | Fix |
|---|---|---|
| Prompt change has no effect | Instances snapshot the prompt at creation. Main session: the change lands at the next activation or restart | New instance. `helix org bots restart <bot>` or `apply-config` for the main session |
| Profile change has no effect | Applies at the instance's next sandbox start | New instance |
| New tool not visible to a running main session | Harness caches `tools/list` at startup | Restart the sandbox |
| Instance has no `get_secret` or other helix tools | Default profile `tools: []`; served = `profile.tools ∩ bot.tools` | `helix org bots profile <bot> --tools get_secret` (owner/admin), and the bot itself must have the tool |
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
| Chat hangs about 5 min, then "external agent not ready" | Sandbox never started or never connected. `helix sandbox list` shows it `failed` / "desktop start failed". Causes seen: Hydra disk nearly full (API log: `hydra API error (status 507) … disk space critically low … minimum 2%`), desktop quota, wallet/subscription on a new org | `helix org instances create --wait` fails fast with the status. `docker logs <api> \| grep "Failed to start bot instance sandbox"` for the cause. Free space on the Hydra host (old `helix-ubuntu` images, unused volumes) |
| "helix: desktop quota reached" | Too many desktop sandboxes | Use headless, or stop idle ones: `helix org instances delete <bot> --all --idle` |
| Instance `terminated_idle` mid-work, `session exec` → "sandbox container not found" | Idle timeout: headless `HELIX_COMPUTE_IDLE_TIMEOUT` (default **10 min**), desktop `HELIX_DESKTOP_IDLE_TIMEOUT` (1h). Only agent activity counts — your `session exec` probing doesn't | `POST /api/v1/sessions/<sid>/resume` (or send a message). Chrome's profile is in `~/work/.chrome-state`, so web logins usually survive; Chrome comes back ~1 min after resume, when the browser MCP starts. The runbook should re-check login, not assume it's gone |
| Customer file "Access denied" or 403 inside the instance | Filestore and artifact URLs need API access the instance key doesn't have. Private networks are unreachable | `helix session put <sid> file` or gateway attachments |
| 403 "this bot instance key is scoped to its own sandbox…" (server log "Bot instance key denied") | The agent tried the Helix API from an instance | By design. Don't design instance flows that call the Helix API |
| Git push fails from an instance | Instance keys are fetch-only on their project's repos | Push from a main session or a human key |
| 403 "this app API key may only chat in sessions of its own app" | Gateway key used on another bot's session | Use that bot's key |
| 403 "path not allowed for app API keys" | App keys only reach `/sessions/chat` and `/v1/chat/completions` | Use a user key for everything else |
| 400 "a new bot chat requires exactly one message" / "attachment … must be a base64 data: URL" | Gateway validation | One message; inline `data:` URLs only |
| 400 `cannot unmarshal string into … MessageContent` | `content` sent as a plain string | `{"content_type":"text","parts":[…]}` |
| 400 "invalid instance profile" | Bad `sandbox_runtime`, `helix` in `mcp_servers`, or an unknown tool | Fix the profile |
| 403 "only organization owners and administrators can …" | Non-default tools, instance tools, secrets, assets or org settings | Needs an org owner or admin key |
| Duplicate or out-of-order replies in operator channels | `preserve_context:false` bots re-run on re-delivered events | Tell the bot to ACK duplicates. Don't loop two bots on one channel |
| Picklist readback is an id like `a2O5q000000kCQOEA2` | Salesforce/LWC record-id picklists: `lightning-combobox.value` is the record id | Read the label on the combobox trigger button (page libraries should compare labels) |
| Form save fails silently after a "successful" fill | A value the portal rejects on save (e.g. Emirates ID with dashes, phone with leading 0) | Put data formats in the prompt/library (digits only, local numbers); readback won't catch it — save does |
| Bot concludes an option "isn't in the list" | Its option scanner found nothing (options live in nested shadow roots with empty outer text) | Check the list yourself before trusting it; page libraries read option text through shadow roots |
| A call suddenly reads 0 cached tokens (TTFT 8–10 s instead of ~3) | The model server evicted the prompt cache — another client's huge context on a shared GPU. Harness requests are append-only, so it's not the bot | Diff consecutive requests in `llm_calls` (`request` jsonb): same prefix + 0 cached = server eviction. `helix session usage --calls` shows which calls. Fix at the provider (KV capacity, host-memory cache) or move big-context bots elsewhere |
| Desktop and headless instances of one bot don't share cache | Different tool lists (e.g. `helix-desktop` adds 17 tools) change the rendered prompt | Keep instance profiles identical; drop MCP servers the bot doesn't call |
| `DOM.setFileInputFiles` does nothing (no upload starts) | Same file name as the input already holds (no `change` fired), or the browser user can't read the file (root-owned 0700 temp dir) | Dispatch `change` on the input if nothing started; make the file world-readable |
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

- Per turn: `helix session turns` gives the wall time and tool count.
- Tokens, cost, latency and cache hits per turn and per call: `helix session usage <sid>` (`--calls`
  for every LLM call).
- Startup: a headless instance calls the model ~2.7 s after the first message; a desktop one ~17 s
  (it waits for the Zed window). Headless Chrome works for full flows; set a normal user agent
  (`chrome-devtools_emulate`) — it reports `HeadlessChrome` otherwise.
- A warm turn splits roughly into prefill 38%, decode 27%, tools/harness 30% and Helix 5%.
  Turn time is set by the number of LLM round trips, so cut round trips first: direct URLs,
  one `fill_form`, scripted `evaluate_script` fetch loops. Trimming the prompt barely helps
  once it's prefix-cached.
