---
name: helix-bot-builder
description: Build, configure, troubleshoot and evaluate helix-org bots (org agents) — especially customer-facing support bots that run as limited-permission bot instances behind an app-key gateway. Covers writing the bot's prompt and runbook, choosing harness/model/sandbox, instance profiles, creating and chatting with instances, delivering files, reading what a bot did, diagnosing stuck or wrong bots, and running graded eval suites (deterministic checks, LLM judge, simulated customers) to compare prompt or model changes. Use when the user wants to create or improve a Helix bot, test a bot, debug a bot/instance, set up a support bot for end customers, or asks how chief-of-staff style bots should be built.
---

# Helix bot builder

A **bot** is a helix-org org agent: instructions (`content`) + a harness (`code_agent_runtime`) +
a model + helix-org tools + its own project/repo, running in a sandbox. This skill is the loop
for making one good: **brief → configure → smoke → eval → fix → ship → monitor**, driven by two
stdlib-only scripts that work from a laptop or from inside a Helix sandbox (chief-of-staff).

Read [helix-cli](../helix-cli/SKILL.md) for auth basics. REST details are in
[references/api.md](references/api.md), failure modes in
[references/troubleshooting.md](references/troubleshooting.md), eval suites in
[references/evals.md](references/evals.md), prompt patterns in
[references/prompts.md](references/prompts.md).

```bash
export HELIX_URL=https://helix.example.com HELIX_API_KEY=hl-… HELIX_ORG=my-org
S=<this skill dir>/scripts            # e.g. ~/.agents/skills/helix-bot-builder/scripts
$S/botctl.py ls                       # bots, status, harness, model, sandbox
$S/botctl.py doctor <bot>             # config lint: harness traps, profile/tool mismatches
```

Inside a Helix sandbox the scripts pick up `HELIX_API_URL`/`USER_API_TOKEN` automatically; set
`HELIX_ORG`. The session key of a *main* bot session can drive every command here; an
*instance* key cannot (it is sandbox-scoped — see below).

## Mental model: bot, main session, instance, gateway

| | Main bot session | Bot instance | Gateway chat |
|---|---|---|---|
| What | The bot's one exploratory session; the org's internal worker | Extra session sharing the bot's identity, own sandbox — **one per end customer** | `POST /api/v1/sessions/chat` with an **app key** bound to the bot's app |
| Started by | `start`/`restart`, triggers, DMs, `chat` channels | `botctl new`, `create_bot_instance`, REST `POST …/instances` | First message without `session_id` creates an instance |
| AGENTS.md | helix-org preamble + prompt | **prompt verbatim** | = instance |
| helix-org tools | the bot's `tools` | `instance_profile.tools ∩ bot.tools` (default **none**) | = instance |
| MCP servers | all (browser, desktop, session, kodit, project MCPs) | `instance_profile.mcp_servers` (default `chrome-devtools` only) | = instance |
| API key in sandbox | full session key (owner's reach) | `bot_instance` key: LLM proxy + own session plumbing + read-only git; **403 on the rest of the API** | = instance |
| First turn | ~11 s activation turn, then work | **no activation turn**; cold chat ≈ 6–8 s | ≈ 7 s cold incl. instance create |
| Transcript | mirrored to `s-transcript-<bot>` (`bot_log`) | **not mirrored** — read `/sessions/{id}/interactions` | + `bot_instance.turn_completed` webhook |

Use the main session for operator/internal work (chief-of-staff delegating, triggers). Use
**instances** for anything customer-facing and for testing: they are fast, isolated, minimal,
and every new one runs the *current* prompt.

## The build loop

### 1. Brief
Before creating anything, pin down: who talks to the bot (internal staff vs end customers), the
systems it touches (web portals → browser; APIs → project MCP/OpenAPI), what it may **change**
vs only read, what needs a human (OTP codes, final submit), and 5–10 concrete example requests
with the exact answers you expect. Those examples become the eval suite in step 5 — write them
down now.

### 2. Choose harness, model, sandbox
Measured on the browser-support eval (12 questions, self-hosted models; see references/evals.md):

| Harness (`code_agent_runtime`) | Verdict |
|---|---|
| `opencode` + `glm-5.3-flash` | **Default.** 12/12, fast, stable |
| `deepseek_harness` + `glm-5.3-flash` | 12/12, often fastest; fails `session/new` if any MCP server fails to start |
| `qwen_code` | correct but ~3× the tokens and slower |
| `zed_agent` | **avoid for bots** — loses AGENTS.md after every clear/new thread (open bug) |
| `goose_code` | avoid — extra side calls, historically leaked browser MCP servers |
| `claude_code` / `codex_cli` | vendor models only (subscription or vendor key) |

GLM beat Qwen on every harness. Instances: prefer `headless-ubuntu` (no GPU, faster start);
use `ubuntu-desktop` only when a human must watch/drive the browser (`botctl shot` needs it).

### 3. Write the prompt
Support-bot prompts that work are **runbooks**, not personas: a numbered run sequence with call
budgets, per-system playbooks (login steps, URL patterns, field glossary), stop criteria, and a
hard gate before any mutating action. Details, measured effects and a template:
[references/prompts.md](references/prompts.md) and `examples/support-bot.prompt.md`.
Short core prompt + one repo skill per customer system scales best (skills live in the bot
project's primary repo under `.agents/skills/<name>/SKILL.md` and are linked into instances too).

### 4. Create / update from a spec
Keep the bot as code: a JSON spec plus a prompt file, applied idempotently.

```bash
$S/botctl.py export dubai-broker -o bots/dubai-broker.json   # snapshot an existing bot
$S/botctl.py apply bots/support-acme.json --dry-run            # shows create vs changed fields
$S/botctl.py apply bots/support-acme.json
$S/botctl.py profile support-acme --runtime headless-ubuntu --mcp chrome-devtools --tools ""
```

`examples/support-bot.json` is a starting spec. Creating a bot merges your `tools` with the
default worker set; **PATCH `tools` replaces the list** (apply warns what it removes). Granting
anything beyond the default set, or any tool to instances, needs an org owner/admin. Prompt-only
edits: `botctl prompt <bot> -f prompt.md`.

### 5. Smoke, then eval
```bash
$S/botctl.py ask support-acme "What's the balance on account BA-10694?" --tools   # new instance, 1 turn, deleted
SID=$($S/botctl.py new support-acme --name "manual test")
$S/botctl.py say $SID "Hi, I need to register my agency" --attach ./license.pdf
$S/botctl.py turns $SID            # every turn: tools called, timings, final text
$S/botctl.py rm support-acme $SID

$S/bot_eval.py run evals/support-acme.eval.json --parallel 3 --keep-failed
$S/bot_eval.py compare runs/before.jsonl runs/after.jsonl
```

An eval suite is JSON: cases with one or more turns, graded by `must`/`must_not` patterns,
latency and tool-call budgets, required/forbidden tools, an LLM `judge` rubric, or a
`simulate`d customer driven by an LLM. Each case gets a fresh instance. Format, judge setup and
reading results: [references/evals.md](references/evals.md); example:
`examples/support-lookup.eval.json`. Always include negative cases — near-miss names that must
come back "not found", credential requests, prompt injection — the smoke run of that example
caught a bot reading its CRM passcode back to a "new admin".

### 6. Fix → re-run
Read failures with `botctl turns <sid>` on the kept instance, change the prompt (or profile, or
harness), **create new instances** (existing ones keep the old prompt), re-run the same suite
with a new `--tag`, and `compare`. Judge speed on totals over ≥10 cases: replicate runs vary
±25–50% in time and tokens.

### 7. Ship to customers (gateway)
```bash
KEY=$($S/botctl.py appkey support-acme create acme-portal)     # app key bound to the bot's app
$S/botctl.py gw "$KEY" "Hi, what documents do you need?"       # prints reply + new session id
$S/botctl.py gw "$KEY" "here it is" --session ses_… --attach eid.png
$S/botctl.py hooks add https://portal.example.com/helix-hook   # bot_instance.turn_completed (org owner)
```
Your backend holds the app key and maps each customer to their `session_id`. **Never ship the
app key to a browser**: an app key can chat into *any* instance of its bot, so the session id is
the only tenant boundary (verified). Attachments must be inline base64 `data:` URLs; they land
in `~/work/incoming/` with a manifest in the message.

Both the blocking reply and the webhook's `response` are the **whole turn** — `<thinking>`,
`**Tool Call:**` blocks and raw page snapshots — not just the answer. Strip before showing a
customer (`last_segment()` in `scripts/_helix.py` is a best-effort cut); with a user key, the
clean answer is the last `text` entry of the interaction.

### 8. Monitor
`botctl instances <bot>` (status: `running`, `terminated_idle` after `HELIX_DESKTOP_IDLE_TIMEOUT`,
default 1h — browser logins are lost), `botctl turns`/`watch <sid>`, `botctl doctor <bot> <sid>`,
and `botctl rm <bot> --all --idle` to clean up. Re-run the eval suite nightly against the real
systems; portals change under you.

## Rules that bite

1. **Instances copy the prompt at creation.** After `prompt`/`apply`, test on a *new* instance.
   Profile changes apply at each instance's next sandbox start; main-session changes to prompt,
   tools or sandbox need `restart` (fresh session) or `apply-config` (keeps the session).
2. **Chat body shape**: `messages[].content` is `{"content_type":"text","parts":[…]}` — a plain
   string is a 400. A new instance via the gateway takes exactly one message.
3. **Interactions are paged from 0** (`page=1` is the second page) and lag the chat reply by a
   moment; the scripts poll until the turn settles.
4. **Instances have no helix-org tools by default**, so no `get_secret`. Either grant it
   (`profile --tools get_secret`, and the bot must have it) or inline credentials — which the
   eval above showed can leak. Prefer per-customer secrets over shared service logins.
5. **Getting files into an instance**: `botctl put <sid> file` (sandbox files API, lands
   root-owned 0644 in `~/work/incoming/`) or gateway attachments. Filestore links, artifact
   downloads and public artifact URLs do **not** work from instances (instance key is scoped;
   sandboxes can't reach private networks).
6. **Human steps** (OTP, "submit"): the bot asks, the customer pastes the code into chat. Don't
   give a bot someone's mailbox; in operator testing, relay codes through chat yourself.
7. A Helix app's own system prompt replaces a request's system message — the eval judge uses a
   neutral judge app (`assets/judge-agent.yaml`), never the bot's app.

## Driving bots from inside helix-org (chief-of-staff)

A manager bot builds bots with its MCP tools; the scripts cover the rest from its sandbox.

| Step | MCP tool (owner set) | Script / REST |
|---|---|---|
| Create | `create_bot {id,name,content,tools,parentId}` | `botctl apply` |
| Prompt | `set_bot_content` | `botctl prompt -f` |
| Tools | `attach_tool` / `detach_tool` | `apply` (tools list) |
| Instances | `create_bot_instance {bot_id,name,sandbox_runtime,message}`, `list_bot_instances`, `delete_bot_instance` | `botctl new / instances / rm` |
| Talk to an instance | — | `botctl say <sid>` (or `helix chat --session <sid>`) |
| Read an instance | — | `botctl turns <sid>` |
| Read the main session | `bot_log {botId}` | `botctl turns <session_id>` |
| Lifecycle | `start_bot` / `stop_bot` / `restart_bot` | `botctl start|stop|restart|apply-config` |

Tool grants to a running main session reach the agent only after a sandbox restart (the
harness caches `tools/list`), despite what the default chief-of-staff prompt says.
