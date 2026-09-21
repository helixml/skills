---
name: helix-session
description: Use when running inside a Helix sandbox, spec task, or org bot/worker and you need a credential, the Helix API URL, or the workspace path — including when `printenv` shows no token, `helix secret list` returns names but no values, a `helix` command reports no API key, or an outbound call fails with 401/403 or connection refused.
---

# Working from inside Helix

You are running in a container Helix created. The platform has already configured your
environment; the usual failure here is going looking for credentials that are, in fact,
already present under names you did not expect.

Confirm where you are:

```bash
[ -n "$HELIX_SESSION_ID" ] && echo "inside a Helix session"
```

## The CLI needs no setup here

Do **not** hunt for an `hl-…` API key. Every `helix` subcommand resolves its URL from
`HELIX_URL`, then `HELIX_API_URL`; and its key from `HELIX_API_KEY`, then `USER_API_TOKEN`.
The sandbox exports the second name in each pair, so the CLI authenticates itself:

```bash
helix organization list        # works with no exports
```

If a command reports a missing API key, the session bootstrap did not complete — that is a
platform fault, not something to work around by minting a new key.

## What is exported

| Variable | Value |
|---|---|
| `HELIX_API_URL`, `HELIX_API_BASE_URL` | The sandbox API proxy. **The only route to the control plane from inside.** |
| `USER_API_TOKEN` | Session-scoped API key. Also set as `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ZED_HELIX_TOKEN`. |
| `HELIX_SESSION_ID` | This session. For controller-managed sandboxes, the sandbox id. |
| `HELIX_PROJECT_ID`, `HELIX_ORGANIZATION_ID` | Set when the session belongs to a project. |
| `HELIX_WORKSPACE_DIR` | Workspace as mounted in the container (`/workspace`). |
| `WORKSPACE_DIR` | The same workspace on the sandbox host; the docker wrapper needs this one. |
| `ZED_WORK_DIR` | Agent working directory (`/home/retro/work`). |

Always reach the API through `$HELIX_API_URL`. The isolated network bridge rejects every other
route, so a hardcoded control-plane address fails with a connection error that looks like the
control plane is down.

## Getting a secret

**Which path you are on depends on what you are.** Try the wrong one and you get an empty
result rather than an error, which is what makes this expensive.

### In a spec task or project sandbox — secrets are already env vars

Project secrets are injected into the container at creation:

```bash
printenv SLACK_BOT_TOKEN
```

If it is absent, the secret is not scoped to this project. Attach it from outside with
`helix secret create -n NAME -v VALUE -p prj_…`, then start a **new** session — injection
happens once, at container creation.

### As an org bot or worker — call the `get_secret` MCP tool

Bot credentials are *bound* to the worker. `get_secret` is the only route that works for
every binding, so reach for it first and do not infer availability from `printenv`.

A binding backed by a connected account (a Slack or GitHub install) is resolved through that
connection and never appears in the environment. A binding backed by a Helix secret must be a
project secret of the worker's own project, so that one *is* also injected as an env var —
the two routes return the same value. Do not treat an empty `printenv` as evidence that a
credential is unavailable.

```jsonc
// list_secrets  — no arguments; returns names and usage metadata, never values
// get_secret    — {"name": "SLACK_BOT_TOKEN"}
```

Both are baseline tools: every bot exposes them, and existing bots are backfilled at API server
start. You do not attach them and you cannot be a bot without them.

**If `get_secret` is not in your tool list, you are not running as an org bot** — so this is the
wrong path, not a broken one. Check `$HELIX_SESSION_ID`: set means you are in a spec task or
project sandbox, so use the env-var path above; unset means you are not inside Helix at all, and
no amount of searching will produce the credential.

Call `get_secret` immediately before the authenticated operation, and again after a 401/403 —
values may rotate or expire. It accepts a name and nothing else; backend source and resource
IDs are deliberately not accepted, and you can only read secrets granted to *you*.

### `helix secret list` is not this

That command is the administrator's CRUD over the secret store. Listings return metadata, never
values. Seeing your secret's name there confirms it exists; it will never hand you the value.
Do not loop on it, and do not go reading the Helix source — if the name is listed and neither
path above yields a value, the secret is not granted to this worker or project.

## Handling a secret once you have it

A `get_secret` result necessarily reaches your context — that is how you use it. The rule is
about everything *downstream* of that: never echo it to stdout or a log, never place it in
command-line arguments (argv is readable by every other process and lands in shell history),
and never let it reach a commit, an artifact, a spec-task attachment or a message back to the
user. Anything that outlives the container is the thing to guard.

Write it to a mode-600 file under `$XDG_RUNTIME_DIR` and have the consumer read the file:

```bash
umask 077
printenv SLACK_BOT_TOKEN > "$XDG_RUNTIME_DIR/slack_token"     # or the get_secret result
curl -H @- https://slack.com/api/... <<< "Authorization: Bearer $(cat "$XDG_RUNTIME_DIR/slack_token")"
```

Secret names must be shell identifiers. `USER_API_TOKEN` and anything starting with `HELIX_`
are reserved for bootstrap configuration and are rejected, so a granted secret never shadows
the session's own credentials.

## Publishing results

Finished pages, reports, PDFs and images belong in the project's artifacts rather than a file
inside a container that is about to be destroyed — see
[helix-artifacts](../helix-artifacts/SKILL.md). For the CLI itself, see
[helix-cli](../helix-cli/SKILL.md).
