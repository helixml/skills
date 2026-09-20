# Board recipes

Move everything merged into Done:

```bash
helix spectask board --project prj_01xxx --status pull_request --json \
  | jq -r '.[] | select(.merged_to_main) | .id' \
  | xargs -rn1 -I{} helix spectask move {} done
```

Triage: label every failed task and bump it:

```bash
helix spectask board --project prj_01xxx --json \
  | jq -r '.[] | select(.status | endswith("_failed")) | .id' \
  | while read id; do
      helix spectask label add "$id" needs-triage
      helix spectask update "$id" --priority high
    done
```

Archive everything done older than 30 days:

```bash
cutoff=$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)
helix spectask board --project prj_01xxx --status done --json \
  | jq -r --arg c "$cutoff" '.[] | select(.updated_at < $c) | .id' \
  | xargs -rn1 helix spectask archive
```
