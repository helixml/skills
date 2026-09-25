# Bot API reference

Everything the `helix org`/`helix session` commands call, for when you need raw `helix api` /
curl (older CLI binaries, or other languages). Paths are under
`$HELIX_URL/api/v1`. `{org}` accepts the org slug or `org_…` id on `/orgs/{org}/…` routes;
`/organizations/{id}/…` routes want the id. ✓ = verified live against a PR #3293 stack.

Org routes decode JSON with **unknown fields rejected** (400) — send only the fields listed.
Errors are `{"error": "…"}`; 404 not found, 409 conflict/cycle, 400 unknown tool / invalid
instance profile, 403 permission.

## Bots

| Method | Path | Body → response |
|---|---|---|
| GET | `/orgs/{org}/bots` ✓ | → `[]Bot` with live status merged in |
| POST | `/orgs/{org}/bots` | create body → 201 `{id, activation_id?}`. Activation is deferred until the org default agent is configured |
| GET | `/orgs/{org}/bots/{id}` ✓ | → `{bot: Bot, legacy_app_id, project_id}` (+ `default_instructions` for seeded bots) |
| PATCH | `/orgs/{org}/bots/{id}` | any patch fields (omitted = unchanged) → Bot |
| DELETE | `/orgs/{org}/bots/{id}` | 204. Cascades: instances, project archived, app, attachments, reporting lines (repos kept) |
| POST | `/orgs/{org}/bots/{id}/activate` | 202 — "start" (creates project/app/session if missing) |
| POST | `/orgs/{org}/bots/{id}/stop` | 204 — stops the sandbox, keeps the session |
| POST | `/orgs/{org}/bots/{id}/restart` | 202 — **deletes the session**, activates a fresh one |
| POST | `/orgs/{org}/bots/{id}/apply-config` | 202 — recreates the container with current config, keeps session + thread |
| POST | `/orgs/{org}/bots/{id}/chat` | ensures project + app exist (no container) |
| POST/DELETE | `/orgs/{org}/bots/{id}/parents[/{parent_id}]` | `{parent_id}` — reporting lines (409 on cycles) |
| GET | `/orgs/{org}/bots/{id}/secrets`, `/available-secrets` | bound secrets / bindable sources |
| PUT/DELETE | `/orgs/{org}/bots/{id}/secrets/{name}` | `{source_kind:"helix_secret", secret_id, description?}` or `{source_kind:"connected_account", account_id, export_key?}` — owner/admin |
| GET | `/orgs/{org}/tools` | full helix-org tool catalogue `[{name, description}]` |

**Create body**: `content` (required), `id?` (else `b-…` minted), `name?`, `tools?` (merged
with the default worker set), `owner?` (owner tool set), `triggers?`, `parent_id?`,
`preserve_context?`, `sandbox_runtime?`, `sandbox_resource_overrides? {vcpus}`,
`code_agent_runtime?`, `code_agent_credential_type?`, `provider?`, `model?`, `reasoning_effort?`.
`instance_profile` is **not** accepted on create — PATCH it after.

**Patch body**: `name, content, tools (replaces the list), project_ids, preserve_context,
sandbox_runtime ("" = inherit), sandbox_resource_overrides ({vcpus:0} = inherit),
code_agent_runtime, code_agent_credential_type, provider, model, reasoning_effort,
instance_profile`. Name/content/agent-config changes are written through to the bot's app.

**Bot fields worth reading**: `status` (`running|starting|stopped`), `agent_work_state`
(`working` while a turn waits), `restart_required`, `sandbox_status`
(`pending|running|stopping|stopped|failed`) + `sandbox_status_message`,
`effective_sandbox_runtime`, `project_id`, `session_id` (main session), `legacy_app_id` (the
bot's app — what app keys bind to), `instance_profile`, `parent_ids`, `tools`.

**Enums**:
- `code_agent_runtime`: `opencode`, `deepseek_harness`, `qwen_code`, `zed_agent`, `goose_code`,
  `claude_code`, `codex_cli`, `gemini_cli`
- `code_agent_credential_type`: `api_key` or `subscription`. Subscription only works for
  `claude_code` and `codex_cli`.
- `reasoning_effort`: `none`, `low`, `medium`, `high`. `qwen3.8-flash-next` rejects `high`.
- `sandbox_runtime`: `headless-ubuntu`, `ubuntu-desktop`, or empty to inherit.
- vCPUs: `0` (inherit), `1`, `4`, `8`, `12`, `16`. Memory follows the vCPU value.

**Permissions**: any org member can list bots and create or list instances. Granting a tool
outside the default worker set needs an org owner or admin, and so does any `owner:true` bot,
instance-profile tools, org secrets bindings and org settings.

## Instances

| Method | Path | Body → response |
|---|---|---|
| GET | `/orgs/{org}/bots/{id}/instances` ✓ | → `[{session_id, bot_id, name, sandbox_runtime, sandbox_status, owner, created_at, updated_at}]`, newest first |
| POST | `/orgs/{org}/bots/{id}/instances` ✓ | `{name?, sandbox_runtime?, message?}` → 201 instance. Sandbox starts async; `message` is queued as the first turn |
| DELETE | `/orgs/{org}/bots/{id}/instances/{session_id}` ✓ | 204. Stops the container, deletes the workspace, deletes the session. Instance owner or org owner only |

`sandbox_status`: `""` (stopped), `starting`, `running`, `restarting`, `terminated_idle`.
Runtime resolution: request → `instance_profile.sandbox_runtime` → bot's effective runtime.
Resources = the bot's effective resources.

**Instance profile** (PATCH `/bots/{id}` `{"instance_profile": …}`):
```json
{"sandbox_runtime": "headless-ubuntu", "mcp_servers": ["chrome-devtools"], "tools": [], "helix_skills": false}
```
- `mcp_servers`: `chrome-devtools` (browser), `helix-session` (session history), `helix-desktop`
  (desktop only), `kodit` (code search), or a project MCP server's name (compared after
  sanitising). Unknown names are silently never kept. `helix` is rejected — it's controlled by `tools`.
- `tools`: helix-org tools; served = `profile.tools ∩ bot.tools`, re-checked per request. Empty →
  the instance has no `helix` MCP server at all.
- `helix_skills: false` → `HELIX_SKILLS=none` (no helix-* skills; the project repo's
  `.agents/skills` are still linked).
- Saved profiles are copied to existing instances and apply at their next sandbox start.

MCP equivalents (owner tool set): `create_bot_instance {bot_id, name?, sandbox_runtime?, message?}`,
`list_bot_instances {bot_id}`, `delete_bot_instance {bot_id, session_id}`.

## Chat

`POST /sessions/chat` ✓ (blocking with `stream:false`; SSE with `stream:true`):
```json
{"session_id": "ses_…", "stream": false, "type": "text",
 "messages": [{"role": "user", "content": {"content_type": "text", "parts": [
   {"type": "text", "text": "Here is my licence"},
   {"type": "file", "file": {"filename": "license.pdf", "file_data": "data:application/pdf;base64,…"}},
   {"type": "image_url", "image_url": {"url": "data:image/png;base64,…"}}]}}]}
```
- Parts may be plain strings, `text`, `image_url` or `file`. Attachments **must** be base64
  `data:` URLs (remote URLs → 400); they are written to `~/work/incoming/` and replaced by an
  "Attachments available in the agent workspace:" manifest.
- Response: `{"id": "<session_id>", "choices": [{"message": {"content": …}}]}`. For bot sessions
  `content` is the **whole turn** (thinking, `**Tool Call: X**\nStatus: …` blocks, tool output).
- Omit `session_id` with a bot's app key (or `app_id` = the bot's `legacy_app_id`) to create a
  new instance; exactly one message is allowed then. Follow-ups: same key + `session_id`.
- Readiness wait 300 s; turn idle timeout 2 h.
- `POST /sessions/{id}/clear` wipes the conversation (sends `close_thread` to the harness).
- `POST /sessions/{id}/messages {content, interrupt?}` → `{prompt_id}`: fire-and-forget into the
  prompt queue (user keys only).

## Reading sessions

- `GET /sessions/{id}/interactions?per_page=N&order=asc|desc&page=0` ✓ →
  `{interactions, page, pageSize, totalCount, totalPages}`. **`page` is 0-based.**
  - Each interaction: `id`, `created`, `completed`, `state` (`waiting|complete|error`), `error`,
    `prompt_message`, `usage`, `response_entries`.
  - `response_entries` types: `text` (content), `tool_call` (`tool_name`, `tool_status`,
    `tool_call_id`, `content` = header + output), `plan`.
  - `response_message` is blanked when entries exist. Entries are capped at the last 50, each
    truncated to 100 KB.
- `GET /sessions/{id}/interactions/{iid}`, `GET /sessions/{id}?skipInteractions=1`.
- `GET /sessions/{id}/zed-config` — effective context servers and model for a session.
- `GET /external-agents/{sid}/workspace-skills` — skills actually linked.
- `GET /agents/{legacy_app_id}/llm-calls?session=ses_…` — raw LLM calls (tokens, TTFT).
  `interaction_id` is not set for bot sessions, so filter by session and time.
- Main session transcript: MCP `bot_log {botId, limit, since, activationId}` or
  `GET /orgs/{org}/triggers/s-transcript-<bot>/events?limit=100`. Instances are not mirrored.

## Sandboxes (exec, files, screenshots)

Every instance and main session is backed by a row in
`GET /organizations/{org_id}/sandboxes` ✓. Match it with `session_id` (the row also carries
`org_bot_id`, `runtime`, `status`).

| Call | Use |
|---|---|
| `POST /organizations/{org_id}/sandboxes/{sbx}/commands` ✓ | `{cmd, args[], cwd?, env?, timeout_seconds?, detached?}` → `{stdout, stderr, exit_code}`. Runs as root |
| `PUT …/files?path=/home/retro/work/incoming/x.pdf` ✓ | Raw body, `application/octet-stream`. Written root-owned, 0644 |
| `GET …/files?path=…`, `GET …/files/list`, `DELETE …/files?path=…` | Read, list, delete |
| `GET …/screenshot` | JPEG. Desktop runtime only |

CLI equivalents: `helix sandbox exec|write|read|ls|screenshot <sbx> --org <org>`. For main
sessions there is also `helix spectask exec|screenshot <ses_id>`.

## App keys, gateway scope

- `POST /api_keys {"name", "type":"app", "app_id":"<legacy_app_id>"}` ✓ → the key as a bare JSON
  **string**. `GET /api_keys?types=app&app_id=…` ✓, `DELETE /api_keys?key=…` ✓.
- CLI: `helix org bots appkey <bot> create|list|delete`, `helix session send - "…" --key <key>`.
- An app key may call only `/v1/chat/completions` and `/api/v1/sessions/chat`; anything else is
  403 "path not allowed for app API keys" ✓.
- It may chat in any session of its own app, **including other customers' instances** ✓. Keep it
  server-side.
- The key owner must be an org member. Instances it creates are owned by that user.

## Webhooks

Org owner only; `{id}` is the org id.
- `POST /organizations/{id}/webhook-endpoints`
  - Body: `{url, description?, project_id?, events?: ["bot_instance.turn_completed"], enabled?}`
  - Returns `{endpoint, secret: "whsec_…"}`. **The secret is shown once.**
  - The URL must be https and public, unless `WEBHOOK_ALLOW_PRIVATE_ENDPOINTS` is set. Max 25 per org.
- Other routes:
  - `GET` the same path
  - `PUT` / `DELETE …/{ep}`
  - `POST …/{ep}/rotate-secret`: the old secret keeps signing for 24 h
  - `GET …/{ep}/deliveries`: last 50
  - `POST …/{ep}/deliveries/{d}/replay`
- Event `bot_instance.turn_completed`:
  - `data`: `{session_id, interaction_id, bot_id, app_id, project_id, organization_id, state, response, error?}`
  - `response` is the whole turn blob (see Chat).
  - Signed with Standard Webhooks headers: `webhook-id` (delivery id), `webhook-timestamp`, `webhook-signature`.
  - Up to 8 attempts; a 410 response disables the endpoint.

## LLM calls (judge, simulated customer)

`POST /v1/chat/completions?app_id=<app>` with a user key ✓ is OpenAI-compatible:
- The `app_id` is what gives the call an org for billing. Without it you get
  "failed to check balance: … org_id not specified".
- The app's system prompt **replaces** your system message ✓. Use a dedicated neutral app for
  the judge (`assets/judge-agent.yaml`) and put instructions in the user message.
- `model` accepts a bare model name or `<provider_id>/<model>`.

## helix-org tool catalogue (for `tools` / `instance_profile.tools`)

- **Base (every bot)**: `managers`, `reports`, `list_bots`, `get_bot`, `list_triggers`,
  `get_trigger`, `list_trigger_events`, `read_events`, `bot_log`, `get_secret`, `list_secrets`,
  `list_processors`, `get_processor`.
- **Default worker adds**:
  - `chat`: post to a channel/trigger
  - `dm`: manager or direct reports only
  - Discovery: `list_projects`, `get_project`, `list_repositories`, `list_bot_repositories`,
    `list_assets`, `get_asset`
  - The 14 `*_spectask*` tools
- **Owner set adds**:
  - Bots: `create_bot`, `set_bot_content`, `attach_tool`, `detach_tool`, `delete_bot`
  - Triggers and processors: `create_trigger`, `trigger_members`, `attach_worker`,
    `detach_worker`, `create_processor`, `update_processor`, `delete_processor`
  - Repositories: `attach_repository`, `detach_repository`
  - Lifecycle: `start_bot`, `stop_bot`, `restart_bot`
  - Instances: `create_bot_instance`, `list_bot_instances`, `delete_bot_instance`
  - Sandboxes: `list_sandbox_runtimes`, `list_sandboxes`, `get_sandbox`, `create_sandbox`,
    `update_sandbox`, `delete_sandbox`, `sandbox_ssh_access`
  - Asset management: `list_org_assets`, `get_org_asset`, `create_server_asset`,
    `update_server_asset`, `delete_asset`, `list_asset_links`, `link_asset`, `unlink_asset`,
    `get_asset_health`
- **Via asset links**: `server_run_command`, `server_read_file`, `server_write_file`, …
- The helix-org MCP endpoint needs a session-scoped key, so a plain user key cannot call these
  tools. Use REST.

## Triggers and channels (main sessions only)

System channels are local triggers:
- `s-team-<manager>`: team chat
- `s-dm-<a>-<b>`: DMs, ids sorted
- `s-transcript-<bot>`

Other routes:
- Triggers: `GET/POST /orgs/{org}/triggers`, `GET /orgs/{org}/triggers/{id}/events`
- Trigger kinds: `local`, `webhook`, `email`, `github`, `gitlab`, `cron`, `slack`, `helix_events`
- Inbound webhook: `POST /orgs/{org}/webhooks/{trigger_id}` (Bearer key)

Instances ignore triggers and channels.
