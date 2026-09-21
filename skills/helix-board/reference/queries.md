# Reading and filtering the board

```bash
helix spectask board --project prj_01xxx
helix spectask board --project prj_01xxx --status spec_review
helix spectask board --project prj_01xxx --label bug --label ui        # AND semantics
helix spectask board --project prj_01xxx --assignee usr_01xxx
helix spectask board --project prj_01xxx --include-archived
helix spectask board --project prj_01xxx --json | jq -r '.[] | "\(.id) \(.status) \(.name)"'
```

Older binaries: `helix project tasks prj_01xxx`, or
`helix api "/spec-tasks?project_id=prj_01xxx"`.

One card:

```bash
helix spectask get spt_01xxx            # --json for the full record
helix spectask progress spt_01xxx       # spec + implementation phase timings
```

One asymmetry to know about: `sandbox_state` (and `queue_reason`'s sandbox context) is computed
by the **list** endpoint, so it is populated in `board` output but comes back `null` from `get`.
Poll the board when you're waiting for a sandbox to come up; `get` is right about everything
else.

