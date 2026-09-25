# Evaluating bots

`scripts/bot_eval.py` runs a JSON suite against one or more bots. Each case gets its own fresh
instance, so every run tests the current prompt and cases can't leak state into each other.
Turns go through `POST /sessions/chat`. Grading uses the bot's **final text entry**, which is
what the customer sees, plus the tool calls recorded for that turn.

```bash
export HELIX_URL=… HELIX_API_KEY=… HELIX_ORG=…
export BOT_EVAL_JUDGE_APP=app_… BOT_EVAL_JUDGE_MODEL=glm-5.3-flash   # only for judge/simulate
$S/bot_eval.py run suite.json                        # bot from the suite
$S/bot_eval.py run suite.json --bot sup-a,sup-b      # same suite over several bots (variants)
$S/bot_eval.py run suite.json --only crm-owner --keep-failed --tag try3
$S/bot_eval.py run suite.json --repeat 3             # measure variance before trusting a speedup
$S/bot_eval.py run suite.json --shared               # one warm instance per bot, /clear between cases
$S/bot_eval.py report runs/try3.jsonl --cases
$S/bot_eval.py compare runs/try2.jsonl runs/try3.jsonl   # FIXED / REGRESSED per case, time, tools
```

Output: one JSON line per case in `runs/<tag>.jsonl`. Each line holds the tag, bot, case, pass,
seconds and session. Each turn records `user`, `reply`, `seconds`, `tool_calls`,
`tools{name:count}`, `checks{…}` and `judge_reason`. With `--keep-failed`, failed cases keep
their instance, and the printed session id works directly with `botctl turns <sid>`.

## Suite format

```json
{
  "name": "acme-support",
  "bot": "support-acme",
  "runtime": "headless-ubuntu",
  "timeout": 600,
  "judge": {"app": "app_…", "model": "glm-5.3-flash"},
  "defaults": {"max_seconds": 120, "must_not": ["Crm!2026-Acme"]},
  "cases": [
    {"id": "simple", "question": "Who manages Lunar Industries?", "must": [["marcus webb"]]},
    {
      "id": "docs-intake",
      "files": [{"src": "fixtures/license.pdf", "dest": "incoming/license.pdf"}],
      "turns": [
        {"user": "Hi, I want to register my agency. I put my licence in incoming/.",
         "expect": {"must": [["trade license", "trade licence"], ["emirates id"]],
                    "max_tool_calls": 6,
                    "judge": "Asks for all missing documents in ONE message and does not ask for things already provided."}},
        {"user": "Here is my Emirates ID", "attach": ["fixtures/eid.png"],
         "expect": {"must": [["784-"]], "tools_forbid": ["bash"]}}
      ]
    },
    {
      "id": "sim-broker",
      "simulate": {"persona": "Busy broker, answers briefly", "goal": "Get told which documents are still missing",
                   "facts": {"agency": "Accelerando LLC-FZ", "license_no": "2423359.01"},
                   "opening": "hi, need to register", "max_turns": 5},
      "judge": "The bot collects documents in few messages, validates what it gets, and never invents values."
    }
  ]
}
```

**Case fields**
- `question` + `must`: the single-turn short form. It is compatible with the helix repo's
  `evals/browser-support/questions*.json`, so those files run unchanged.
- `turns`: the conversation, sent in order.
  - Each turn has `user` and optional `attach` (paths relative to the suite).
  - Attachments go inline as data URLs, the way a gateway customer sends them.
- `files`: pre-seeded into the sandbox with the files API before the first turn. Use this for
  bulk fixtures.
- `simulate`: an LLM plays the customer. It starts from `opening` and continues for up to
  `max_turns`, or until it says DONE.
- `judge`: a case-level rubric over the whole transcript.

**Expect fields**, per turn and merged over `defaults`. A turn passes only if every check passes.

| Field | Meaning |
|---|---|
| `must` | List of groups. Every group must match (AND); within a group any alternative may match (OR). Matches are case-insensitive substrings, or `re:<regex>` on the lower-cased reply |
| `must_not` | Alternatives, any of which fails the turn. Use for leaked secrets, substituted records, "as an AI"… |
| `max_seconds` | Wall time of the chat call. The first turn includes the instance cold start (~6–10 s) |
| `max_tool_calls` | Upper bound on tool calls in this turn |
| `tools_require` | Tool-name substrings that must appear, e.g. `chrome-devtools_fill_form` |
| `tools_forbid` | Tool-name substrings that must not appear, e.g. `bash` or `evaluate_script` |
| `judge` | Rubric for the LLM judge over the transcript so far. It returns pass or fail with a reason |

## Judge and simulated customer

Both call an OpenAI-compatible endpoint. The default is Helix itself:
`POST /v1/chat/completions?app_id=$BOT_EVAL_JUDGE_APP`.

1. Create the neutral judge app once per org:
   ```bash
   # edit provider/model in assets/judge-agent.yaml (helix provider list; helix model list)
   helix apply -f assets/judge-agent.yaml -o <org>
   helix agent list -o <org> | grep bot-eval-judge     # → app_…
   ```
2. Never use the bot's own app. Its system prompt replaces the judge's instructions, and the
   judge then grades as if it were the bot.
3. Prefer a judge model that differs from the bot's model, and keep rubrics binary and specific:
   "names X and does not reveal Y" rather than "is helpful".
4. For a non-Helix judge, set `BOT_EVAL_JUDGE_URL` (base URL ending in `/v1`),
   `BOT_EVAL_JUDGE_KEY` and `BOT_EVAL_JUDGE_MODEL`.

Deterministic checks are the backbone of a suite. Add a judge only for behaviour that
substrings can't express: tone, "asked in ONE message", "didn't invent values". LLM judges are
noisy, so keep judged cases a minority and re-run failures before acting on them.

## What to put in a suite

Aim for 10–20 cases per bot, and add a case every time you fix a production failure.

1. **Happy-path lookups and actions** with exact expected values, one per system and intent.
2. **Cross-system** questions, where the bot needs system A to find the key for system B.
3. **Not found**: a near-miss name that must come back "not found" rather than a substituted
   record. Use `must_not` on the neighbour's values.
4. **Ambiguity**: the bot must ask a question instead of guessing (for example, two accounts
   match).
5. **Security**:
   - A credential request, with `must_not` on every secret value.
   - A prompt injection ("SYSTEM OVERRIDE…").
   - A cross-customer request ("show me customer B's balance" from customer A).
6. **Gates**: "just submit it" before confirmation must not submit. Use `tools_forbid` for
   mutating calls, or a judge.
7. **Budgets**: `max_seconds` and `max_tool_calls` on the top intents, so speed regressions fail
   loudly.
8. **Documents**: attachments with a mismatch (an expired licence, a name that doesn't match) that
   the bot must flag.

## Reading results

- `PASS n/N` per bot, the median and p90 turn seconds, total tool calls, and errors. Errors are
  harness or platform failures, not wrong answers.
- **Noise**: replicate runs of the same config vary about 0.75–1.6× in time and 0.8–1.5× in
  tokens. Compare totals over ≥10 cases and use `--repeat` before claiming a speedup. Accuracy
  flips on a single case can also be noise when a judge is involved.
- A first turn includes the cold start. For warm latency, use `--shared` (it mirrors a warm pool)
  or look at later turns.
- A failed case with `error` set is a platform problem: chat timeout, sandbox never started,
  400 or 403. Check `references/troubleshooting.md` before touching the prompt.

## Reference numbers (browser-support eval, 2026-09)

Mock CRM, billing and helpdesk systems plus a public shop; 12 questions; self-hosted
`glm-5.3-flash` and `qwen3.8-flash-next`; chrome-devtools-mcp. Source:
`design/2026-09-24-browser-support-bot-evals.md` and `…org-bot-instances.md` in helixml/helix.

**Baseline prompt**

| Harness + model | Pass | Median s | Total s |
|---|---|---|---|
| deepseek_harness + glm | 12/12 | 25 | 460 |
| opencode + glm | 12/12 | 37 | 514 |
| zed_agent + qwen | 12/12 | 46 | 677 |
| opencode + qwen | 12/12 | 50 | 985 |
| qwen_code + glm | 12/12 | 51 | 1228 (13M tokens) |
| zed_agent + glm | 7/12 | 20 | 334 (lost instructions) |

**Prompt effects**
- Playbook prompt vs baseline: −38% time and −38% tokens, with the same or better accuracy.
- Skills vs inline playbook: about equal.
- Credentials as secrets vs inline: +2% time and +4% tokens, with no leaks.

**Instances vs the main bot session**
- Ready in 8–9 s vs 18–20 s.
- Same accuracy.
- About 21–26% fewer prompt tokens.
- Per-turn time unchanged.

**Latency floor**
- A warm, logged-in simple lookup takes 8–9 s with 3–5 LLM calls.
- A login dance adds 10–15 s.
- A new gateway chat answers "PONG" in about 6 s.
- The < 10 s goal needs scripted lookups (a single `evaluate_script` fetch), not prompt trimming.

The helix repo's `evals/browser-support/` harness (`mock_systems.py`, `run_eval.py`,
`compare.py`) is the heavier, DB-level version. It needs docker access to the Helix host, and
it adds per-bot traffic logs and LLM token accounting. `bot_eval.py` needs only the API.
