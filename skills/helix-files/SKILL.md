---
name: helix-files
description: Get files into Helix — upload to the filestore, list and remove filestore paths, sync a local directory into an agent's knowledge base with `helix apply --rsync`, index websites and documents as RAG knowledge, search and version that knowledge, and attach context files to spec tasks. Use when the user wants to upload files to Helix, build a knowledge base or RAG index, attach logs/screenshots to a task, or move files in and out of a Helix sandbox.
---

# Files, uploads and knowledge in Helix

There are four distinct places a file can go in Helix. Picking the wrong one is the usual
mistake, so start here:

| Destination | Use it for | Command |
|---|---|---|
| **Filestore** | Raw storage, and the backing store for filestore-sourced knowledge | `helix upload`, `helix filesystem` |
| **Knowledge / RAG** | Documents an agent should be able to search and cite | knowledge in agent YAML + `helix apply --rsync` |
| **Spec task attachments** | Logs, screenshots, briefs a *specific* task's agent should read | `helix spectask attach` / `--attach` |
| **Sandbox filesystem** | Files a running container needs right now | `helix spectask copy`, `helix sandbox write` |

Read [helix-cli](../helix-cli/SKILL.md) for auth first.

## Filestore

```bash
helix upload ./report.pdf docs/report.pdf        # local → remote
helix upload ./docs/ manuals/                    # directories upload recursively
helix filesystem ls                              # root
helix filesystem ls manuals/
helix filesystem remove docs/report.pdf
```

`helix upload` is a shortcut for `helix filesystem upload`; `filesystem` also aliases to `fs`.
A directory upload walks the tree and preserves relative paths under the remote prefix.

## Knowledge (RAG)

Knowledge is declared on an agent, not created by a standalone command. Sources can be inline
content, a filestore path, or a list of URLs to crawl:

```yaml
# agent.yaml
name: support-bot
assistants:
  - name: Helix
    model: claude-sonnet-4-6
    knowledge:
      - name: manuals                 # files you uploaded to the filestore
        source:
          filestore:
            path: manuals/
      - name: docs-site               # crawled with the built-in scraper
        source:
          web:
            urls:
              - https://docs.example.com/getting-started
              - https://docs.example.com/api
      - name: facts                   # inline, for small fixed context
        source:
          content: |
            Support hours are 09:00–17:00 UTC.
            Escalation goes to #support-escalation.
```

Apply it, syncing a local directory into the filestore in the same step:

```bash
# push ./docs into the filestore behind the "manuals" knowledge source, then index
helix apply -f agent.yaml --rsync ./docs:manuals --wait-knowledge

# several sources
helix apply -f agent.yaml --rsync ./docs:manuals --rsync ./faq:faqs

# mirror deletions too
helix apply -f agent.yaml --rsync ./docs:manuals --delete

# force a full re-index of everything
helix apply -f agent.yaml --refresh-knowledge --wait-knowledge --knowledge-timeout 15m
```

`--rsync ./local/path[:knowledge_name]` — omit the name and it targets the agent's first
knowledge source. `--wait-knowledge` blocks until indexing finishes (default timeout 5m, raise it
with `--knowledge-timeout`); without it the command returns while indexing is still running, which
is exactly how you end up querying an empty index.

Inspect and query what got indexed:

```bash
helix knowledge list -o acme
helix knowledge inspect kno_01xxx
helix knowledge versions kno_01xxx
helix knowledge search --knowledge kno_01xxx --prompt "how do I rotate the signing key?"
helix knowledge search --app app_01xxx --prompt "refund policy"
helix knowledge remove kno_01xxx
```

Knowledge is organization-scoped, so `helix knowledge list` needs `-o` (or `HELIX_ORG`) when you
belong to more than one org.

## Spec task attachments

Attachments are how you give one task's agent bulky context — a failing CI log, a screenshot of
the bug, a design doc — without pasting it into the prompt. The agent reads them inside its
sandbox at `design/tasks/<task>/attachments/<name>`.

```bash
# at creation
helix spectask start --project prj_01xxx --prompt "Fix this crash" \
  --attach ./crash.log --attach ./screenshot.png

# on an existing task
helix spectask attach spt_01xxx ./failing-run.log ./trace.txt
helix spectask attachments spt_01xxx
helix spectask attachments spt_01xxx --json
helix spectask attachments spt_01xxx --delete att_01xxx
```

Limits: 100 MB per file, 500 files per task, and the MIME type must be one of PNG, JPEG, GIF,
WebP, SVG, PDF, plain text, Markdown, or CSV. A `.log` file uploads fine as `text/plain`; a
`.tar.gz` will be rejected — extract it or convert first.

For a long brief, prefer `--prompt-file ./brief.md` over an attachment: it goes straight into the
prompt, so the agent reads it without having to be told to.

> `helix spectask attach` / `attachments` landed in helixml/helix#3033 — merged to main, shipping in the first release after 2.12.3. On older binaries the
> `--attach` flag on `start` works, and you can POST multipart to
> `/api/v1/spec-tasks/<id>/attachments` directly.

## Files in and out of a running container

```bash
# spec task container — session id first, then the local file
helix spectask copy ses_01xxx ./patch.diff                       # → ~/work/incoming/patch.diff
helix spectask copy ses_01xxx ./config.json --dest /home/retro/work/config.json
helix spectask exec ses_01xxx ls /home/retro/work/incoming       # `exec` is allowlisted:
helix spectask exec ses_01xxx cat /home/retro/work/incoming/patch.diff   # ls/cat/echo/test only

# standalone sandbox
echo "hello" | helix sandbox write sbx_01xxx /root/in.txt --mode 644
helix sandbox read sbx_01xxx /root/out.txt
helix sandbox ls sbx_01xxx --path /root
```

These write into ephemeral container storage. Anything you want to keep must be committed to the
repo by the agent, uploaded to the filestore, or read back out before the sandbox goes away.

## Choosing between them

- The agent should be able to **search** it later, across tasks → knowledge.
- **One task** needs to read it → attachment.
- A **running container** needs it on disk now → `copy` / `sandbox write`.
- You just need it **stored** somewhere Helix can reach → filestore.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Agent can't find uploaded documents | Indexing hadn't finished — re-run with `--wait-knowledge` |
| Attachment upload rejected | MIME type not on the allowlist, or over 100 MB |
| `--rsync` uploaded nothing | The `:knowledge_name` doesn't match a knowledge source in the YAML |
| Stale answers after replacing docs | Add `--refresh-knowledge` to force a re-index |
| Deleted local files still answered | `--rsync` doesn't delete by default; add `--delete` |
