#!/usr/bin/env python3
"""bot_eval — run an eval suite against helix-org bot instances and grade it.

  bot_eval.py run suite.json [--bot a,b] [--tag T] [--parallel 3] [--repeat 1]
                             [--only case1,case2] [--shared] [--keep-failed] [--runtime R]
  bot_eval.py report runs/T.jsonl [--cases]
  bot_eval.py compare runs/A.jsonl runs/B.jsonl

Each case runs on a FRESH instance by default (the prompt snapshot is taken at
instance creation, so a fresh instance always tests the current prompt). Turns
are sent through POST /sessions/chat and graded with:

  must        list of groups; every group needs one alternative to match (AND of ORs).
              Case-insensitive substring, or "re:<regex>" on the lower-cased reply.
  must_not    alternatives that fail the turn if any matches (leaked secrets, "as an AI"…)
  judge       rubric string for an LLM judge (needs a judge app — see references/evals.md)
  max_seconds / max_tool_calls / tools_require / tools_forbid   (tool names match by substring)

A case may instead set "simulate" to let an LLM play the customer for up to
max_turns, then a case-level "judge" grades the whole transcript.
Results: runs/<tag>.jsonl (one line per case) + a summary table.
"""
import argparse
import json
import os
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helix import Helix, HelixError, strip_thinking, table, tool_calls  # noqa: E402

LOCK = threading.Lock()


# -- grading -----------------------------------------------------------------
def norm(s):
    return (s or "").lower().replace(" ", " ")


def alt_match(alt, text):
    return bool(re.search(alt[3:], text)) if alt.startswith("re:") else alt.lower() in text


def grade_turn(expect, reply, secs, calls):
    text = norm(reply)
    checks = {}
    if expect.get("must"):
        groups = [any(alt_match(a, text) for a in g) for g in expect["must"]]
        checks["must"] = all(groups)
        if not checks["must"]:
            checks["must_failed_groups"] = [expect["must"][i] for i, ok in enumerate(groups) if not ok]
    if expect.get("must_not"):
        hits = [a for a in expect["must_not"] if alt_match(a, text)]
        checks["must_not"] = not hits
        if hits:
            checks["must_not_hits"] = hits
    names = [c.get("tool_name") or "" for c in calls]
    if "max_seconds" in expect:
        checks["max_seconds"] = secs <= expect["max_seconds"]
    if "max_tool_calls" in expect:
        checks["max_tool_calls"] = len(calls) <= expect["max_tool_calls"]
    for t in expect.get("tools_require") or []:
        checks[f"uses:{t}"] = any(t in n for n in names)
    for t in expect.get("tools_forbid") or []:
        checks[f"avoids:{t}"] = not any(t in n for n in names)
    return checks


# -- LLM (judge + simulated customer) ----------------------------------------
class LLM:
    """OpenAI-compatible chat. Default: Helix /v1/chat/completions scoped by a neutral judge app
    (?app_id= gives the call an org for billing; a bot's app would inject the bot's prompt)."""

    def __init__(self, h, cfg):
        self.h = h
        self.app = cfg.get("app") or os.environ.get("BOT_EVAL_JUDGE_APP")
        self.model = cfg.get("model") or os.environ.get("BOT_EVAL_JUDGE_MODEL")
        self.url = cfg.get("url") or os.environ.get("BOT_EVAL_JUDGE_URL")
        self.key = os.environ.get("BOT_EVAL_JUDGE_KEY")

    @property
    def ok(self):
        return bool(self.app or self.url)

    def complete(self, system, user, temperature=0):
        # One user message: a Helix app's own system prompt REPLACES any system message we send.
        body = {"messages": [{"role": "user", "content": f"{system}\n\n{user}"}], "temperature": temperature}
        if self.model:
            body["model"] = self.model
        if self.url:
            import urllib.request
            r = urllib.request.Request(self.url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                       headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=180) as resp:
                d = json.loads(resp.read())
        else:
            d = self.h.req("POST", "/v1/chat/completions", body=body, query={"app_id": self.app}, timeout=180)
        return strip_thinking(d["choices"][0]["message"].get("content") or "")

    def judge(self, rubric, transcript):
        sys_p = ("You grade a support chatbot transcript against a rubric. Be strict: pass only if every "
                 "requirement in the rubric is met by the BOT's messages. Reply with one JSON object "
                 '{"pass": true|false, "reason": "<one sentence>"} and nothing else.')
        raw = self.complete(sys_p, f"RUBRIC:\n{rubric}\n\nTRANSCRIPT:\n{transcript}")
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            v = json.loads(m.group(0)) if m else {}
        except ValueError:
            v = {}
        if "pass" in v:
            return {"pass": bool(v["pass"]), "reason": v.get("reason", "")}
        word = re.search(r"\b(PASS|FAIL)\b", raw.upper())
        if word:
            return {"pass": word.group(1) == "PASS", "reason": raw[:200]}
        return {"pass": False, "reason": f"unparseable judge output: {raw[:200]}"}

    def customer(self, sim, transcript):
        sys_p = ("You are role-playing a CUSTOMER talking to a support bot, to test it. Stay in character.\n"
                 f"Persona: {sim.get('persona', 'a typical customer')}\nGoal: {sim.get('goal', '')}\n"
                 f"Facts you know (share only when asked): {json.dumps(sim.get('facts', {}))}\n"
                 "Write ONLY your next message to the bot, short and natural. If the goal is reached, the bot "
                 "is stuck/looping, or it asks for something you do not have, reply exactly DONE.")
        return self.complete(sys_p, f"Conversation so far:\n{transcript}\n\nYour next message:", temperature=0.4)


def render(turns):
    return "\n".join(f"CUSTOMER: {t['user']}\nBOT: {t['reply']}" for t in turns)


# -- running -----------------------------------------------------------------
def normalize_case(c, defaults):
    c = dict(c)
    if "question" in c and "turns" not in c:  # run_eval.py questions.json compatibility
        c["turns"] = [{"user": c["question"], "expect": {k: c[k] for k in ("must", "must_not") if k in c}}]
    for t in c.get("turns") or []:
        t["expect"] = {**defaults, **(t.get("expect") or {})}
    return c


def resolve(base, p):
    return p if os.path.isabs(p) else os.path.join(base, p)


def run_case(h, llm, suite, base, bot, case, args, shared_sid=None):
    rec = {"tag": args.tag, "suite": suite.get("name"), "bot": bot, "case": case["id"], "turns": [],
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    sid = shared_sid
    t_case = time.time()
    try:
        if not sid:
            inst = h.new_instance(bot, f"eval {args.tag} {case['id']}"[:60], args.runtime or suite.get("runtime"))
            sid = inst["session_id"]
        rec["session"] = sid
        for f in case.get("files") or []:  # pre-seed the workspace (bulk docs, fixtures)
            s = h.sandbox_for(sid, wait=180)
            if not s:
                raise RuntimeError(f"{sid}: sandbox never came up")
            dest = f["dest"] if f["dest"].startswith("/") else "/home/retro/work/" + f["dest"]
            with open(resolve(base, f["src"]), "rb") as fh:
                h.write_file(s["id"], dest, fh.read())
        timeout = case.get("timeout") or suite.get("timeout") or 900
        turns = list(case.get("turns") or [])
        sim = case.get("simulate")
        if sim:
            turns = [{"user": sim.get("opening", "Hi"), "expect": {}}]
        i = 0
        while i < len(turns):
            t = turns[i]
            attach = [resolve(base, p) for p in t.get("attach") or []]
            res = h.turn(t["user"], session_id=sid, attach=attach, timeout=timeout)
            reply, secs, last = res["reply"], res["seconds"], res["interaction"]
            calls = tool_calls(last)
            tools = {}
            for c in calls:
                tools[c.get("tool_name")] = tools.get(c.get("tool_name"), 0) + 1
            checks = grade_turn(t.get("expect") or {}, reply, secs, calls)
            tr = {"user": t["user"], "reply": reply[:4000], "seconds": round(secs, 1), "tool_calls": len(calls),
                  "tools": tools, "checks": checks, "state": (last or {}).get("state")}
            if (t.get("expect") or {}).get("judge") and llm.ok:
                j = llm.judge(t["expect"]["judge"], render(rec["turns"] + [tr]))
                tr["checks"]["judge"] = j["pass"]
                tr["judge_reason"] = j["reason"]
            tr["pass"] = all(v for k, v in tr["checks"].items() if isinstance(v, bool))
            rec["turns"].append(tr)
            if sim and len(rec["turns"]) < sim.get("max_turns", 6):
                nxt = llm.customer(sim, render(rec["turns"]))
                if nxt.strip().upper().rstrip(".") != "DONE":
                    turns.append({"user": nxt.strip(), "expect": {}})
            i += 1
        if case.get("judge"):
            if llm.ok:
                rec["judge"] = llm.judge(case["judge"], render(rec["turns"]))
            else:
                rec["judge"] = {"pass": None, "reason": "no judge configured (BOT_EVAL_JUDGE_APP)"}
        rec["pass"] = all(t["pass"] for t in rec["turns"]) and (rec.get("judge") or {}).get("pass") is not False
    except (HelixError, RuntimeError, OSError) as e:
        rec["pass"] = False
        rec["error"] = str(e)[:1000]
    rec["seconds"] = round(time.time() - t_case, 1)
    if sid and not shared_sid:
        if args.keep or (args.keep_failed and not rec["pass"]):
            rec["kept"] = True
        else:
            try:
                h.delete_instance(bot, sid)
            except HelixError:
                pass
    with LOCK:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        why = rec.get("error") or "; ".join(
            f"t{n + 1} {k}" for n, t in enumerate(rec["turns"]) for k, v in t["checks"].items() if v is False)
        if rec.get("judge") and rec["judge"].get("pass") is False:
            why += f" judge: {rec['judge']['reason']}"
        print(f"{'PASS' if rec['pass'] else 'FAIL'} {bot} {case['id']} {rec['seconds']}s "
              f"turns={len(rec['turns'])} tools={sum(t['tool_calls'] for t in rec['turns'])}"
              + (f" session={sid}" if rec.get("kept") else "") + (f"  ← {why}" if not rec["pass"] else ""), flush=True)
    return rec


def cmd_run(args):
    h = Helix(org=args.org)
    with open(args.suite) as f:
        suite = json.load(f)
    base = os.path.dirname(os.path.abspath(args.suite))
    defaults = suite.get("defaults") or {}
    cases = [normalize_case(c, defaults) for c in suite["cases"]]
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    bots = (args.bot or suite.get("bot") or "").split(",")
    if not bots[0]:
        sys.exit("no bot: set \"bot\" in the suite or pass --bot")
    args.tag = args.tag or f"{suite.get('name', 'eval')}-{time.strftime('%m%d-%H%M')}"
    args.out = args.out or os.path.join("runs", args.tag + ".jsonl")
    llm = LLM(h, suite.get("judge") or {})
    needs_llm = any(c.get("simulate") or c.get("judge") or any((t.get("expect") or {}).get("judge") for t in c.get("turns") or [])
                    for c in cases)
    if needs_llm and not llm.ok:
        print("warning: suite uses judge/simulate but no judge is configured — see references/evals.md", file=sys.stderr)
    print(f"tag={args.tag} bots={bots} cases={len(cases)} repeat={args.repeat} → {args.out}", flush=True)
    jobs = [(b, c) for _ in range(args.repeat) for b in bots for c in cases]
    if args.shared:
        for b in bots:  # one warm instance per bot, cleared between cases (mirrors a warm pool)
            sid = h.new_instance(b, f"eval {args.tag} shared", args.runtime or suite.get("runtime"))["session_id"]
            try:
                for _ in range(args.repeat):
                    for c in cases:
                        h.post(f"/sessions/{sid}/clear")
                        time.sleep(2)
                        run_case(h, llm, suite, base, b, c, args, shared_sid=sid)
            finally:
                if not args.keep:
                    h.delete_instance(b, sid)
    else:
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = []
            for n, (b, c) in enumerate(jobs):
                futs.append(ex.submit(run_case, h, llm, suite, base, b, c, args))
                if n < args.parallel:
                    time.sleep(2)
            for f in futs:
                f.result()
    report(args.out, per_case=True, tag=args.tag)


def load(path, tag=None):
    with open(path) as f:
        recs = [json.loads(line) for line in f if line.strip()]
    return [r for r in recs if not tag or r.get("tag") == tag]


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else 0


def report(path, per_case=False, tag=None):
    recs = load(path, tag)
    rows = []
    for bot in sorted({r["bot"] for r in recs}):
        rs = [r for r in recs if r["bot"] == bot]
        ts_ = [t["seconds"] for r in rs for t in r["turns"]]
        rows.append([bot, f"{sum(r['pass'] for r in rs)}/{len(rs)}", f"{statistics.median(ts_):.1f}" if ts_ else "-",
                     f"{pct(ts_, 0.9):.1f}" if ts_ else "-", sum(t["tool_calls"] for r in rs for t in r["turns"]),
                     sum(1 for r in rs if r.get("error"))])
    print()
    table(rows, ["BOT", "PASS", "MEDIAN TURN s", "P90 TURN s", "TOOL CALLS", "ERRORS"])
    if per_case:
        print()
        table([[r["bot"], r["case"], "✅" if r["pass"] else "❌", r["seconds"], len(r["turns"]),
                (r.get("error") or (r.get("judge") or {}).get("reason") or "")[:90]] for r in recs],
              ["BOT", "CASE", "OK", "s", "TURNS", "NOTE"])


def compare(a, b):
    A, B = load(a), load(b)
    key = lambda r: (r["bot"], r["case"])  # noqa: E731
    ia, ib = {key(r): r for r in A}, {key(r): r for r in B}
    rows = []
    for k in sorted(set(ia) & set(ib)):
        ra, rb = ia[k], ib[k]
        sa, sb = sum(t["seconds"] for t in ra["turns"]), sum(t["seconds"] for t in rb["turns"])
        ca, cb = sum(t["tool_calls"] for t in ra["turns"]), sum(t["tool_calls"] for t in rb["turns"])
        flag = "" if ra["pass"] == rb["pass"] else ("FIXED" if rb["pass"] else "REGRESSED")
        rows.append([k[0], k[1], f"{'✅' if ra['pass'] else '❌'}→{'✅' if rb['pass'] else '❌'}", flag,
                     f"{sa:.0f}→{sb:.0f}", f"{ca}→{cb}"])
    table(rows, ["BOT", "CASE", "PASS", "", "TURN s", "TOOLS"])
    pa, pb = sum(r["pass"] for r in A), sum(r["pass"] for r in B)
    print(f"\npass {pa}/{len(A)} → {pb}/{len(B)}. Replicates vary ±25-50% in time and tokens: "
          "judge speed on totals over ≥10 cases, not single cases.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--org")
    sp = p.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("suite")
    r.add_argument("--bot", help="comma list; overrides the suite's bot (run a matrix of variants)")
    r.add_argument("--tag")
    r.add_argument("--out")
    r.add_argument("--only")
    r.add_argument("--parallel", type=int, default=3)
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--runtime", help="headless-ubuntu | ubuntu-desktop (default: suite, then bot profile)")
    r.add_argument("--shared", action="store_true", help="one warm instance per bot, /clear between cases")
    r.add_argument("--keep", action="store_true", help="keep every instance")
    r.add_argument("--keep-failed", action="store_true", help="keep failed cases' instances for debugging")
    rp = sp.add_parser("report")
    rp.add_argument("file")
    rp.add_argument("--cases", action="store_true")
    rp.add_argument("--tag")
    c = sp.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    a = p.parse_args()
    if a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "report":
        report(a.file, per_case=a.cases, tag=a.tag)
    else:
        compare(a.a, a.b)


if __name__ == "__main__":
    main()
