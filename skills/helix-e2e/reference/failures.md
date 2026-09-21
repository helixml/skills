# When a step fails

| Step | Symptom | Where to look |
|---|---|---|
| 0 | `401` | Runner token instead of a user `hl-` key |
| 1 | Command hangs listing orgs | Interactive org prompt — export `HELIX_ORG` |
| 3 | No agents listed | No coding agent in the org; add one via the project YAML |
| 2 | Task fails minutes in with `No primary repository specified` | The project has no repo. `helix api /projects/<id>/repositories` returns `[]` |
| 5 | Sandbox stuck `absent`/`starting` | No sandbox/Hydra node, or `RUNNER_TOKEN` mismatch — `helix api /sandboxes` first, then `docker logs helix-sandbox` |
| 5 | Wait loop never finishes though the container is up | Polling `spectask get` for `sandbox_state`; it's only populated by the list/board endpoint |
| 5 | Screenshot 503 | RevDial not connected yet; retry before calling it broken |
| 6 | Message sent, no reply | Agent never connected. `helix spectask exec` into the container and check the agent process |
| 8 | Stuck in `spec_review` | Waiting on you — `helix spectask approve` |
| 8 | Stuck queued with `⏳` | WIP limit or dependency; check `queue_reason` |
| 8 | `oauth_required` | Connect the git provider in the web UI |
| 8 | No PR appears | Repo not attached to the project, or push credentials missing |

Log commands and database queries for each of these are in
[helix-deploy](../../helix-deploy/SKILL.md).
