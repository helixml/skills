# Knowledge and RAG

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

