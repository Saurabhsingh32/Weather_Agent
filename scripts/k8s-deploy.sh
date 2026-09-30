#!/usr/bin/env bash
# Build the notes API image, push to ttl.sh (ephemeral registry), deploy 3 replicas.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="${IMAGE_TAG:-2h}"
IMAGE="ttl.sh/agentic-web-app-${USER}:${TAG}"

echo "Building agentic-web-app:latest ..."
docker build -t agentic-web-app:latest .

echo "Pushing ${IMAGE} ..."
docker tag agentic-web-app:latest "${IMAGE}"
docker push "${IMAGE}"

# Point the Deployment at the pushed image (Docker Desktop often cannot use local-only images).
tmp="$(mktemp)"
sed "s|image: .*agentic-web-app.*|image: ${IMAGE}|" k8s/10-deployment.yaml >"${tmp}"
cp "${tmp}" k8s/10-deployment.yaml
rm -f "${tmp}"

kubectl apply -f k8s/
kubectl -n agentic-web-app rollout status deployment/notes-api --timeout=180s
kubectl -n agentic-web-app get pods,svc
echo
echo "Try: curl http://127.0.0.1:8000/health"
echo "Docs: http://127.0.0.1:8000/docs"
