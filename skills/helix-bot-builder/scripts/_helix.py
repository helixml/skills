"""Minimal Helix REST client shared by botctl.py and bot_eval.py (stdlib only).

Auth: HELIX_URL (or HELIX_API_URL) + HELIX_API_KEY (or USER_API_TOKEN, which is
what a Helix sandbox exports). Org: --org, else HELIX_ORG, else HELIX_ORGANIZATION_ID.
"""
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

WORK = "/home/retro/work"
INCOMING = WORK + "/incoming"


class HelixError(Exception):
    def __init__(self, status, body, method, path):
        self.status, self.body, self.method, self.path = status, body, method, path
        super().__init__(f"{method} {path} -> HTTP {status}: {body[:500]}")


class Helix:
    def __init__(self, url=None, key=None, org=None):
        self.url = (url or os.environ.get("HELIX_URL") or os.environ.get("HELIX_API_URL") or "").rstrip("/")
        self.key = key or os.environ.get("HELIX_API_KEY") or os.environ.get("USER_API_TOKEN") or ""
        self.org = org or os.environ.get("HELIX_ORG") or os.environ.get("HELIX_ORGANIZATION_ID") or ""
        if not self.url or not self.key:
            sys.exit("set HELIX_URL and HELIX_API_KEY")
        self._org_id = None

    # -- transport -----------------------------------------------------------
    def req(self, method, path, body=None, raw=None, timeout=120, key=None, ctype=None, query=None):
        if not path.startswith("/v1/") and not path.startswith("/api/"):
            path = "/api/v1" + (path if path.startswith("/") else "/" + path)
        if query:
            path += ("&" if "?" in path else "?") + urllib.parse.urlencode(query)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(self.url + path, data=data, method=method)
        r.add_header("Authorization", "Bearer " + (key or self.key))
        if data is not None:
            r.add_header("Content-Type", ctype or "application/json")
        for attempt in range(30):  # dev stacks hot-reload the API: ride out ~60 s of "connection refused"
            try:
                with urllib.request.urlopen(r, timeout=timeout) as resp:
                    out = resp.read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (502, 503) and method == "GET" and attempt < 29:
                    time.sleep(2)
                    continue
                raise HelixError(e.code, e.read().decode(errors="replace"), method, path) from None
            except urllib.error.URLError as e:
                # refused = the request never reached the API, so a retry is safe even for POST
                if isinstance(e.reason, ConnectionRefusedError) and attempt < 29:
                    time.sleep(2)
                    continue
                raise HelixError(0, f"cannot reach {self.url}: {e.reason}", method, path) from None
        if not out:
            return None
        try:
            return json.loads(out)
        except ValueError:
            return out.decode(errors="replace")

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.req("POST", path, body=body if body is not None else {}, **kw)

    def patch(self, path, body, **kw):
        return self.req("PATCH", path, body=body, **kw)

    def delete(self, path, **kw):
        return self.req("DELETE", path, **kw)

    # -- org -----------------------------------------------------------------
    def need_org(self):
        if not self.org:
            sys.exit("no org: pass --org or set HELIX_ORG")
        return self.org

    def org_id(self):
        """The org_… id (the /organizations/{id}/… routes want the id, org routes take either)."""
        if self._org_id:
            return self._org_id
        o = self.need_org()
        if o.startswith("org_"):
            self._org_id = o
        else:
            for x in self.get("/organizations") or []:
                if o in (x.get("name"), x.get("id")):
                    self._org_id = x["id"]
            if not self._org_id:
                sys.exit(f"org {o!r} not found among your organizations")
        return self._org_id

    def o(self, path):
        return f"/orgs/{self.need_org()}{path}"

    # -- bots ----------------------------------------------------------------
    def bots(self):
        return self.get(self.o("/bots")) or []

    def bot(self, bot_id):
        d = self.get(self.o(f"/bots/{bot_id}"))
        b = d.get("bot", d) if isinstance(d, dict) else d
        if isinstance(d, dict):
            for k in ("legacy_app_id", "project_id"):
                if d.get(k) and not b.get(k):
                    b[k] = d[k]
        return b

    def instances(self, bot_id):
        return self.get(self.o(f"/bots/{bot_id}/instances")) or []

    def new_instance(self, bot_id, name=None, runtime=None, message=None):
        body = {}
        if name:
            body["name"] = name
        if runtime:
            body["sandbox_runtime"] = runtime
        if message:
            body["message"] = message
        return self.post(self.o(f"/bots/{bot_id}/instances"), body)

    def delete_instance(self, bot_id, sid):
        return self.delete(self.o(f"/bots/{bot_id}/instances/{sid}"))

    # -- chat ----------------------------------------------------------------
    def chat(self, text, session_id=None, attach=(), key=None, timeout=900, app_id=None):
        """Blocking /sessions/chat turn. Returns (session_id, reply_text, seconds)."""
        parts = [{"type": "text", "text": text}] if attach else [text]
        for p in attach:
            parts.append(attachment_part(p))
        body = {"stream": False, "type": "text",
                "messages": [{"role": "user", "content": {"content_type": "text", "parts": parts}}]}
        if session_id:
            body["session_id"] = session_id
        if app_id:
            body["app_id"] = app_id
        t0 = time.time()
        d = self.req("POST", "/sessions/chat", body=body, timeout=timeout, key=key)
        secs = time.time() - t0
        if not isinstance(d, dict) or "choices" not in d:
            raise RuntimeError(f"unexpected chat response: {str(d)[:500]}")
        return d.get("id"), d["choices"][0]["message"].get("content") or "", secs

    def turn(self, text, session_id=None, attach=(), key=None, timeout=900):
        """One turn, graded the way a customer sees it.

        The blocking /sessions/chat reply is the WHOLE turn (thinking, "**Tool Call:**" blocks,
        page snapshots), so the reply returned here is the interaction's last text entry.
        App keys cannot read interactions; for them the cleaned raw reply is the best we have.
        Returns dict(session_id, reply, raw, seconds, interaction)."""
        prev = (self.last_interaction(session_id) or {}).get("id") if session_id and not key else None
        sid, raw, secs = self.chat(text, session_id=session_id, attach=attach, key=key, timeout=timeout)
        inter = None if key else self.wait_turn(sid, prev)
        reply = final_text(inter) if inter else last_segment(raw)
        return {"session_id": sid, "reply": reply, "raw": raw, "seconds": secs, "interaction": inter}

    def interactions(self, sid, per_page=100, order="asc", page=0):
        # pages are 0-indexed: page=1 is the SECOND page (empty for short sessions)
        d = self.get(f"/sessions/{sid}/interactions", query={"per_page": per_page, "order": order, "page": page})
        return (d or {}).get("interactions") or []

    def last_interaction(self, sid):
        xs = sorted(self.interactions(sid, per_page=5, order="desc"), key=lambda i: i.get("created", ""))
        return xs[-1] if xs else None

    def wait_turn(self, sid, prev_id=None, timeout=60):
        """The interaction list lags the chat reply by a moment: poll until a turn newer than
        prev_id has settled (complete/error)."""
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = self.last_interaction(sid)
            if last and last.get("id") != prev_id and last.get("state") in ("complete", "error"):
                return last
            time.sleep(1)
        return last if last and last.get("id") != prev_id else None

    # -- sandboxes -----------------------------------------------------------
    def sandbox_for(self, sid, wait=0):
        """Find the sandbox row backing a session (instances and bot sessions both have one)."""
        deadline = time.time() + wait
        while True:
            d = self.get(f"/organizations/{self.org_id()}/sandboxes")
            rows = d if isinstance(d, list) else (d or {}).get("sandboxes") or (d or {}).get("data") or []
            for s in rows:
                if s.get("session_id") == sid:
                    if not wait or s.get("status") == "running":
                        return s
            if time.time() >= deadline:
                return None
            time.sleep(3)

    def sbx_path(self, sbx, tail=""):
        return f"/organizations/{self.org_id()}/sandboxes/{sbx}{tail}"

    def exec(self, sbx, script, timeout=60, cwd=None):
        body = {"cmd": "bash", "args": ["-lc", script], "timeout_seconds": timeout}
        if cwd:
            body["cwd"] = cwd
        return self.post(self.sbx_path(sbx, "/commands"), body, timeout=timeout + 30)

    def write_file(self, sbx, path, data):
        return self.req("PUT", self.sbx_path(sbx, "/files"), raw=data,
                        ctype="application/octet-stream", query={"path": path})

    def read_file(self, sbx, path):
        return self.get(self.sbx_path(sbx, "/files"), query={"path": path})


# -- helpers -----------------------------------------------------------------
THINK_RE = re.compile(r"<thinking>.*?</thinking>", re.S)


def strip_thinking(text):
    return THINK_RE.sub("", text or "").strip()


TOOL_BLOCK_RE = re.compile(r"\*\*Tool Call: ")


def last_segment(raw):
    """Best-effort final answer from a raw turn blob (app-key/webhook callers): drop thinking and
    everything up to the last tool-call block's output. Prefer final_text(interaction)."""
    text = strip_thinking(raw)
    if not TOOL_BLOCK_RE.search(text):
        return text
    tail = TOOL_BLOCK_RE.split(text)[-1]
    parts = re.split(r"\n\s*\n", tail)
    return parts[-1].strip() if len(parts) > 1 else tail.strip()


def attachment_part(path):
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        url = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    if mime.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": url}}
    return {"type": "file", "file": {"filename": os.path.basename(path), "file_data": url}}


def final_text(interaction):
    """Last text entry of a turn, thinking stripped (what the user saw)."""
    texts = [e for e in (interaction or {}).get("response_entries") or [] if e.get("type") == "text"]
    return strip_thinking(texts[-1]["content"]) if texts else strip_thinking((interaction or {}).get("response_message"))


def tool_calls(interaction):
    return [e for e in (interaction or {}).get("response_entries") or [] if e.get("type") == "tool_call"]


def ts(s):
    """Parse an RFC3339 timestamp from the API into epoch seconds (None if unset)."""
    if not s or s.startswith("0001"):
        return None
    from datetime import datetime
    s = re.sub(r"\.(\d{6})\d*", r".\1", s.replace("Z", "+00:00"))
    return datetime.fromisoformat(s).timestamp()


def table(rows, headers):
    rows = [[str(c) for c in r] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w[i]) for i, h in enumerate(headers)))
    for r in rows:
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)))
