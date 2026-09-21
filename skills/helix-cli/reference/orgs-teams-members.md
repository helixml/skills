# Organizations, teams and members

## Contents
- Organizations
- Teams
- Members and roles
- Admin-only commands

`--org`/`-o` accepts a name or an `org_…` id throughout. Omit it and the CLI uses `$HELIX_ORG`,
or prompts when you belong to several organizations.

## Organizations

```bash
helix organization list
helix organization create -n acme -d "Acme Corp"        # -n slug, -d display name
helix organization delete acme                          # accepts id or name
```

## Teams

```bash
helix team list -o acme
helix team create -o acme -n platform
helix team inspect -o acme -t platform
helix team delete -o acme -t team_01xxx
```

## Members and roles

```bash
helix member list -o acme                               # add -t platform for one team
helix member add -o acme -u dev@acme.com -r member      # roles: owner | member
helix member add -o acme -t platform -u dev@acme.com    # add to a team
helix member remove -o acme -u dev@acme.com -f

helix roles list -o acme
```

## Admin-only

```bash
helix user list
helix user reset-password
helix system settings get
```
