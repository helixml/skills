# Starting a task

```bash
# create and start in one step
helix spectask start --project prj_01xxx --agent app_01yyy \
  -n "Add dark mode" --prompt "Users want a dark theme across the app"

# start a card that already exists on the board
helix spectask start spt_01xxx

# dispatch a full brief without committing it to the repo
helix spectask start --project prj_01xxx --agent app_01yyy -n "Investigate flaky login" \
  --prompt "Work through the brief below end to end." \
  --prompt-file ./brief.md \
  --attach ./failing-run.log --attach ./trace.txt

# cheap and fast: no compositor, no streaming, agent only
helix spectask start --project prj_01xxx --runtime headless-ubuntu -n "Bump deps" --prompt "…"
```

Behaviour worth knowing:

- **It returns immediately.** The sandbox provisions in the background; the printed task URL
  shows it booting. `--wait` blocks (up to 3 minutes) and then prints session-level connect info.
- A `--wait` timeout is **not** a failure — the task exists and is still provisioning. The CLI
  exits 0 and prints the task id.
- `--prompt-file` is appended after `--prompt` when both are given. Use it for design docs and
  briefs — nothing needs to be committed.
- `--attach` uploads files as task attachments; the agent reads them inside the sandbox at
  `~/work/helix-specs/design/tasks/<NNNNNN>_<slug>/attachments/`. Put logs and large context
  there rather than in the prompt, and give each file a distinct name — they land in one flat
  directory, so seven files called `SKILL.md` collide.
- `--runtime` is fixed for the life of the task. `ubuntu-desktop` (default) gives a streamable
  GNOME desktop with screenshots; `headless-ubuntu` is agent-only.
- `-q` prints only the task id (or the session id with `--wait`) — use it in scripts.

