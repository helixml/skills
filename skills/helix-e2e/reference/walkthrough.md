# Full end-to-end walkthrough

## Contents
- 0. Account and key
- 1. Organization
- 2. Project
- 3. Agent
- 3b. Pre-flight the sandbox runner
- 4. Dispatch a task
- 5. Wait for the sandbox
- 6. Chat with the running agent
- 7. Board mechanics
- 8. Approve and check the PR
- 9. Tear down

## 0. Account and key

There is no `helix` subcommand for registration, but there *is* an API for it — you do not need a
browser:

```bash
export HELIX_URL=http://localhost:8080

curl -sS -X POST "$HELIX_URL/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"e2e@example.com","password":"hunter2hunter2",
       "password_confirm":"hunter2hunter2","full_name":"E2E User"}'
```

`password_confirm` is required — omit it and the request fails. A successful call returns 200 with
a JWT, and **an `hl-` API key is created for the account automatically**, so there is no trip to
Account → API Keys either:

```bash
TOKEN=$(curl -sS -X POST "$HELIX_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"e2e@example.com","password":"hunter2hunter2"}' | jq -r .token)

export HELIX_API_KEY=$(curl -sS "$HELIX_URL/api/v1/api_keys" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].key')

helix organization list          # must succeed before you continue
```

Two things people expect here that are **not** true:

- **The first registered user is not automatically an admin.** On a fresh deployment the first
  and only account comes back with `"admin": false` (and `admin = f` in the database). Anything
  needing admin — `helix user list`, `helix system settings` — needs `ADMIN_USER_IDS` set on the
  control plane.
- The browser onboarding flow asks you to create an organization before other pages work. That's
  a UI constraint; from the API you can go straight to step 1.

Registering in the browser at `$HELIX_URL` also works and is fine if you have one.

## 1. Organization

```bash
export ORG=e2e-$(date +%s)
helix organization create -n "$ORG" -d "E2E Test Org"
export HELIX_ORG="$ORG"          # every org-scoped command picks this up
helix organization list | grep "$ORG"
```

Optional — prove multi-tenancy works:

```bash
helix team create -o "$ORG" -n platform
helix member add -o "$ORG" -u teammate@example.com -r member
helix member list -o "$ORG"
helix roles list -o "$ORG"
```

## 2. Project

Fastest path — fork a bundled sample, which brings its own repo and seed tasks:

```bash
helix project samples                    # modern-todo-app, clone-demo-shapes, helix-in-helix
helix project fork modern-todo-app -n "E2E Project" -o "$ORG"
helix project list -o "$ORG"
export PROJECT=prj_...                   # id from the output
```

Or apply your own project, which also creates its coding agent:

```yaml
# e2e-project.yaml
apiVersion: helix.ml/v1alpha1
kind: Project
metadata:
  name: e2e-project
spec:
  description: "End-to-end verification project"
  repository:
    url: "https://github.com/your-org/your-repo"
    branch: main
  agent:
    name: "E2E Coding Agent"
    runtime: claude_code
    model: claude-sonnet-4-6
    provider: anthropic
```

```bash
helix apply -f e2e-project.yaml -o "$ORG"
helix api /projects/$PROJECT/repositories        # must NOT be []
```

**Check that last line.** A project with no repository accepts tasks and then fails them at
workspace setup with `No primary repository specified` — after several minutes of what looks
like normal planning. Attaching an external repo needs git provider OAuth; if you don't have it,
create a Helix-hosted repo instead (recipe in [helix-board](../../helix-board/SKILL.md)).

## 3. Agent

```bash
helix spectask list-agents -o "$ORG"
export AGENT=app_...
```

**Do not trust this list alone.** Spec tasks need `agent_kind: coding_agent`, and `list-agents`
prints `agent_type`, not kind — so a helix-org bot shows up as `zed_external` with a ready-made
`spectask start` line and is then refused:

```
spec tasks requires agent kind "coding_agent", got "org_agent"
```

Confirm before dispatching:

```bash
helix api /apps | jq -r '.[] | select(.agent_kind=="coding_agent") | "\(.id) \(.config.helix.name)"'
```

If nothing comes back, the org has no coding agent — add one via the project YAML's `agent:`
block (step 2), which is classified `coding_agent`, and re-check. See
[helix-spec-tasks](../../helix-spec-tasks/SKILL.md) for the full three-attribute picture.

## 3b. Pre-flight the sandbox runner

Do this before dispatching anything — a missing sandbox node is the single most common reason an
otherwise healthy deployment never runs a task, and it's much cheaper to catch here than after a
ten-minute wait in step 5.

```bash
helix api /sandboxes | jq -r '.[] | "\(.id) \(.status) active=\(.active_sandboxes)/\(.max_sandboxes)"'
helix sandbox runtimes

# exercises API → RevDial → Hydra → nested dockerd → container
helix sandbox create --name preflight --runtime headless-ubuntu --ttl 300
helix sandbox exec sbx_... -- bash -lc "echo hydra ok"
helix sandbox delete sbx_...
```

Empty output from the first command means no sandbox node is registered — install one
(`./install.sh --sandbox`) before continuing. See [helix-deploy](../../helix-deploy/SKILL.md).

## 4. Dispatch a task

Start with a small, self-contained change so the run finishes quickly:

```bash
export TASK=$(helix spectask start \
  --project "$PROJECT" --agent "$AGENT" \
  -n "E2E: add a CONTRIBUTING note" \
  --prompt "Add a short 'Running the tests' section to CONTRIBUTING.md describing how to run the test suite. Do not change any code." \
  -q)
echo "task: $TASK"
```

`start` returns as soon as the task exists — the sandbox provisions in the background, so this is
expected, not a failure.

## 5. Wait for the sandbox

```bash
for i in $(seq 1 60); do
  row=$(helix spectask board --project "$PROJECT" --json \
        | jq -r --arg t "$TASK" '.[] | select(.id==$t) | "\(.status) \(.sandbox_state // "absent")"')
  echo "[$i] $row"
  [ "${row##* }" = "running" ] && break
  sleep 10
done
export SESSION=$(helix spectask get "$TASK" --json | jq -r .planning_session_id)
```

**Poll the board, not `get`.** `sandbox_state` is computed by the list endpoint only — on a
single-task fetch it comes back `null` no matter what the container is doing, so a loop written
around `helix spectask get … | jq .sandbox_state` never terminates. `status` and
`planning_session_id` are correct on both.

Ten minutes is a reasonable ceiling on a cold host (image pull). A desktop runtime should also
answer a screenshot once it's up:

```bash
cd /tmp && helix spectask screenshot "$SESSION"    # writes screenshot-<timestamp>.jpg here
```

Headless tasks (`--runtime headless-ubuntu`) have no compositor — skip the screenshot for those.

## 6. Chat with the running agent

```bash
helix spectask send "$TASK" "What repository are you working in, and what's the current branch?" \
  --wait --max-wait 300 --json

helix spectask interact "$TASK" --history --count 5
```

This is the step that proves the whole path: CLI → API → RevDial → sandbox → agent → back. If
messages land but nothing comes back, the agent isn't connected — see step 11.

Inspect the container directly if you need to — remembering that `exec` only runs allowlisted
binaries (`ls`, `cat`, `echo`, `test`, …), with no shell:

```bash
helix spectask exec "$SESSION" ls /home/retro/work
helix spectask exec "$SESSION" cat /home/retro/work/README.md
```

For anything needing a real shell, ask the agent instead:
`helix spectask send "$TASK" "run git status and paste the output" --wait`.

## 7. Board mechanics

```bash
helix spectask board --project "$PROJECT"
helix spectask label add "$TASK" e2e
helix spectask update "$TASK" --priority high
helix spectask get "$TASK"
```

## 8. Approve and check the PR

The task parks in `spec_review` waiting for a human — this is a gate, not a hang:

```bash
helix spectask get "$TASK" --json | jq -r .status      # spec_review?
helix spectask approve "$TASK"                          # → implementation starts

for i in $(seq 1 90); do
  s=$(helix spectask get "$TASK" --json | jq -r .status)
  echo "[$i] $s"
  case "$s" in pull_request|done|*_failed) break;; esac
  sleep 20
done

helix spectask get "$TASK" --json | jq -r '.repo_pull_requests[]? | "\(.pr_url) \(.pr_state) ci=\(.ci_status)"'
```

Approving specs needs the approver to have git provider OAuth connected — an `oauth_required`
response means connect GitHub/GitLab/Azure DevOps in the web UI first.

Once the PR is merged, `helix spectask approve "$TASK" --implementation` (or letting the merge
poll notice) closes the task out at `done`.

## 9. Tear down

```bash
helix spectask archive "$TASK"        # stops the agent and frees the sandbox
helix spectask delete "$TASK" -f      # only if you want it gone entirely
helix organization delete "$ORG"      # removes the whole test org
```

Archive first. Deleting the org while a sandbox is still running leaves the container to be
reaped rather than stopped cleanly.

## Old patterns

<details>
<summary>Before helixml/helix#3033: steps 4–9 need <code>helix api</code> equivalents</summary>

Steps 4–9 use board commands that landed in helixml/helix#3033. On an older binary, substitute
the `helix api` equivalents listed in [helix-board](../../helix-board/SKILL.md), or run the
built-in `helix spectask e2e` harness, which works on every version.

</details>
