---
name: helix-files
description: Use when moving files into or out of Helix — uploading to the filestore, building or re-indexing a knowledge/RAG base, attaching logs or screenshots to a spec task, or copying files in and out of a running sandbox container.
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

> **Auth.** `export HELIX_URL=… HELIX_API_KEY=hl-…`, then `helix organization list` to verify.
> Inside a Helix sandbox this is already configured — see [helix-session](../helix-session/SKILL.md).

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

Declared on an agent, not created by a standalone command; `helix apply --rsync` syncs a local
directory into it and triggers indexing. Full guide, including source types, versioning, search
and the sync gotchas: [reference/knowledge.md](reference/knowledge.md).

## Spec task attachments

Attachments are how you give one task's agent bulky context — a failing CI log, a screenshot of
the bug, a design doc — without pasting it into the prompt.

They are committed onto the task's `helix-specs` branch when spec generation starts, and the
agent reads them inside its sandbox at:

```
~/work/helix-specs/design/tasks/<NNNNNN>_<slug>/attachments/<name>
```

The directory is the task **number** and a slug of its name (e.g. `000042_add-dark-mode`),
not the `spt_…` id — so tell the agent to `ls ~/work/helix-specs/design/tasks/` rather than
hard-coding a path. `requirements.md`, `design.md` and `tasks.md` land alongside `attachments/`.

Give each file a **distinct name**: they all land in one flat directory, so uploading seven files
called `SKILL.md` collides. Rename before uploading.

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

## Artifacts and reading files back (gotchas from practice)

Two things that aren't obvious and cost real time:

**Reading a file back out of the filestore.** There is no `helix filesystem download`/`cat`.
Files are served over HTTP: resolve the physical path, then GET the viewer URL with your key.

```bash
# GET /api/v1/filestore/get?path=<your relative path> returns metadata incl. .path
META=$(curl -s -H "Authorization: Bearer $HELIX_API_KEY" \
  "$HELIX_URL/api/v1/filestore/get?path=engagements/prj_01x/notes.md")
P=$(echo "$META" | jq -r '.path')            # e.g. dev/users/usr_.../engagements/prj_01x/notes.md
curl -s -H "Authorization: Bearer $HELIX_API_KEY" "$HELIX_URL/api/v1/filestore/viewer/$P"
```

Use this (not artifacts) for machine-readable state you write with `helix upload` and read back
in a later session.

**Artifacts** (`helix artifact create|list|update|get|delete`) publish a static page/doc into a
project (visible in the UI, optionally shared via a public subdomain):

```bash
helix artifact create ./report.html -n "Report" --project prj_01x \
  --entrypoint report.html --visibility project   # or --visibility public
helix artifact create ./report.pdf  -n "Report PDF" --project prj_01x
helix artifact update art_01x ./report.html --entrypoint report.html   # new version, stable URL
```

- **Single-file kinds:** HTML (`single_file`), PDF (`pdf`), an image (`image`), or **Markdown**
  (`.md` → kind `markdown`, rendered natively by the viewer). A directory uploads as a multi-file
  `spa` (needs `--entrypoint`). Other single files are rejected. Markdown is ideal for living
  docs like notebooks/READMEs — publish the `.md` directly, no HTML conversion.
- **Artifact content is NOT readable back via the API** — `GET /artifacts/<id>` returns metadata,
  and the content URL serves the viewer app, not the raw file. If you need the bytes back later,
  keep them in the filestore too.
- **Provenance** auto-fills from `HELIX_SESSION_ID` / `HELIX_SPEC_TASK_ID` when created inside a
  spec task, linking the artifact to the task that produced it.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Agent can't find uploaded documents | Indexing hadn't finished — re-run with `--wait-knowledge` |
| Attachment upload rejected | MIME type not on the allowlist, or over 100 MB |
| `--rsync` uploaded nothing | The `:knowledge_name` doesn't match a knowledge source in the YAML |
| Stale answers after replacing docs | Add `--refresh-knowledge` to force a re-index |
| Deleted local files still answered | `--rsync` doesn't delete by default; add `--delete` |
