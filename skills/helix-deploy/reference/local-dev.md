# Local development stack

```bash
cp .env.example-prod .env
./stack start                     # docker-compose.dev.yaml
docker compose -f docker-compose.dev.yaml ps
```

Ready means `helix-api-1`, `helix-frontend-1` and `helix-postgres-1` all `Up` and
`curl -s -o /dev/null -w '%{http_code}' http://localhost:8080` returning `200`. **Cold bring-up
takes 5–10 minutes** — connection-refused or `Restarting` early on means "still coming up". Poll;
don't conclude failure.

The dev stack's sandbox is a compose profile, unlike production:

```bash
COMPOSE_PROFILES=code-nvidia ./stack start     # or code-amd-intel / code-software / code-macos
```

```bash
./stack stop                      # STOP_POSTGRES=1 / STOP_PGVECTOR=1 for data services too
./stack up <service>
./stack rebuild <service>
./stack lint
./stack test [./path/...]
./stack psql
./stack update_openapi
./stack build-sandbox             # Hydra + DinD image
./stack build-ubuntu              # desktop image (GNOME + Zed + streaming)
./stack build-zed release         # must be `release` on ARM
./stack help
```

Hot reload: the API rebuilds on save via `air`; the frontend is Vite HMR on 8081 behind 8080.
**Hydra does not hot reload** — Air doesn't rebuild the binary that lives inside the sandbox
container:

```bash
cd api && CGO_ENABLED=0 GOOS=linux go build -o /tmp/hydra-linux ./cmd/hydra
docker cp /tmp/hydra-linux helix-sandbox-nvidia-1:/usr/local/bin/hydra
docker compose -f docker-compose.dev.yaml exec -T sandbox-nvidia pkill -TERM hydra
docker logs helix-sandbox-nvidia-1 | grep "RevDial control connection established"
```

Desktop images and the settings-sync-daemon need `./stack build-ubuntu` plus a **new** session.

Avoid `./stack start-tmux` non-interactively, and never `docker builder prune` /
`docker system prune` on a Helix dev machine — delete old image tags instead if disk is full.

