# Secrets and provider endpoints

## Contents
- Reading a secret from inside a container
- Managing secrets (administrator view)
- Provider endpoints

## Reading a secret from inside a container

This is the common case, and none of the `helix secret` commands below do it. They are the
administrator's CRUD over the store: every listing returns metadata, never values.

Try these in order and stop at the first that yields a value:

1. **`get_secret`**, if it is in your tool list: `get_secret {"name": "SLACK_BOT_TOKEN"}`.
   Prefer it for every credential. It covers everything granted to you whatever the backend
   — a Helix secret or a connected account (a Slack or GitHub install) alike — and which
   credentials those are is controlled by the bot's own grants, not by the backend type.
   `list_secrets` shows the names you have been granted.
2. **An environment variable**: `printenv NAME`. Project secrets are injected at container
   creation, so a credential scoped to this project is already in the environment. This is
   the route when `get_secret` is not in your tool list — you are not running as a bot.
   `$HELIX_SESSION_ID` unset means you are not inside Helix at all.
3. **`helix secret` / `helix api`** — for managing the store, not for reading a value. They
   exist for completeness; neither returns one.

**If the first two yield nothing, stop.** The credential is not granted to this worker or
project. Seeing its name in a listing confirms only that it exists somewhere. Do not retry the
same command with different flags, do not guess API endpoints, do not grep the filesystem or
logs, and do not go reading the Helix source — none of those contain the value, and the search
has no terminating condition. Report that the credential is not available to you and stop.

See [helix-session](../../helix-session/SKILL.md) for the full picture of what a sandbox
exports, if that skill is available to you.

## Managing secrets (administrator view)

These manage the store from outside. They are how a secret gets *created*, not how a running
agent reads one:

```bash
helix secret list                          # personal; --org for org-owned
helix secret create -n GITHUB_TOKEN -v ghp_xxx -p prj_01xxx    # -p scopes it to a project
helix secret create -n OPENAI_API_KEY -v sk-xxx -a app_01xxx   # -a scopes it to an agent
helix secret update -n GITHUB_TOKEN -v ghp_yyy
helix secret delete -n GITHUB_TOKEN
```

A project-scoped secret is injected as an environment variable into that project's sessions,
which is how an agent gets a `GITHUB_TOKEN` without it landing in a prompt or the repo.

Two things to know: `helix secret list` shows **names only — values are write-only** and cannot
be read back through the CLI/API (by design). And a project-scoped secret is injected only into
**project spec-task sessions**; an external CLI session on your laptop won't see the value, so
for durable state a future session must resume from, store the secret *name* (not the value) in
your notes and let the resuming spec task pick it up from the environment.
Injection happens once, when a container is created — adding a secret to a project does not
reach sessions that are already running, so start a new one.

Names must be shell identifiers. `USER_API_TOKEN` is reserved for bootstrap configuration.

## Provider endpoints

Provider endpoints attach any OpenAI-compatible API (OpenAI, Together, a self-hosted vLLM):

```bash
helix provider list
helix provider create -n my-vllm -u https://vllm.internal/v1 -k sk-xxx -m qwen3-32b,qwen3-8b
helix provider update prov_01xxx -m qwen3-32b
helix provider delete prov_01xxx
```

`-f/--api-key-file` reads the key from a file instead of argv, which keeps it out of your shell
history and the process table. Prefer it in scripts.
