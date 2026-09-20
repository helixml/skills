# Secrets and provider endpoints

## Contents
- Managing secrets (administrator view)
- Reading a secret from inside a container
- Provider endpoints

## Managing secrets

Secrets are injected as environment variables into project sessions, so this is how an agent
gets a `GITHUB_TOKEN` or an API key without it landing in a prompt or the repo:

```bash
helix secret list                          # personal; --org for org-owned
helix secret create -n GITHUB_TOKEN -v ghp_xxx -p prj_01xxx    # -p scopes it to a project
helix secret create -n OPENAI_API_KEY -v sk-xxx -a app_01xxx   # -a scopes it to an agent
helix secret update -n GITHUB_TOKEN -v ghp_yyy
helix secret delete -n GITHUB_TOKEN
```

Names must be shell identifiers. `USER_API_TOKEN` and anything beginning `HELIX_` are reserved
for bootstrap configuration and are rejected, so a project secret can never shadow a session's
own credentials.

Injection happens once, when a container is created. Adding a secret to a project does not
reach sessions that are already running — start a new one.

## Reading a secret from inside a container

`helix secret list` is the administrator's view of the store: listings return metadata, never
values. It is not how a running agent obtains a credential. For that — project secrets as env
vars, or the `get_secret` MCP tool for org bots — see
[helix-session](../../helix-session/SKILL.md).

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
