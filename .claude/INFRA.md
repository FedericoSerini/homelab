# HOMELAB — Federico Serini
CLUSTER: Talos v1.13.3 / k8s v1.36.1 / containerd 2.2.4
  maestrale:      control-plane, Ready

GITOPS: FluxCD / branch=main ONLY / SOPS+Age (secret:sops-age)
  kustomizations: apps(15m) databases(15m) infr-controllers(1h) monitoring(1h)
  TRAP: Flux tracks main only → kubectl patch is fast path for hotfixes

STORAGE: synology-iscsi-storage (default) / NAS:192.168.1.52 / iSCSI/ext4/Retain

APPS:
  bookstack  ns:bookstack  img:linuxserver/bookstack:26.03  port:80   db:MariaDB  host:bookstack.federicoserini.com
  linkding   ns:linkding   img:sissbruecker/linkding:1.45.0 port:9090 db:CNPG     host:linkding.federicoserini.com
  mealie     ns:mealie     img:ghcr.io/mealie-recipes/mealie:v3.19.1 port:9000 db:CNPG host:mealie.federicoserini.com
  phos       ns:phos       img:ghcr.io (private, secret:ghcr-login-secret)
  mobile-db  ns:mobile-db  img:ghcr.io/federicoserini/mobile-db:latest port:8443 db:SQLite/crsqlite(PVC) host:mobile-db.federicoserini.com secret:mobile-db-secret
  keycloak   ns:keycloak   chart:keycloakx@7.2.0(codecentric) port:80 db:CNPG   host:gatekeeper.federicoserini.com
  moneybud   ns:moneybud   img:ghcr.io/federicoserini/moneybud:latest port:3001 db:none(PVC-stub) host:moneybud.federicoserini.com secret:moneybud-secret(MOBILE_DB_URL) VITE_KEYCLOAK_URL baked at build

INFRA CONTROLLERS (HelmReleases in ns matching name):
  ✅ cloudnative-pg-operator@0.23.1   ✅ external-dns@1.15.0
  ✅ mariadb-operator@0.28.1          ✅ mongodb-operator@0.13.0
  ✅ falco@4.20.1                     ✅ keycloakx@7.2.0
  ✅ kube-prometheus-stack@68.5.0 

DATABASES (all in same ns as app):
  CNPG PostgreSQL 17.4 (1 instance, synology-iscsi-storage):
    pg-keycloak (ns:keycloak-pg)  pg-linkding (ns:linkding-pg)  pg-mealie (ns:mealie-pg)
  MariaDB (mariadb-operator): bookstack / port:3306 / external-dns:mariadb.federicoserini.com

INGRESS: Cloudflare Tunnels / one cloudflared Deployment per namespace
  secret:tunnel-credentials / creds:/etc/cloudflared/creds/credentials.json
  service pattern: http://<app-svc>:<port>

SECRETS: all SOPS+Age encrypted / NEVER decode in terminal
  keycloak-secret keys: keycloak-db-host keycloak-db-port keycloak-db-user keycloak-db-name KEYCLOAK_ADMIN_USER KEYCLOAK_ADMIN_PASSWORD
  ConfigMaps: kustomize hash-named (e.g. keycloak-values-{hash}) — patch ConfigMap + delete pod required (StatefulSet won't self-update)

REPO LAYOUT:
  apps/{base,staging}/<app>/          ← Deployments, Services, Cloudflare, Secrets
  databases/data/<app>/               ← CNPG Cluster / MariaDB CRDs
  infrastructure/controllers/{base,staging}/<ctrl>/ ← HelmReleases (valuesFrom ConfigMap)
  monitoring/controllers/{base,staging}/
  clusters/staging/                   ← Flux entrypoints (apps/databases/infrastructure/monitoring)

WORKFLOWS:
  New Cloudflare tunnel:
    cloudflared tunnel create <name>
    cloudflared tunnel route dns <name> <hostname>
    credentials → ~/.cloudflared/<tunnel-id>.json

  New SOPS secret (from secrets/ folder pattern):
    kubectl create secret generic <name> --from-literal=KEY=VAL ... --dry-run=client -o yaml > secret.yaml
    sops --age=$AGE_PUBLIC --encrypt --encrypted-regex '^(data|stringData)$' \
      --config clusters/staging/.sops.yaml --in-place secret.yaml
    mv secret.yaml apps/staging/<app>/secret.yaml

  New tunnel-credentials secret:
    kubectl create secret generic tunnel-credentials \
      --from-file=credentials.json=~/.cloudflared/<id>.json --dry-run=client -o yaml > secret.yaml
    (then same sops encrypt + move)

KNOWN TRAPS:
  keycloakx: use args:["start"] NOT command:[] / KC_HOSTNAME required in production mode
  ConfigMap patch → pod won't restart → must delete pod manually
  HelmRelease stalled → annotate reconcile.fluxcd.io/requestedAt / flux reconcile alone insufficient
  Bitnami images: Docker Hub auth-gated since Nov 2023 — avoid
  HelmRelease valuesFrom uses kustomize hash-named ConfigMap → patch existing CM, then delete pod
  Synology CSI on Talos: iscsiadm lives at /usr/local/sbin (musl libs, not in CSI container) → node DaemonSet uses initContainer+nsenter wrapper; btrfs kernel module absent from Talos 6.18.33-talos → use ext4
  StatefulSet RollingUpdate stuck on CrashLoop → delete pod manually to force new revision
  Dead node pods: stuck Terminating forever → kubectl delete pod --force --grace-period=0 + kubectl delete node
