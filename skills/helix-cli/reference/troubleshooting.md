# CLI troubleshooting

| Symptom | Cause |
|---|---|
| `401 unauthorized` | `HELIX_API_KEY` missing/expired, or you used the runner token |
| `403 ... record not found` | The key's user isn't a member of that project's org — this is authz, not a missing row |
| Command hangs printing an org list | Interactive org prompt; pass `--org`/`-o` or set `HELIX_ORG` |
| `connection refused` | Wrong `HELIX_URL`, or the control plane is still starting — see [helix-deploy](../../helix-deploy/SKILL.md) |
| `project has no default coding agent` | The project has no agent attached; pass `--agent app_…` or set one on the project |
| No API key found, but you are in a sandbox | Session bootstrap did not complete — see [helix-session](../../helix-session/SKILL.md) |
| `helix secret list` shows a name but no value | Expected: listings never return values — see [helix-session](../../helix-session/SKILL.md) |
