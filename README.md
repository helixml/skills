# Helix agent skills

Agent skills for [Helix](https://github.com/helixml/helix) — a private agent fleet with
spec-driven coding. They teach a coding agent how to drive a Helix control plane from the
`helix` CLI: manage the Kanban board, dispatch and steer spec tasks, upload files and build
knowledge bases, configure agents, and install or debug a deployment.

## Install

```bash
npx skills add helixml/skills
```

Or copy the directories you want out of `skills/` into your agent's skills directory
(`.claude/skills/`, `.agents/skills/`, …).

## Skills

| Skill | Use it for |
|---|---|
| [helix-cli](skills/helix-cli/SKILL.md) | Install and authenticate the CLI, the command map, orgs/teams/members/secrets/providers, and the `helix api` escape hatch. **Start here.** |
| [helix-board](skills/helix-board/SKILL.md) | Projects and the Kanban board: project YAML, listing the board, creating and moving cards, labels, assignees, WIP limits, approvals, archiving. |
| [helix-spec-tasks](skills/helix-spec-tasks/SKILL.md) | Running work: start a task, watch and chat with its agent, exec in its sandbox, screenshot and stream the desktop, drive standalone sandboxes. |
| [helix-files](skills/helix-files/SKILL.md) | Getting files into Helix: filestore uploads, knowledge/RAG indexing and search, spec-task attachments, files in and out of containers. |
| [helix-agents](skills/helix-agents/SKILL.md) | Agent YAML (system prompts, OpenAPI tools, MCP servers, tests), chatting with agents, models and provider endpoints. |
| [helix-deploy](skills/helix-deploy/SKILL.md) | Install and debug: control plane on Compose or Helm, the **Hydra sandbox runner** that actually runs agent desktops, runtime config, health checks, logs, troubleshooting. |
| [helix-e2e](skills/helix-e2e/SKILL.md) | Prove a deployment works end to end: org → project → agent → task → chat → approve → PR → cleanup. |

## Quick start

```bash
export HELIX_URL=https://your-helix.example.com
export HELIX_API_KEY=hl-...            # Account → API Keys in the web UI
export HELIX_ORG=your-org              # optional default

helix organization list                            # check auth
helix project list                                 # find a project
helix spectask board --project prj_01xxx           # read the board
helix spectask start --project prj_01xxx --agent app_01yyy \
  -n "Add dark mode" --prompt "Users want a dark theme"
```

## Version note

The board and task-lifecycle commands (`helix spectask board|get|create|update|move|label|
attach|attachments|approve|archive|delete|progress`, and addressing a task by `spt_…` in
`send`/`interact`) come from [helixml/helix#3033](https://github.com/helixml/helix/pull/3033),
which is merged to `main` and ships in the first release after 2.12.3. Every skill that uses
them also gives the `helix api` equivalent, so the guidance holds on older binaries too.

## Contributing

Each skill is one directory under `skills/` containing a `SKILL.md` with YAML frontmatter:

```markdown
---
name: helix-something
description: One line describing what the skill covers and when to reach for it.
---
```

Keep commands verified against a real control plane — check `helix <command> --help` before
documenting a flag, and mark anything that isn't in a released binary yet.
