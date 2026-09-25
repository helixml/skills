#!/usr/bin/env python3
"""botctl — build, poke and debug helix-org bots and their instances.

Stdlib only; runs on a laptop or inside a Helix sandbox. Auth from HELIX_URL +
HELIX_API_KEY (or USER_API_TOKEN), org from --org / HELIX_ORG.

  botctl.py ls                              bots with status, harness, model
  botctl.py get BOT [--prompt]              one bot (profile, tools, ids)
  botctl.py export BOT [-o bot.json]        bot -> spec file (+ prompt .md beside it)
  botctl.py apply bot.json [--dry-run]      create or update a bot from a spec
  botctl.py prompt BOT [-f prompt.md]       print, or replace, the bot's instructions
  botctl.py profile BOT [--runtime R] [--mcp a,b] [--tools x,y] [--skills on|off]
  botctl.py start|stop|restart|apply-config BOT
  botctl.py new BOT [--name N] [--runtime R] [--message M]
  botctl.py instances BOT
  botctl.py rm BOT SID... | --all [--idle]
  botctl.py say SID "message" [--attach f]... [--tools]
  botctl.py ask BOT "message" [--attach f]... [--keep] [--runtime R]
  botctl.py turns SID [--last N] [--full]
  botctl.py watch SID
  botctl.py sbx SID
  botctl.py put SID LOCAL [REMOTE]          default REMOTE: ~/work/incoming/<name>
  botctl.py exec SID -- CMD...
  botctl.py logs SID [--lines N]
  botctl.py shot SID [-o file.jpg]          desktop runtimes only
  botctl.py doctor BOT [SID]
  botctl.py appkey BOT [create NAME | ls | rm KEY]
  botctl.py gw KEY "message" [--session SID] [--attach f]...
  botctl.py hooks [ls | add URL [--project P] [--events e,..] | deliveries EP]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helix import INCOMING, Helix, HelixError, strip_thinking, table, tool_calls, ts  # noqa: E402

CREATE_FIELDS = ["id", "name", "content", "tools", "triggers", "parent_id", "preserve_context",
                 "sandbox_runtime", "sandbox_resource_overrides", "code_agent_runtime",
                 "code_agent_credential_type", "provider", "model", "reasoning_effort", "owner"]
PATCH_FIELDS = ["name", "content", "tools", "project_ids", "preserve_context", "sandbox_runtime",
                "sandbox_resource_overrides", "code_agent_runtime", "code_agent_credential_type",
                "provider", "model", "reasoning_effort", "instance_profile"]
EXPORT_FIELDS = ["id", "name", "tools", "parent_ids", "preserve_context", "sandbox_runtime",
                 "sandbox_resource_overrides", "code_agent_runtime", "code_agent_credential_type",
                 "provider", "model", "reasoning_effort", "instance_profile"]
RESTART_FIELDS = {"content", "tools", "sandbox_runtime", "sandbox_resource_overrides"}


def out(x):
    print(json.dumps(x, indent=2) if not isinstance(x, str) else x)


# -- bots --------------------------------------------------------------------
def cmd_ls(h, a):
    bots = h.bots()
    if a.json:
        return out(bots)
    table([[b["id"], b.get("name", ""), b.get("status", ""), b.get("code_agent_runtime") or b.get("agent_runtime", ""),
            b.get("model", ""), b.get("effective_sandbox_runtime", ""), len(b.get("tools") or []),
            ",".join(b.get("parent_ids") or [])] for b in bots],
          ["ID", "NAME", "STATUS", "HARNESS", "MODEL", "SANDBOX", "TOOLS", "PARENTS"])


def cmd_get(h, a):
    b = h.bot(a.bot)
    if a.json:
        return out(b)
    if a.prompt:
        return print(b.get("content", ""))
    keys = ["id", "name", "status", "restart_required", "agent_work_state", "code_agent_runtime", "provider",
            "model", "reasoning_effort", "effective_sandbox_runtime", "sandbox_status", "sandbox_status_message",
            "preserve_context", "parent_ids", "project_id", "session_id", "legacy_app_id", "sandbox_id"]
    for k in keys:
        if b.get(k) not in (None, "", []):
            print(f"{k:28} {b[k]}")
    print(f"{'instance_profile':28} {json.dumps(b.get('instance_profile'))}")
    print(f"{'tools':28} {len(b.get('tools') or [])}: {', '.join(b.get('tools') or [])}")
    c = b.get("content") or ""
    print(f"{'prompt':28} {len(c)} chars, {len(c.split())} words — first line: {c.strip().splitlines()[0] if c.strip() else ''}")
    ins = h.instances(a.bot)
    print(f"{'instances':28} {len(ins)} ({sum(1 for i in ins if i.get('sandbox_status') == 'running')} running)")


def cmd_export(h, a):
    b = h.bot(a.bot)
    spec = {k: b[k] for k in EXPORT_FIELDS if b.get(k) not in (None, "", [], {})}
    if spec.get("parent_ids"):
        spec["parent_id"] = spec.pop("parent_ids")[0]
    path = a.o or f"{a.bot}.json"
    prompt_path = os.path.splitext(path)[0] + ".prompt.md"
    spec["content_file"] = os.path.basename(prompt_path)
    with open(prompt_path, "w") as f:
        f.write(b.get("content") or "")
    with open(path, "w") as f:
        json.dump(spec, f, indent=2)
        f.write("\n")
    print(f"wrote {path} and {prompt_path}")


def load_spec(path):
    with open(path) as f:
        spec = json.load(f)
    if "content_file" in spec:
        with open(os.path.join(os.path.dirname(os.path.abspath(path)), spec.pop("content_file"))) as f:
            spec["content"] = f.read()
    return spec


def norm_field(k, v):
    """The API omits zero values (e.g. helix_skills:false) and returns tools sorted."""
    if k == "instance_profile":
        v = v or {}
        return {"sandbox_runtime": v.get("sandbox_runtime") or "", "mcp_servers": sorted(v.get("mcp_servers") or []),
                "tools": sorted(v.get("tools") or []), "helix_skills": bool(v.get("helix_skills"))}
    if k == "tools":
        return sorted(v or [])
    if k == "sandbox_resource_overrides":
        return (v or {}).get("vcpus") or 0
    return v if v not in (None, "") else None


def cmd_apply(h, a):
    spec = load_spec(a.spec)
    bid = spec.get("id") or sys.exit("spec needs an id (it becomes the bot id)")
    try:
        cur = h.bot(bid)
    except HelixError as e:
        if e.status != 404:
            raise
        cur = None
    if cur is None:
        body = {k: spec[k] for k in CREATE_FIELDS if k in spec}
        print(f"create {bid}: {sorted(body)}")
        if a.dry_run:
            return
        res = h.post(h.o("/bots"), body)
        print(f"created {res}")
        if spec.get("instance_profile"):
            h.patch(h.o(f"/bots/{bid}"), {"instance_profile": spec["instance_profile"]})
            print("instance_profile set")
        return
    body = {}
    for k in PATCH_FIELDS:
        if k in spec and norm_field(k, spec[k]) != norm_field(k, cur.get(k)):
            body[k] = spec[k]
    if "tools" in body:
        missing = sorted(set(cur.get("tools") or []) - set(body["tools"]))
        if missing:
            print(f"note: PATCH tools replaces the list; removing {missing}")
    if not body:
        return print(f"{bid}: up to date")
    print(f"update {bid}: {sorted(body)}")
    if a.dry_run:
        return
    h.patch(h.o(f"/bots/{bid}"), body)
    if RESTART_FIELDS & set(body):
        print("changed fields reach the main bot session on its next restart/apply-config;"
              " instances snapshot the prompt at creation — create a NEW instance to test")


def cmd_prompt(h, a):
    if not a.f:
        return print(h.bot(a.bot).get("content", ""))
    with open(a.f) as f:
        content = f.read()
    h.patch(h.o(f"/bots/{a.bot}"), {"content": content})
    print(f"{a.bot}: prompt updated ({len(content)} chars). New instances use it; existing ones keep the old one.")


def cmd_profile(h, a):
    b = h.bot(a.bot)
    p = dict(b.get("instance_profile") or {})
    changed = False
    if a.runtime is not None:
        p["sandbox_runtime"] = "" if a.runtime == "inherit" else a.runtime
        changed = True
    if a.mcp is not None:
        p["mcp_servers"] = [x for x in a.mcp.split(",") if x]
        changed = True
    if a.tools is not None:
        p["tools"] = [x for x in a.tools.split(",") if x]
        changed = True
    if a.skills is not None:
        p["helix_skills"] = a.skills == "on"
        changed = True
    if changed:
        not_on_bot = sorted(set(p.get("tools") or []) - set(b.get("tools") or []))
        if not_on_bot:
            print(f"warning: {not_on_bot} are not on the bot's own tools, so instances will NOT get them"
                  " (served tools = profile.tools ∩ bot.tools)")
        b = h.patch(h.o(f"/bots/{a.bot}"), {"instance_profile": p})
        print("applies to each instance's next sandbox start")
    out(b.get("instance_profile") if isinstance(b, dict) else p)


def cmd_lifecycle(h, a):
    path = {"start": "activate"}.get(a.cmd, a.cmd)
    out(h.post(h.o(f"/bots/{a.bot}/{path}")) or f"{a.cmd}: ok")


# -- instances ---------------------------------------------------------------
def cmd_new(h, a):
    inst = h.new_instance(a.bot, a.name or "botctl", a.runtime, a.message)
    print(inst["session_id"])
    if a.v:
        out(inst)


def cmd_instances(h, a):
    ins = h.instances(a.bot)
    if a.json:
        return out(ins)
    table([[i["session_id"], i.get("name", ""), i.get("sandbox_runtime", ""), i.get("sandbox_status") or "stopped",
            i.get("created_at", "")[:19], i.get("updated_at", "")[:19]] for i in ins],
          ["SESSION", "NAME", "RUNTIME", "STATUS", "CREATED", "UPDATED"])


def cmd_rm(h, a):
    sids = a.sids
    if a.all:
        sids = [i["session_id"] for i in h.instances(a.bot)
                if not a.idle or (i.get("sandbox_status") or "") in ("", "terminated_idle", "stopped")]
    for s in sids:
        try:
            h.delete_instance(a.bot, s)
            print(f"deleted {s}")
        except HelixError as e:
            print(f"{s}: {e}")


def print_turn_tools(interaction):
    calls = tool_calls(interaction)
    counts = {}
    for c in calls:
        counts[c.get("tool_name")] = counts.get(c.get("tool_name"), 0) + 1
    print(f"[{len(calls)} tool calls] " + ", ".join(f"{k}×{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])),
          file=sys.stderr)


def cmd_say(h, a):
    r = h.turn(a.message, session_id=a.sid, attach=a.attach or (), timeout=a.timeout)
    print(r["raw"] if a.raw else r["reply"])
    print(f"[{r['seconds']:.1f}s session={r['session_id']}]", file=sys.stderr)
    if a.tools:
        print_turn_tools(r["interaction"])


def cmd_ask(h, a):
    inst = h.new_instance(a.bot, "botctl ask", a.runtime)
    sid = inst["session_id"]
    print(f"[instance {sid}]", file=sys.stderr)
    try:
        r = h.turn(a.message, session_id=sid, attach=a.attach or (), timeout=a.timeout)
        print(r["raw"] if a.raw else r["reply"])
        print(f"[{r['seconds']:.1f}s incl. cold start]", file=sys.stderr)
        if a.tools:
            print_turn_tools(r["interaction"])
    finally:
        if not a.keep:
            h.delete_instance(a.bot, sid)
        else:
            print(f"[kept {sid}]", file=sys.stderr)


def fmt_entry(e, full):
    if e.get("type") == "tool_call":
        body = (e.get("content") or "").split("\n", 1)[-1].strip().replace("\n", " ")
        return f"  🔧 {e.get('tool_name')} [{e.get('tool_status', '')}] {body if full else body[:160]}"
    if e.get("type") == "text":
        t = e.get("content") or ""
        if not full:
            t = strip_thinking(t)
        return "  💬 " + (t if full else t[:600]).replace("\n", "\n     ")
    return None


def cmd_turns(h, a):
    xs = h.interactions(a.sid, per_page=a.last, order="desc")[::-1]
    for i in xs:
        t0, t1 = ts(i.get("created")), ts(i.get("completed"))
        dur = f"{t1 - t0:.1f}s" if t0 and t1 else "…"
        calls = tool_calls(i)
        print(f"── {i['id']} {i.get('created', '')[:19]} state={i.get('state')} {dur} tools={len(calls)}"
              + (f" ERROR={i.get('error')}" if i.get("error") else ""))
        print("  👤 " + (i.get("prompt_message") or "")[: (None if a.full else 400)].replace("\n", "\n     "))
        for e in i.get("response_entries") or []:
            line = fmt_entry(e, a.full)
            if line:
                print(line)


def cmd_watch(h, a):
    seen = set()
    while True:
        i = h.last_interaction(a.sid)
        if not i:
            time.sleep(3)
            continue
        for e in i.get("response_entries") or []:
            k = (i["id"], e.get("message_id"), e.get("tool_status"), len(e.get("content") or ""))
            if k in seen:
                continue
            seen.add(k)
            line = fmt_entry(e, False)
            if line and (e.get("type") != "text" or e.get("content")):
                print(line, flush=True)
        if i.get("state") in ("complete", "error") and not a.follow:
            print(f"── turn {i['id']} {i.get('state')} {i.get('error') or ''}")
            return
        time.sleep(a.interval)


# -- sandbox -----------------------------------------------------------------
def need_sbx(h, sid, wait=0):
    s = h.sandbox_for(sid, wait=wait)
    if not s:
        sys.exit(f"no sandbox found for {sid} (stopped/idle-terminated instances have none running)")
    return s


def cmd_sbx(h, a):
    s = need_sbx(h, a.sid)
    out(s if a.json else f"{s['id']} status={s.get('status')} runtime={s.get('runtime')} bot={s.get('org_bot_id', '')}")


def cmd_put(h, a):
    s = need_sbx(h, a.sid, wait=120)
    remote = a.remote or f"{INCOMING}/{os.path.basename(a.local)}"
    with open(a.local, "rb") as f:
        h.write_file(s["id"], remote, f.read())
    print(f"wrote {remote}")


def cmd_exec(h, a):
    s = need_sbx(h, a.sid)
    r = h.exec(s["id"], " ".join(a.command), timeout=a.timeout)
    sys.stdout.write(r.get("stdout") or "")
    sys.stderr.write(r.get("stderr") or "")
    sys.exit(r.get("exit_code") or 0)


LOG_SCRIPT = r"""
n=%d
sec() { echo; echo "===== $1"; }
sec "processes"; ps -eo pid,etime,rss,cmd --sort=start_time | grep -E 'opencode|dsh|goose|qwen|claude|codex|zed|chrome-devtools-mcp|chrome --' | grep -v -E 'grep|crashpad|--type=' | cut -c1-170
sec "chrome-devtools-mcp servers (one per live agent thread; count growing across clears = leak)"; ps -eo args | grep -c '^chrome-devtools-mcp' 
sec "workspace"; ls -la ~/work ~/work/incoming 2>/dev/null | head -40; test -f ~/.helix-setup-failed && { echo "SETUP FAILED:"; cat ~/.helix-setup-failed; }
sec "AGENTS.md (head)"; head -c 600 ~/work/AGENTS.md 2>/dev/null; echo
sec "skills"; ls ~/.agents/skills 2>/dev/null; env | grep -E '^HELIX_SKILLS='
sec "setup log"; tail -n $n ~/.helix-setup.log 2>/dev/null
sec "Zed.log errors"; grep -iE 'error|failed|panic|denied|timeout' ~/.local/share/zed/logs/Zed.log 2>/dev/null | tail -n $n | cut -c1-300
sec "opencode log"; tail -n $n ~/work/.opencode-state/opencode/log/*.log 2>/dev/null | cut -c1-300
sec "chrome"; tail -n $n /tmp/helix-chrome.log 2>/dev/null | cut -c1-300
"""


def cmd_logs(h, a):
    s = need_sbx(h, a.sid)
    r = h.exec(s["id"], LOG_SCRIPT % a.lines, timeout=60)
    print(r.get("stdout") or "", r.get("stderr") or "")


def cmd_shot(h, a):
    s = need_sbx(h, a.sid)
    data = h.req("GET", h.sbx_path(s["id"], "/screenshot"), timeout=60)
    path = a.o or f"{a.sid}.jpg"
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("latin-1"))
    print(f"wrote {path}")


# -- doctor ------------------------------------------------------------------
def cmd_doctor(h, a):
    probs, notes = [], []
    b = h.bot(a.bot)
    rt = b.get("code_agent_runtime") or b.get("agent_runtime")
    prof = b.get("instance_profile") or {}
    tools = set(b.get("tools") or [])
    if rt == "zed_agent":
        probs.append("harness zed_agent loses AGENTS.md after every clear/new thread (open bug) — use opencode or deepseek_harness")
    if rt in ("claude_code", "codex_cli") and b.get("code_agent_credential_type") != "subscription":
        notes.append(f"{rt} is gated to vendor models; self-hosted providers will not work")
    if not (b.get("content") or "").strip():
        probs.append("empty prompt")
    elif len(b["content"]) > 20000:
        notes.append(f"prompt is {len(b['content'])} chars; move per-system detail into repo skills (.agents/skills)")
    if b.get("restart_required"):
        notes.append("restart_required: main session runs stale config (instances are unaffected)")
    if b.get("sandbox_status") == "failed":
        probs.append(f"sandbox failed: {b.get('sandbox_status_message')}")
    served = set(prof.get("tools") or []) & tools
    dropped = set(prof.get("tools") or []) - tools
    if dropped:
        probs.append(f"instance_profile.tools {sorted(dropped)} are not on the bot → instances never get them")
    if "get_secret" in (b.get("content") or "") and "get_secret" not in served:
        probs.append("prompt mentions get_secret but instances are not served it (add to instance_profile.tools and bot tools)")
    if "chrome-devtools" not in (prof.get("mcp_servers") or []) and "browser" in (b.get("content") or "").lower():
        probs.append("prompt talks about the browser but instance_profile.mcp_servers lacks chrome-devtools")
    if prof.get("sandbox_runtime") == "ubuntu-desktop" or (not prof.get("sandbox_runtime") and b.get("effective_sandbox_runtime") == "ubuntu-desktop"):
        notes.append("instances default to ubuntu-desktop; headless-ubuntu is faster and cheaper unless a human must watch")
    ins = h.instances(a.bot)
    idle = [i for i in ins if (i.get("sandbox_status") or "") in ("", "terminated_idle", "stopped")]
    if idle:
        notes.append(f"{len(idle)} idle/stopped instances (botctl rm {a.bot} --all --idle)")
    print(f"bot {b['id']}: harness={rt} model={b.get('model')} status={b.get('status')} "
          f"profile={json.dumps(prof)} served_instance_tools={sorted(served)}")
    if a.sid:
        s = h.sandbox_for(a.sid)
        if not s:
            probs.append(f"{a.sid}: no sandbox (stopped or idle-terminated → create a new instance)")
        else:
            print(f"sandbox {s['id']} status={s.get('status')} runtime={s.get('runtime')}")
            r = h.exec(s["id"], "test -f ~/.helix-setup-failed && cat ~/.helix-setup-failed; "
                                "echo AGENTS=$(wc -c < ~/work/AGENTS.md 2>/dev/null); "
                                "echo CDM=$(ps -eo args | grep -c '^chrome-devtools-mcp'); "
                                "echo CHROME=$(ps -eo args | grep -c '^/opt/google/chrome/chrome --')",
                       timeout=30)
            o = r.get("stdout") or ""
            print(o.strip())
            if "AGENTS=\n" in o or "AGENTS=0" in o:
                probs.append("AGENTS.md missing/empty in the sandbox")
            if "exit_code" in o:
                probs.append("workspace setup failed (see botctl logs)")
            if "chrome-devtools" in (prof.get("mcp_servers") or []) and "CHROME=0" in o and "CDM=0" not in o:
                notes.append("browser MCP is up but Chrome is not running yet (it starts on the first browser call)")
        last = h.last_interaction(a.sid)
        if last and last.get("state") == "error":
            probs.append(f"last turn errored: {last.get('error')}")
        if last and last.get("state") == "waiting":
            notes.append("last turn still waiting (botctl watch SID)")
    for p in probs:
        print("✗", p)
    for n in notes:
        print("•", n)
    if not probs:
        print("✓ no blocking problems found")


# -- gateway -----------------------------------------------------------------
def cmd_appkey(h, a):
    app = h.bot(a.bot)["legacy_app_id"]
    if a.action == "create":
        key = h.post("/api_keys", {"name": a.arg or f"{a.bot}-gateway", "type": "app", "app_id": app})
        print(key)
    elif a.action == "rm":
        h.delete("/api_keys", query={"key": a.arg})
        print("deleted")
    else:
        for k in h.get("/api_keys", query={"types": "app", "app_id": app}) or []:
            print(f"{k['key'][:10]}…  {k.get('name')}  {k.get('created', '')[:19]}")


def cmd_gw(h, a):
    """Talk as the end customer would: an app key, no user credentials. App keys cannot read
    interactions, so the reply is cut from the raw turn blob (see last_segment)."""
    r = h.turn(a.message, session_id=a.session, attach=a.attach or (), key=a.key, timeout=a.timeout)
    print(r["raw"] if a.raw else r["reply"])
    print(f"[{r['seconds']:.1f}s session={r['session_id']}]", file=sys.stderr)


def cmd_hooks(h, a):
    base = f"/organizations/{h.org_id()}/webhook-endpoints"
    if a.action == "add":
        body = {"url": a.arg, "events": (a.events or "bot_instance.turn_completed").split(",")}
        if a.project:
            body["project_id"] = a.project
        out(h.post(base, body))
        print("store the secret now — it is shown once", file=sys.stderr)
    elif a.action == "deliveries":
        out(h.get(f"{base}/{a.arg}/deliveries"))
    else:
        out(h.get(base))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--org")
    sp = p.add_subparsers(dest="cmd", required=True)

    def sub(name, fn, *args, **kw):
        s = sp.add_parser(name, **kw)
        for x in args:
            s.add_argument(x)
        s.set_defaults(fn=fn)
        return s

    sub("ls", cmd_ls).add_argument("--json", action="store_true")
    s = sub("get", cmd_get, "bot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--prompt", action="store_true")
    sub("export", cmd_export, "bot").add_argument("-o")
    sub("apply", cmd_apply, "spec").add_argument("--dry-run", action="store_true")
    sub("prompt", cmd_prompt, "bot").add_argument("-f")
    s = sub("profile", cmd_profile, "bot")
    s.add_argument("--runtime", help="headless-ubuntu | ubuntu-desktop | inherit")
    s.add_argument("--mcp", help="comma list: chrome-devtools,helix-session,helix-desktop,kodit,<project mcp>")
    s.add_argument("--tools", help="comma list of helix-org tools (must also be on the bot)")
    s.add_argument("--skills", choices=["on", "off"])
    for c in ("start", "stop", "restart", "apply-config"):
        sub(c, cmd_lifecycle, "bot")
    s = sub("new", cmd_new, "bot")
    s.add_argument("--name")
    s.add_argument("--runtime")
    s.add_argument("--message")
    s.add_argument("-v", action="store_true")
    sub("instances", cmd_instances, "bot").add_argument("--json", action="store_true")
    s = sub("rm", cmd_rm, "bot")
    s.add_argument("sids", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("--idle", action="store_true", help="with --all: only stopped/idle-terminated")
    for name, fn, first in (("say", cmd_say, "sid"), ("ask", cmd_ask, "bot"), ("gw", cmd_gw, "key")):
        s = sub(name, fn, first, "message")
        s.add_argument("--attach", action="append")
        s.add_argument("--timeout", type=int, default=900)
        s.add_argument("--raw", action="store_true", help="print the whole turn blob (thinking, tool calls)")
        if name != "gw":
            s.add_argument("--tools", action="store_true", help="print tool-call summary of the turn")
        if name == "ask":
            s.add_argument("--keep", action="store_true")
            s.add_argument("--runtime")
        if name == "gw":
            s.add_argument("--session")
    s = sub("turns", cmd_turns, "sid")
    s.add_argument("--last", type=int, default=20)
    s.add_argument("--full", action="store_true")
    s = sub("watch", cmd_watch, "sid")
    s.add_argument("--interval", type=float, default=3)
    s.add_argument("--follow", action="store_true", help="keep going across turns")
    sub("sbx", cmd_sbx, "sid").add_argument("--json", action="store_true")
    s = sub("put", cmd_put, "sid", "local")
    s.add_argument("remote", nargs="?")
    s = sub("exec", cmd_exec, "sid")
    s.add_argument("--timeout", type=int, default=60)
    s.add_argument("command", nargs=argparse.REMAINDER)
    sub("logs", cmd_logs, "sid").add_argument("--lines", type=int, default=30)
    sub("shot", cmd_shot, "sid").add_argument("-o")
    s = sub("doctor", cmd_doctor, "bot")
    s.add_argument("sid", nargs="?")
    s = sub("appkey", cmd_appkey, "bot")
    s.add_argument("action", nargs="?", choices=["create", "ls", "rm"], default="ls")
    s.add_argument("arg", nargs="?")
    s = sub("hooks", cmd_hooks)
    s.add_argument("action", nargs="?", choices=["ls", "add", "deliveries"], default="ls")
    s.add_argument("arg", nargs="?")
    s.add_argument("--project")
    s.add_argument("--events")

    a = p.parse_args()
    if a.cmd == "exec" and a.command and a.command[0] == "--":
        a.command = a.command[1:]
    h = Helix(org=a.org)
    try:
        a.fn(h, a)
    except HelixError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
