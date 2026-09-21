# `helix api` and scripting

## Contents
- The escape hatch
- Output formats for scripting

## The escape hatch

Not every endpoint has a first-class command. `helix api` is `gh api` for Helix: same
credentials, any path, any method.

```bash
helix api /projects?organization_id=org_01xxx
helix api /spec-tasks?project_id=prj_01xxx
helix api -X PUT /spec-tasks/spt_01xxx --input '{"priority":"critical"}'
helix api -X POST /orgs/acme/bots/chief-of-staff/activate
echo '{"label":"bug"}' | helix api -X POST /spec-tasks/spt_01xxx/labels --input -
helix api -X POST /projects --input @project.json
```

- Path may be `/projects`, `/api/v1/projects`, or `projects` — all resolve.
- `--input` takes a JSON string, `@file`, or `-` for stdin. `-f key=value` sets a single string
  field when there's no body.
- `--timeout` is in seconds (default 120).

**There is no endpoint that returns a secret's value.** `/secrets` and friends list metadata
only, and no query parameter changes that. If a first-class command did not give you a value,
guessing paths here will not either — see
[secrets-and-providers.md](secrets-and-providers.md) for the two routes that do work.

When you find yourself scripting the same `helix api` call repeatedly, that's a missing CLI
command — the CLI lives in `api/pkg/cli/` in the helix repo and new commands are small cobra
files.

## Output formats for scripting

Most commands print human-readable tables. For scripting, prefer:

- `--json` where offered (`spectask board`, `spectask get`, `org agents list`, …)
- `helix agent inspect <id> --output json`
- `helix api <path>` — always raw JSON, always parseable

```bash
# every task id on a board
helix spectask board --project prj_01xxx --json | jq -r '.[].id'

# the session behind a task
helix api /spec-tasks/spt_01xxx | jq -r '.planning_session_id'
```
