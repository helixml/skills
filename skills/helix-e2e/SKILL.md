---
name: helix-e2e
description: Use when verifying that a Helix deployment actually works end to end — after a fresh install or an upgrade, when proving the full spec-task loop from organization through to a pull request, or when reproducing a bug against a clean project.
---

# End-to-end test of a Helix deployment

The "does the whole thing actually work" pass: org → project → agent → task → chat → approve →
PR → cleanup. Run it after an install, after an upgrade, or when a bug report needs a clean
reproduction.

Prerequisites: a running control plane ([helix-deploy](../helix-deploy/SKILL.md)), a `helix`
binary, and a user API key.

## Try the built-in harness first

For a post-upgrade check that doesn't need a new org, the CLI ships its own harness — this is
the cheap path, and it works on every version:

```bash
helix spectask e2e --project "$PROJECT" --agent "$AGENT" \
  --prompt "List the files in the repo" --cleanup
helix spectask test --session "$SESSION" --all --json
```

`spectask e2e` creates a task, boots the sandbox, cancels a live turn, sends a follow-up,
screenshots, and exercises the session MCP tools — a good regression check for the sandbox path
specifically. It does **not** cover org creation, project YAML, spec approval or the PR.

## The full pass

Copy this checklist and tick items off as you go:

```
- [ ] 0. Account and API key
- [ ] 1. Organization
- [ ] 2. Project (with a repository attached)
- [ ] 3. Agent, and pre-flight the sandbox runner
- [ ] 4. Dispatch a task
- [ ] 5. Wait for the sandbox
- [ ] 6. Chat with the running agent
- [ ] 7. Board mechanics
- [ ] 8. Approve and check the PR
- [ ] 9. Tear down
```

Every step, with the commands and what each one proves:
[reference/walkthrough.md](reference/walkthrough.md).

When a step fails, match the symptom: [reference/failures.md](reference/failures.md).

Two failures account for most first runs — the project has no repository attached (step 2), and
there is no sandbox node registered (step 5). Check both before anything else:

```bash
helix api /projects/$PROJECT/repositories     # [] means step 2 will fail
helix api /sandboxes                          # [] means step 5 will never finish
```
