# Models and provider endpoints

```bash
helix model list                              # --runtime vllm --type chat --enabled true
helix model list -q                           # ids only
helix model inspect llama3.1:8b --format json
helix model apply -f model.yaml
helix model delete my-model --force
```

```yaml
# model.yaml
apiVersion: model.aispec.org/v1alpha1
kind: Model
metadata:
  name: llama3.1:8b
spec:
  id: llama3.1:8b
  name: Llama 3.1 8B
  type: chat            # chat | image | embed
  runtime: ollama       # ollama | vllm | diffusers
  memory: "8GB"
  context_length: 8192
  enabled: true
```

You only declare total memory — Helix picks the GPUs, sets tensor-parallel size for vLLM, and
computes memory ratios itself.

To attach a hosted or self-hosted OpenAI-compatible endpoint instead of running models locally:

```bash
helix provider create -n my-vllm -u https://vllm.internal/v1 -f ./key.txt -m qwen3-32b
helix provider list
```

Secrets referenced as `${VAR}` in agent YAML come from `helix secret` — see
[helix-cli](../../helix-cli/SKILL.md).

