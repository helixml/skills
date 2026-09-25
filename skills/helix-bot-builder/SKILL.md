---
name: helix-bot-builder
description: Build, configure, troubleshoot and evaluate helix-org bots (org agents) — especially customer-facing support bots that run as limited-permission bot instances behind an app-key gateway. Covers writing the bot's prompt and runbook, shipping tested page/form libraries as repo skills, choosing harness/model/sandbox, instance profiles, creating and chatting with instances, delivering files, reading what a bot did, diagnosing stuck or wrong bots, and running graded eval suites (deterministic checks, LLM judge, simulated customers) with the helix CLI. Use when the user wants to create or improve a Helix bot, test a bot, debug a bot/instance, set up a support bot for end customers, or asks how chief-of-staff style bots should be built.
---

# Helix bot builder

A **bot** is a helix-org org agent: instructions (`content`) + a harness (`code_agent_runtime`) +
a model + helix-org tools + its own project/repo, running in a sandbox. This skill is the loop
for making one good — **brief → configure → smoke → eval → fix → ship → monitor** — driven by
the `helix` CLI (`helix org bots|instances|eval`, `helix session`).

Read [helix-cli](../helix-cli/SKILL.md) for auth. REST details: [references/api.md](references/api.md);
failure modes: [references/troubleshooting.md](references/troubleshooting.md); eval suites:
[references/evals.md](references/evals.md); prompt and page-library patterns:
[references/prompts.md](references/prompts.md).

```bash
export HELIX_URL=https://helix.example.com HELIX_API_KEY=hl-… HELIX_ORG=my-org
helix org bots list
helix org bots doctor <bot>            # config lint: harness traps, profile/tool mismatches
```

> **CLI version.** `helix org instances`, `helix org eval`, `helix session` and
> `helix org bots apply|export|prompt|profile|doctor|appkey|apply-config|delete`, `helix org webhooks`
> are newer than the latest release ([helixml/helix#3298](https://github.com/helixml/helix/pull/3298)). Check with `helix session --help`. On an older binary use the `helix api`
> forms in [references/api.md](references/api.md) — every command here maps to one or two REST calls.

Inside a Helix sandbox the CLI picks up `HELIX_API_URL`/`USER_API_TOKEN` automatically; set
`HELIX_ORG`. A bot's *main* session key can drive everything here; an *instance* key cannot
(it is sandbox-scoped — see below).

## Mental model: bot, main session, instance, gateway

| | Main bot session | Bot instance | Gateway chat |
|---|---|---|---|
| What | The bot's one exploratory session; the org's internal worker | Extra session sharing the bot's identity, own sandbox — **one per end customer** | `POST /api/v1/sessions/chat` with an **app key** bound to the bot's app |
| Started by | `helix org bots start/restart`, triggers, DMs | `helix org instances create`, `create_bot_instance` | First message without a session id creates an instance |
| AGENTS.md | helix-org preamble + prompt | **prompt verbatim**, copied at creation | = instance |
| helix-org tools | the bot's `tools` | `instance_profile.tools ∩ bot.tools` (default **none**) | = instance |
| MCP servers | all (browser, desktop, session, kodit, project MCPs) | `instance_profile.mcp_servers` (default `chrome-devtools`) | = instance |
| API key in sandbox | full session key | `bot_instance` key: LLM proxy + own session plumbing + read-only git; **403 elsewhere** | = instance |
| First turn | ~11 s activation turn, then work | **no activation turn**; cold chat ≈ 6–8 s | ≈ 7 s cold incl. instance create |
| Transcript | mirrored to `s-transcript-<bot>` (`bot_log`) | **not mirrored** — `helix session turns <sid>` | + `bot_instance.turn_completed` webhook |
| Skills | helix-* skills + repo `.agents/skills` | repo `.agents/skills` only (`helix_skills: false`) | = instance |

Use the main session for operator/internal work; use **instances** for anything customer-facing
and for testing — fast, isolated, minimal, and every new one runs the *current* prompt.

## The build loop

### 1. Brief
Pin down: who talks to the bot (staff vs end customers), which systems it touches (web portals →
browser; APIs → project MCP/OpenAPI), what it may **change** vs only read, which steps need a human
(OTP codes, final submit), and 5–10 concrete requests with the exact answers you expect — they
become the eval suite in step 5.

### 2. Choose harness, model, sandbox
Browser-support eval (12 questions, self-hosted models; references/evals.md):

| Harness (`code_agent_runtime`) | Verdict |
|---|---|
| `opencode` + `glm-5.3-flash` | **Default.** 12/12, fast, stable |
| `deepseek_harness` + `glm-5.3-flash` | 12/12, often fastest; fails `session/new` if any MCP server fails |
| `qwen_code` | correct but ~3× the tokens and slower |
| `zed_agent` | **avoid for bots** — loses AGENTS.md after every clear/new thread |
| `goose_code` | avoid — extra side calls, historically leaked browser MCP servers |
| `claude_code` / `codex_cli` | vendor models only |

Instances: `headless-ubuntu` (set `instance_profile.sandbox_runtime`) unless a human must watch
the browser (`--runtime ubuntu-desktop`, `helix session screenshot`) — the agent starts ~2.7 s after
the first message instead of ~17 s, and headless Chrome runs full logins and uploads. Keep
`mcp_servers` to what the bot calls (`helix-desktop` adds 17 unused tools per call). Sandboxes
stop after 10 idle minutes; resume with `POST /api/v1/sessions/<sid>/resume`.

### 3. Write the prompt — and ship the page knowledge as code
Support-bot prompts that work are **runbooks**: numbered steps with call budgets, data formats,
stop criteria, and a hard gate before anything that mutates. Details and a template:
[references/prompts.md](references/prompts.md), `examples/support-bot.prompt.md`.

For web portals, the biggest speed and reliability lever is **not** prompt text: explore the
page once, write a small tested JS library (`fill`, `scan`, `press`) and commit it as a repo skill
(`<bot repo>/.agents/skills/<system>/SKILL.md` + `fill.js`). The bot installs it with one
`evaluate_script` and fills a whole form in one call instead of re-discovering the DOM every run
(DHRE broker bot: 287 s → 124 s per login+fill, zero failed scripts). How to build and test one:
references/prompts.md → "Page libraries".

### 4. Keep the bot in git, deploy with apply
Give each bot a folder in a git repo — `bot.yaml` (spec), `prompt.md`, `skills/<name>/SKILL.md`
(+ page libraries), `evals/` — and deploy it with one idempotent command. Example layout:
[helixml/dubai-properties → bots/dubai-properties-broker](https://github.com/helixml/dubai-properties).

```bash
helix org bots apply -f bots/my-bot/bot.yaml --dry-run   # create, or which fields/skills change
helix org bots apply -f bots/my-bot/bot.yaml             # config + prompt, then skills → bot repo
```
`content_file` inlines the prompt; `skills_dir` pushes the skill folders into the bot project's
Helix repo (`.agents/skills/`, commit by "helix apply"), where every new instance links them;
`provider` may be the endpoint **name** (e.g. `ds4-flash-node06`) so specs work across
environments. Other commands:

```bash
helix org bots export dubai-broker -o bots/dubai-broker.yaml   # spec + dubai-broker.prompt.md
helix org bots apply -f bots/support-acme.yaml --dry-run        # create, or which fields change
helix org bots apply -f bots/support-acme.yaml
helix org bots prompt support-acme -f support-acme.prompt.md    # prompt only
helix org bots profile support-acme --runtime headless-ubuntu --mcp chrome-devtools --tools ""
```
`examples/support-bot.yaml` is a starting spec; `export` writes one (provider by name) plus the prompt. Create merges `tools` with the default worker set;
**updating `tools` replaces the list** (apply prints what it removes). Tools beyond the default
set, and any instance tools, need an org owner/admin.

### 5. Smoke, then eval
```bash
helix org instances ask support-acme "What's the balance on BA-10694?" --tools   # one-shot
SID=$(helix org instances create support-acme --name "manual test" --wait)
helix session put  $SID ./licence.pdf                      # → ~/work/incoming/licence.pdf
helix session send $SID "Hi, I need to register" --tools   # final message + tool summary
helix session turns $SID                                   # every turn: tools, timings, reply
helix org instances delete support-acme $SID

helix org eval run evals/support-acme.eval.yaml --parallel 3 --keep-failed
helix org eval compare runs/before.jsonl runs/after.jsonl
```
Suites: cases with one or more turns graded by `must`/`must_not` patterns, latency and tool
budgets, required/forbidden tools, an LLM `judge` rubric, or an LLM-`simulate`d customer; each
case on a fresh instance. See [references/evals.md](references/evals.md) and
`examples/support-lookup.eval.json`. Always include negative cases — near-miss names, credential
requests, prompt injection: the example suite caught a bot reading its CRM passcode to a "new
admin" in 1 of 3 runs.

### 6. Fix → re-run
Read failures with `helix session turns <sid>` on the kept instance; change prompt, profile,
page library or harness; **create new instances** (existing ones keep the old prompt); re-run
with a new `--tag`; `compare`. Judge speed on totals over ≥10 cases (±25–50% noise).

### 7. Ship to customers (gateway)
```bash
KEY=$(helix org bots appkey support-acme create acme-portal)
helix session send - "Hi, what documents do you need?" --key "$KEY"   # new instance; prints session id
helix session send ses_01… "here it is" --key "$KEY" --attach eid.png
helix org webhooks create https://portal.example.com/helix --events bot_instance.turn_completed
```
Your backend holds the app key and maps each customer to their `session_id`. **Never ship the
app key to a browser**: an app key can chat into *any* instance of its bot (verified).
Attachments go inline as base64 `data:` URLs and land in `~/work/incoming/`.

The blocking reply and the webhook `response` are the **whole turn** — `<thinking>`,
`**Tool Call:**` blocks, raw page snapshots. Strip before showing a customer; with a user key the
clean answer is the text after the interaction's last tool call (what `helix session send` prints).

### 8. Monitor
`helix org instances list <bot>` (`terminated_idle` after `HELIX_DESKTOP_IDLE_TIMEOUT`, default
1h — browser logins are lost), `helix session watch <sid>`, `helix org bots doctor <bot> <sid>`,
`helix org instances delete <bot> --all --idle`. Re-run evals nightly: portals change under you.

## Rules that bite

1. **Instances copy the prompt at creation.** Test prompt changes on a *new* instance. Profile
   changes apply at the next sandbox start; main-session prompt/tools/sandbox changes need
   `restart` (fresh session) or `apply-config` (keeps it). Repo skills are cloned at sandbox start.
2. **Chat body**: `messages[].content` is `{"content_type":"text","parts":[…]}` — a plain string is
   a 400. A new gateway chat takes exactly one message.
3. **Interactions page from 0** and lag the chat reply; a harness splits one answer across several
   text entries. `helix session send/turns` handle both.
4. **Instances have no helix-org tools by default** — no `get_secret`. Grant it
   (`profile --tools get_secret`, and on the bot) or inline credentials, which evals show can leak.
5. **Files into an instance**: `helix session put` (root-owned 0644 in `~/work/incoming/`) or
   gateway attachments. Filestore links and artifact URLs do **not** work from instances.
6. **Human steps** (OTP, "submit"): the customer pastes codes into chat. In operator testing read
   the *newest message* of the mail thread — thread rows show a stale code.
7. A Helix app's own system prompt replaces a request's system message — the eval judge uses a
   neutral judge app (`assets/judge-agent.yaml`), never the bot's app.
8. A sandbox that "failed to start" makes the first chat wait 5 min for "external agent not
   ready". `instances create --wait`/`ask`/`eval` fail fast with the sandbox status; the cause
   (disk space, desktop quota) is in the API log (`Failed to start bot instance sandbox`).

## Driving bots from inside helix-org (chief-of-staff)

| Step | MCP tool (owner set) | CLI |
|---|---|---|
| Create / update | `create_bot`, `set_bot_content`, `attach_tool`/`detach_tool` | `helix org bots apply -f` / `prompt -f` |
| Instances | `create_bot_instance`, `list_bot_instances`, `delete_bot_instance` | `helix org instances create/list/delete` |
| Talk to an instance | — | `helix session send <sid>` |
| Read an instance | — | `helix session turns <sid>` |
| Read the main session | `bot_log {botId}` | `helix session turns <session_id>` |
| Lifecycle | `start_bot` / `stop_bot` / `restart_bot` | `helix org bots start/stop/restart/apply-config` |
| Page libraries | — | clone the bot repo (`helix api /projects/<id>` → `default_repo_id`), push `.agents/skills/` |

Tool grants reach a running main session only after a sandbox restart (the harness caches
`tools/list`), whatever the default chief-of-staff prompt says.
