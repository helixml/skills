# Kubernetes

## Contents
- Prerequisites and resource requirements
- Control plane chart
- External Postgres
- Sandbox chart
- Chart specifics that bite

Two published charts. Do **not** install from a git clone — `Chart.yaml` is generated at release
time and a clone produces a sentinel version.

Prerequisites the section used to assume: **helm** and a **cluster**. `kind` stands one up in
about 20 seconds and is enough for the whole control plane; `scripts/kind_helm_install.sh` in
the helix repo automates the lot. **`jq`** is used by most one-liners here.

**Resource requirements.** A measured install of the full five-pod control plane on a cold host:
ready **2m11s** after `helm install`, then idling at **~1.8 GiB RAM, under 5% of 4 CPUs, ~5 GiB
disk**. It fits comfortably on a small VM — much smaller than the component list suggests.

```bash
helm repo add helix https://charts.helixml.tech
helm repo update

curl -o values.yaml \
  https://raw.githubusercontent.com/helixml/helix/main/charts/helix-controlplane/values-example.yaml
# set global.serverUrl, ingress, storageClass, postgresql
# AND replace controlplane.runnerToken — see the warning below

helm upgrade --install helix helix/helix-controlplane -f values.yaml \
  --set image.tag=$(curl -s https://get.helixml.tech/latest.txt)

kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=helix-controlplane --timeout=300s
```

> **Replace the runner token before you deploy.** `values-example.yaml` ships
> `controlplane.runnerToken: "your-secure-runner-token-here"`, and applying it verbatim gives you
> a cluster whose runner/sandbox join secret is a publicly known string. This is the Helm
> equivalent of `oh-hallo-insecure-token`, and it is easy to miss because the file's own comment
> reads like a placeholder you might get away with. Generate one:
> `--set controlplane.runnerToken="$(openssl rand -hex 32)"`, or better, point
> `controlplane.runnerTokenExistingSecret` at a Kubernetes secret. Verify afterwards with
> `kubectl exec deploy/<release>-helix-controlplane -- printenv RUNNER_TOKEN`.

That label selector covers the whole stack, and 300s is enough in practice — a measured cold
install had all five pods ready in 2m11s.

External Postgres:

```bash
helm upgrade --install helix helix/helix-controlplane -f values.yaml \
  --set postgresql.enabled=false \
  --set postgresql.external.existingSecret=my-pg-secret \
  --set postgresql.external.existingSecretHostKey=host \
  --set postgresql.external.existingSecretPortKey=port \
  --set postgresql.external.existingSecretUserKey=user \
  --set postgresql.external.existingSecretDatabaseKey=dbname \
  --set postgresql.external.existingSecretPasswordKey=password
```

Sandbox chart — this is the Hydra node on Kubernetes:

```bash
# the token secret's key must be literally "token"
kubectl create secret generic helix-runner-token --from-literal=token="$RUNNER_TOKEN"

helm upgrade --install helix-sandbox helix/helix-sandbox \
  --set sandbox.apiUrl=http://helix-helix-controlplane:80 \
  --set sandbox.runnerTokenExistingSecret=helix-runner-token \
  --set sandbox.maxSandboxes=10 \
  --set gpu.vendor=none \
  --set hydra.enabled=true
```

Three things in that command are easy to get wrong:

- **`gpu.vendor` defaults to `nvidia`.** Leaving it on a cluster without GPUs parks the pod in
  `Pending` forever with `0/1 nodes are available: 1 Insufficient nvidia.com/gpu`. Set it to
  match the hardware; `none` is right for a CPU-only cluster.
- **`sandbox.apiUrl` must name the real service.** `helm install helix helix/helix-controlplane`
  creates `helix-helix-controlplane`, not `helix-controlplane` — the release name is prefixed.
  Check with `kubectl get svc`.
- **`runnerTokenExistingSecretKey` defaults to `token`**, so the secret must have a key of that
  name.

The node also needs `/run/udev` to exist on the host, or the pod never starts:
`MountVolume.SetUp failed for volume "udev": hostPath type check failed: /run/udev is not a directory`.

Chart specifics that bite:

- `securityContext.privileged: true` is required (DinD). On OpenShift you also need the
  privileged SCC — see the `openshift:` block in `values.yaml`.
- Three PVCs are provisioned: `dockerStorage` → `/var/lib/docker` (50Gi), `hydraData` →
  `/hydra-data` (20Gi), `workspaceData` → `/data` (100Gi). `hydraData` **must** be a real volume;
  overlay-on-overlay breaks nested dockerd.
- Disk-pressure admission only watches the first two by default. To cover `/data` too:
  ```yaml
  sandbox:
    extraEnv:
      - name: HELIX_DISK_PRESSURE_PATHS
        value: "/var/lib/docker,/hydra-data,/data"
  ```
- Default probes `exec` into the nested dockerd. On AKS with cgroup v2 they fail spuriously —
  disable them (`--set probes.liveness.enabled=false`) or override via a **values file**. Using
  `--set` to add an `httpGet` merges rather than replaces and yields an invalid spec.
- `hydra.privilegedMode: true` disables tenant isolation. Dev only.
- Per-cloud starting points ship as `charts/helix-sandbox/values-{gke,eks,aks,bare-metal}.yaml`.

`scripts/kind_helm_install.sh` stands the whole thing up on kind — the cheapest rehearsal.
`USE_LOCAL_HELM_CHART=1`, `USE_EXTERNAL_POSTGRES=1` and `INSTALL_SANDBOX=1` toggle the variants.
Read `charts/helix-controlplane/UPGRADE.md` before bumping a chart version.

