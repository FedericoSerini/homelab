# bottega-knowledge — remaining setup

Manifests scaffolded by Claude on 2026-06-25 while the cluster was offline and
no `gh`/`docker`/SOPS-age credentials were available in that session. The
deployment is **not wired into Flux yet** (see commented-out resources in
`kustomization.yaml`). Steps left, in order:

## 1. Build & push the image

Source: `bottega-v2/container/Dockerfile` + `.github/workflows/docker-build-push.yaml`
(builds `ghcr.io/federicoserini/bottega-knowledge`).

Either push `bottega-v2` to a GitHub repo (workflow runs on push to `main`), or
build/push manually:
```
cd bottega-v2
docker login ghcr.io
docker build -f container/Dockerfile -t ghcr.io/federicoserini/bottega-knowledge:latest .
docker push ghcr.io/federicoserini/bottega-knowledge:latest
```

## 2. Cloudflare tunnel

```
cloudflared tunnel create bottega-knowledge
cloudflared tunnel route dns bottega-knowledge bottega-knowledge.federicoserini.com
# credentials land at ~/.cloudflared/<tunnel-id>.json
```

Then, from the homelab repo root:
```
kubectl create secret generic tunnel-credentials \
  --from-file=credentials.json=~/.cloudflared/<tunnel-id>.json \
  --dry-run=client -o yaml > secret.yaml
sops --age=$AGE_PUBLIC --encrypt --encrypted-regex '^(data|stringData)$' \
  --config clusters/staging/.sops.yaml --in-place secret.yaml
mv secret.yaml apps/staging/bottega-knowledge/tunnel-credentials.yaml
```

## 3. Auth token secret

This service sits behind a **public** tunnel — it requires
`BOTTEGA_KNOWLEDGE_TOKEN` or every request is unauthenticated. Generate one:
```
TOKEN=$(openssl rand -hex 32)
kubectl create secret generic bottega-knowledge-secret \
  --from-literal=BOTTEGA_KNOWLEDGE_TOKEN=$TOKEN \
  --dry-run=client -o yaml > secret.yaml
sops --age=$AGE_PUBLIC --encrypt --encrypted-regex '^(data|stringData)$' \
  --config clusters/staging/.sops.yaml --in-place secret.yaml
mv secret.yaml apps/staging/bottega-knowledge/bottega-knowledge-secret.yaml
```
Save `$TOKEN` somewhere — the Mac-side `bottega` CLI needs it too, as
`BOTTEGA_KNOWLEDGE_TOKEN` in its own environment (it's sent as a Bearer token
by `knowledge/client.py`).

## 4. ghcr pull secret (if the image stays private)

Same pattern as `apps/staging/mobile-db/ghcr-login-secret.yaml` — copy that
file's approach (a `kubernetes.io/dockerconfigjson` secret, SOPS-encrypted).

## 5. Wire into kustomization + INFRA.md

Once 1-4 exist, uncomment the three resources in `kustomization.yaml`, then
update `.claude/INFRA.md`'s `APPS:` section:
```
bottega-knowledge ns:bottega-knowledge img:ghcr.io/federicoserini/bottega-knowledge:latest port:8000 db:LanceDB+NetworkX(PVC) host:bottega-knowledge.federicoserini.com secret:bottega-knowledge-secret(BOTTEGA_KNOWLEDGE_TOKEN)
```

## 6. Commit & push

```
git add apps/base/bottega-knowledge apps/staging/bottega-knowledge .claude/INFRA.md
git commit
git push origin main
flux get kustomizations --watch
kubectl -n bottega-knowledge get pods --watch
```

Then on the Mac side, point `bottega` at it:
```
export BOTTEGA_KNOWLEDGE_TOKEN=<the token from step 3>
bottega <project_root> <staging_path> https://bottega-knowledge.federicoserini.com
```
