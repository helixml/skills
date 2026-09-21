# Inside the container

## Contents
- Watching the agent, and desktop control
- Exec and its allowlist
- Copying files in
- Stop and resume

## Watching the agent

```bash
helix spectask list                     # active sessions with external agents
helix spectask screenshot ses_01xxx     # also the quickest RevDial connectivity check
helix spectask live ses_01xxx           # stream stats + recent activity + send commands
helix spectask health                   # API health, active agent sessions, MCP endpoint
```

`spectask health` does **not** check the sandbox hosts. If tasks aren't getting sandboxes at all,
that's `helix api /sandboxes` — see [helix-deploy](../../helix-deploy/SKILL.md).

`spectask screenshot` writes `screenshot-<timestamp>.jpg` into the current directory and prints
the filename — it does not write to stdout, so don't redirect it. (`helix sandbox screenshot`
does the opposite: stdout by default, `-o` for a file.)

Desktop control (desktop runtimes only):

```bash
helix spectask mcp desktop ses_01xxx take_screenshot
helix spectask mcp desktop ses_01xxx list_windows
helix spectask mcp desktop ses_01xxx type_text --text "hello"
helix spectask mcp desktop ses_01xxx mouse_click --x 640 --y 480
```

## Exec and its allowlist

`helix spectask exec` is **not** a general-purpose shell. The desktop container enforces a
server-side allowlist and rejects anything else with `403 command not allowed: <cmd>`:

```
vkcube  glxgears  weston-simple-egl        # benchmark/graphics
ls  cat  echo  test                        # inspection
pkill  killall                             # process control
npm  claude                                # agent CLI upkeep
helix-claude-auth-wrapper  helix-codex-auth-wrapper
git                                        # only `git config --global user.name|user.email <v>`
```

No `bash`, no `sh`, no `python3`, no `go`. There is no shell, so pipes, redirection, `&&` and
globs are not available either — each call is one `execve` of an allowlisted binary.

```bash
helix spectask exec ses_01xxx ls /home/retro/work
helix spectask exec ses_01xxx cat /home/retro/work/README.md
helix spectask exec ses_01xxx -- ls -la /home/retro/work        # -- before flag-like args
helix spectask exec ses_01xxx --timeout 300 vkcube
helix spectask exec ses_01xxx --background vkcube
```

Use `--` before any argument starting with `-`, or cobra parses it as a flag of `exec` itself
(`unknown shorthand flag: 'c' in -c` is what a forgotten `--` looks like).

**To actually run arbitrary commands**, pick one of:

- **Ask the agent** — `helix spectask send spt_01xxx "run the tests and paste the failures" --wait`.
  It has a real shell; you are talking to something that can use it.
- **Use a standalone sandbox** — `helix sandbox exec` *is* general-purpose (see below).

Copying files in is unrestricted:

```bash
helix spectask copy ses_01xxx ./patch.diff                          # → ~/work/incoming/patch.diff
helix spectask copy ses_01xxx ./config.json --dest /home/retro/work/config.json
helix spectask copy ses_01xxx ./data.txt --no-file-manager          # don't pop the file manager
```

Note the argument order: session **first**, then the local file.

`--timeout` on `exec` defaults to 30 seconds.

## Stop and resume

```bash
helix spectask stop ses_01xxx
helix spectask resume ses_01xxx      # verifies session restore
```

Do **not** run `helix spectask stop --all` on a shared instance — it stops every external-agent
session, including other people's work.

To free resources while keeping the card, prefer `helix spectask archive spt_01xxx`
(see [helix-board](../../helix-board/SKILL.md)) — it stops the agent *and* takes the card off the
board.

