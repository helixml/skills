---
name: helix-artifacts
description: Build, publish, update, inspect, list, and delete project-scoped Helix Artifacts. Use when a user asks for an interactive page, dashboard, visualization, prototype, report, shareable HTML, or compiled static SPA that should be stored and served by Helix rather than run in a sandbox.
---

# Helix Artifacts

Publish finished static output with `helix artifact`. Artifacts inherit project RBAC, keep immutable content versions, and need no running sandbox.

## Choose the artifact form

- Use one self-contained `.html` file for documents, reports, diagrams, and small interactive experiences.
- Use a directory for a compiled SPA. Build it first and publish only the static output directory such as `dist/` or `build/`.
- Do not publish source trees, dependency directories, development servers, server-side applications, secrets, or API keys.
- Make asset URLs relative. A canonical artifact runs below `/artifacts/<id>/`; absolute paths such as `/assets/app.js` point at Helix, not the artifact.

## Create

Use the current project automatically when `HELIX_PROJECT_ID` is set:

```bash
helix artifact create report.html --name "Experiment report"
helix artifact create dist/ --name "Capacity dashboard"
```

Outside an agent workspace, pass the project explicitly:

```bash
helix artifact create dist/ --project prj_01xxx --name "Capacity dashboard"
```

Artifacts are project-private by default. Make publication an explicit user or task requirement:

```bash
helix artifact create dist/ --name "Public demo" --visibility public
helix artifact create dist/ --name "Public demo" --visibility public --subdomain
```

Use `--subdomain` only when the user wants a directly shareable public hostname. Public canonical `/artifacts/<id>/` pages are intentionally browser-sandboxed because they share the Helix hostname. Project-private artifacts transparently bootstrap into an isolated authenticated origin so multi-file apps work without exposing a public URL. A requested subdomain is public; never use it for private content.

For a nonstandard HTML entrypoint:

```bash
helix artifact create dist/ --name "Demo" --entrypoint app.html
```

The CLI records `HELIX_SESSION_ID` and `HELIX_SPEC_TASK_ID` automatically when the target matches `HELIX_PROJECT_ID`. An org worker may pass `--project` for another project it is authorized to manage; the CLI then omits current-session provenance. Do not override provenance unless the user supplies a valid same-project ID.

## Verify

Create with `--json`, inspect the returned `url`, then fetch or open that exact URL. For SPAs, verify both the root and one client-side route. Do not report completion after only running the frontend build.

```bash
helix artifact create dist/ --name "Demo" --json
helix artifact get art_01xxx --json
```

Before publishing, confirm:

- The entrypoint exists and renders without a development server.
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
helix artifact update art_01xxx --visibility public --subdomain
helix artifact update art_01xxx --visibility project --subdomain=false
helix artifact delete art_01xxx
```

Updating content creates a new immutable version and keeps the artifact ID and URL stable. Metadata-only updates do not create a content version. Deletion removes every stored version and its subdomain route.

## Authentication

Agent workspaces use `HELIX_API_URL`, `USER_API_TOKEN`, and `HELIX_PROJECT_ID`. A local operator can instead set `HELIX_URL`, `HELIX_API_KEY`, and pass `--project`. Never print tokens or place them in artifact content.
