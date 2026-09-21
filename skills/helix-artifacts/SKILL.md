---
name: helix-artifacts
description: Use when an agent is asked for an interactive page, dashboard, visualization, prototype, report, PDF, image, shareable HTML, or compiled static SPA that should be uploaded to and served by a Helix project rather than left in a sandbox, or when updating, listing or deleting one that already exists.
---

# Helix Artifacts

Publish finished static output with `helix artifact`. Artifacts inherit project RBAC, keep immutable content versions, and need no running sandbox.

## Resolve the organization and project

Identify the project before building or uploading. Never guess when multiple projects have similar names.

1. In a project agent workspace, use `HELIX_PROJECT_ID`. `HELIX_ORGANIZATION_ID` identifies its organization. Confirm the target when needed:

   ```bash
   helix api "/projects/${HELIX_PROJECT_ID}"
   helix artifact list --project "${HELIX_PROJECT_ID}"
   ```

2. When the user gives a Helix project URL such as `/orgs/acme/projects/prj_01xxx/artifacts`, read `acme` as the organization reference and `prj_01xxx` as the project ID. Use the ID with artifact commands; do not substitute the project name.

3. Outside a project workspace, navigate from organizations to projects:

   ```bash
   helix organization list
   helix project list --org acme
   helix artifact list --project prj_01xxx
   ```

   Set `HELIX_ORG=acme` to make the organization the CLI default. In non-interactive work, always pass `--org` when several organizations are available so the CLI does not stop for a prompt.

The project artifacts page is `${HELIX_URL}/orgs/<org-name>/projects/<project-id>/artifacts`. Created artifacts use the stable viewer path `${HELIX_URL}/artifacts/<artifact-id>`.

## Choose the artifact form

- Use one self-contained `.html` file for documents, reports, diagrams, and small interactive experiences.
- Use a directory for a compiled SPA. Build it first and publish only the static output directory such as `dist/` or `build/`.
- Upload a `.pdf` directly when the desired result is a finished document. Helix opens it with the browser's native PDF viewer; do not wrap it in HTML.
- Upload an image directly for a finished visual, diagram, export, or mockup. Helix displays it responsively; do not create an HTML wrapper only to show the image.
- Do not publish source trees, dependency directories, development servers, server-side applications, secrets, or API keys.
- Make asset URLs relative so the same build works on its isolated artifact origin and across local deployments.

## Create

Use the current project automatically when `HELIX_PROJECT_ID` is set:

```bash
helix artifact create report.html --name "Experiment report"
helix artifact create dist/ --name "Capacity dashboard"
helix artifact create report.pdf --name "Quarterly report"
helix artifact create architecture.png --name "System architecture"
```

Outside an agent workspace, pass the project explicitly:

```bash
helix artifact create dist/ --project prj_01xxx --name "Capacity dashboard"
```

Artifacts are project-private by default. Make publication an explicit user or task requirement:

```bash
helix artifact create dist/ --name "Public demo" --visibility public
```

The stable `/artifacts/<id>` URL opens Helix's artifact viewer with a permission-checked toolbar. HTML renders in a sandboxed isolated-origin frame. PDFs use a permission-checked document route and the browser's native controls. Images render in a contained responsive view. Project-private artifacts render only inside that viewer. Public artifacts automatically receive an isolated share subdomain; the viewer's Share menu copies it or makes the artifact private again. Never publish unless the user or task explicitly requires public access.

For a nonstandard HTML entrypoint:

```bash
helix artifact create dist/ --name "Demo" --entrypoint app.html
```

The CLI records `HELIX_SESSION_ID` and `HELIX_SPEC_TASK_ID` automatically when the target matches `HELIX_PROJECT_ID`. An org worker may pass `--project` for another project it is authorized to manage; the CLI then omits current-session provenance. Do not override provenance unless the user supplies a valid same-project ID.

## Verify

Create with `--json`, inspect the returned `url`, then open that viewer URL. When public, also verify `subdomain_url`. For SPAs, verify both the root and one client-side route. Do not report completion after only running the frontend build.

```bash
helix artifact create dist/ --name "Demo" --json
helix artifact get art_01xxx --json
```

Before publishing, confirm:

- The entrypoint exists and renders without a development server.
- PDF and image artifacts are the intended final exported files, not source documents.
- Browser assets use relative URLs.
- No secrets, source maps containing secrets, `.env` files, or private data are present.
- Public visibility is actually intended.
- The result works at its returned URL.

## Manage

```bash
helix artifact list
helix artifact list --project prj_01xxx --json
helix artifact get art_01xxx
helix artifact update art_01xxx dist/
helix artifact update art_01xxx --name "New title"
helix artifact update art_01xxx --visibility public
helix artifact update art_01xxx --visibility project
helix artifact delete art_01xxx
```

Updating content creates a new immutable version and keeps the artifact ID and URL stable. Metadata-only updates do not create a content version. Deletion removes every stored version and its subdomain route.

## Authentication

Agent workspaces use `HELIX_API_URL`, `USER_API_TOKEN`, and `HELIX_PROJECT_ID`, all already exported — see [helix-session](../helix-session/SKILL.md). A local operator sets `HELIX_URL` and `HELIX_API_KEY` instead, and passes `--project`. Never print tokens or place them in artifact content.
