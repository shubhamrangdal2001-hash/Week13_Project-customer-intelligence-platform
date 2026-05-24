#!/usr/bin/env bash
# =============================================================================
# azure_deploy.sh – Deploy Week 13 services to Azure App Service
# =============================================================================
# Prerequisites:
#   • Azure CLI installed and logged in  (az login)
#   • Docker Desktop running
#   • Run from the repo root:  bash infra/azure_deploy.sh
# =============================================================================

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
RESOURCE_GROUP="${RESOURCE_GROUP:-weel13-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-weel13acr}"          # must be globally unique in Azure
APP_PLAN="${APP_PLAN:-weel13-plan}"
APP_NAME="${APP_NAME:-weel13-app}"
APP_PLAN_SKU="${APP_PLAN_SKU:-S1}"          # S1 = 1 vCPU, 1.75 GB RAM

# Image tags
CONVERSION_IMAGE="weel13-conversion:latest"
RAG_IMAGE="weel13-rag:latest"

# ─── Helper ──────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERR ]\033[0m  $*" >&2; exit 1; }

# ─── 1. Build Docker images ───────────────────────────────────────────────────
info "Building conversion service image…"
docker build -f docker/Dockerfile.conversion -t "$CONVERSION_IMAGE" .

info "Building RAG service image…"
docker build -f docker/Dockerfile.rag -t "$RAG_IMAGE" .

# ─── 2. Create Azure resource group ──────────────────────────────────────────
info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'…"
az group create \
  --name  "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ─── 3. Create Azure Container Registry ──────────────────────────────────────
info "Creating ACR '$ACR_NAME'…"
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_LOGIN_SERVER=$(az acr show \
  --name "$ACR_NAME" \
  --query loginServer \
  --output tsv)

ACR_PASSWORD=$(az acr credential show \
  --name "$ACR_NAME" \
  --query "passwords[0].value" \
  --output tsv)

# ─── 4. Push images to ACR ───────────────────────────────────────────────────
info "Logging into ACR…"
docker login "$ACR_LOGIN_SERVER" \
  --username "$ACR_NAME" \
  --password "$ACR_PASSWORD"

info "Pushing conversion image…"
docker tag "$CONVERSION_IMAGE" "$ACR_LOGIN_SERVER/$CONVERSION_IMAGE"
docker push "$ACR_LOGIN_SERVER/$CONVERSION_IMAGE"

info "Pushing RAG image…"
docker tag "$RAG_IMAGE" "$ACR_LOGIN_SERVER/$RAG_IMAGE"
docker push "$ACR_LOGIN_SERVER/$RAG_IMAGE"

# ─── 5. Create App Service Plan (Linux) ──────────────────────────────────────
info "Creating App Service plan '$APP_PLAN' (SKU=$APP_PLAN_SKU)…"
az appservice plan create \
  --name "$APP_PLAN" \
  --resource-group "$RESOURCE_GROUP" \
  --is-linux \
  --sku "$APP_PLAN_SKU" \
  --output none

# ─── 6. Generate docker-compose config for Azure multi-container App Service ─
COMPOSE_YAML=$(cat <<EOF
version: "3.8"
services:
  conversion:
    image: ${ACR_LOGIN_SERVER}/${CONVERSION_IMAGE}
    ports:
      - "8000:8000"
    environment:
      - SERVICE_NAME=conversion-service
      - APPLICATIONINSIGHTS_CONNECTION_STRING=\${APPLICATIONINSIGHTS_CONNECTION_STRING}

  rag:
    image: ${ACR_LOGIN_SERVER}/${RAG_IMAGE}
    ports:
      - "8001:8001"
    environment:
      - SERVICE_NAME=rag-service
      - LLM_MODEL_NAME=/app/rag/llm
      - APPLICATIONINSIGHTS_CONNECTION_STRING=\${APPLICATIONINSIGHTS_CONNECTION_STRING}
EOF
)

COMPOSE_FILE_PATH="/tmp/weel13_azure_compose.yml"
echo "$COMPOSE_YAML" > "$COMPOSE_FILE_PATH"

# ─── 7. Create the multi-container Web App ────────────────────────────────────
info "Creating Web App '$APP_NAME'…"
az webapp create \
  --resource-group "$RESOURCE_GROUP" \
  --plan "$APP_PLAN" \
  --name "$APP_NAME" \
  --multicontainer-config-type COMPOSE \
  --multicontainer-config-file "$COMPOSE_FILE_PATH" \
  --output none

# ─── 8. Configure ACR credentials in the Web App ─────────────────────────────
info "Setting ACR credentials on Web App…"
az webapp config container set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
  --docker-registry-server-user "$ACR_NAME" \
  --docker-registry-server-password "$ACR_PASSWORD" \
  --output none

# ─── 9. Stream public URL ─────────────────────────────────────────────────────
APP_URL=$(az webapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query defaultHostName \
  --output tsv)

info "Deployment complete!"
echo ""
echo "  Conversion endpoint : https://${APP_URL}:8000/predict"
echo "  RAG endpoint        : https://${APP_URL}:8001/answer"
echo "  Swagger (conversion): https://${APP_URL}:8000/docs"
echo "  Swagger (RAG)       : https://${APP_URL}:8001/docs"
echo ""
echo "Set the following environment variable for Azure Monitor telemetry:"
echo "  APPLICATIONINSIGHTS_CONNECTION_STRING=<your-connection-string>"
