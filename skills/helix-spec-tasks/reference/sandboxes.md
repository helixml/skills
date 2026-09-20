# Standalone sandboxes

`helix sandbox` is a separate, lighter-weight API: a container with no board card and no coding
agent. Good for one-off compute, reproducing a build, or scripted environments.

```bash
helix sandbox runtimes                                  # what the server offers
helix sandbox create --runtime headless-ubuntu --size medium --ttl 1800 --name scratch
# also the cheapest end-to-end proof that the Hydra container runner is healthy
# small=1CPU/2GB, medium=4CPU/8GB, large=8CPU/16GB; --ttl seconds (default 600)
# --persistent mounts a workspace volume that survives restarts
# --project prj_01xxx associates it with a project

helix sandbox list --org acme
helix sandbox wait sbx_01xxx --timeout 3m
helix sandbox exec sbx_01xxx -- bash -lc "uname -a"
helix sandbox exec sbx_01xxx --detached -- ./long-job.sh     # prints a command id
helix sandbox logs sbx_01xxx cmd_01xxx --follow
helix sandbox commands sbx_01xxx
helix sandbox kill sbx_01xxx cmd_01xxx --signal TERM

helix sandbox ls sbx_01xxx --path /root
helix sandbox read sbx_01xxx /root/out.txt
echo "hello" | helix sandbox write sbx_01xxx /root/in.txt --mode 644
helix sandbox screenshot sbx_01xxx -o shot.jpg          # desktop runtimes only
helix sandbox terminal sbx_01xxx                        # interactive; avoid in scripts

helix sandbox delete sbx_01xxx
```

Sandboxes expire at their TTL. Set one long enough for the job, and delete explicitly when done
rather than relying on expiry.

**`--org` is per-command, not sticky.** If you create a sandbox in one org and then omit `--org`
on `exec`/`delete`, the CLI resolves your *first* org and the API answers `404 sandbox not found`
— which reads like the sandbox died, but is really "wrong org". Export `HELIX_ORG`, or pass
`--org` to every sandbox subcommand in a script.

The runtime list is deployment config (`HELIX_SANDBOX_RUNTIMES` on the API), not a fixed set —
`helix sandbox runtimes` is the only reliable answer for a given deployment, and it lists the
desktop runtime alongside the headless ones (`ubuntu-desktop`, `headless-ubuntu`, `node22`,
`python313` on a default install).

A runtime appearing there does **not** guarantee the node can start it: the catalogue is
control-plane config, while the images a sandbox node has pulled are independent of it. See the
"node online but create fails" case in [helix-deploy](../../helix-deploy/SKILL.md). `--image` needs
`HELIX_SANDBOX_ALLOW_CUSTOM_IMAGE=true` on the server and is rejected otherwise.

Each sandbox runs under its own Docker daemon inside the Hydra runner, so containers you start
inside one are invisible to every other session. See
[helix-deploy](../../helix-deploy/SKILL.md) for what that means operationally.

