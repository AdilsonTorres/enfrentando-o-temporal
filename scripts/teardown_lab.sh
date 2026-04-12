#!/usr/bin/env bash
# =============================================================================
# teardown_lab.sh — Encerra o ambiente de lab limpo
#
# Para todos os workers, destrói o containerlab e para a infra Temporal.
#
# Uso:
#   bash scripts/teardown_lab.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_DIR/infra"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[teardown]${NC} $*"; }
warn() { echo -e "${YELLOW}[teardown]${NC} $*"; }

# ─── Para workers Python em background ───────────────────────────────────────
log "Encerrando workers Python (worker.py)..."
pkill -f "worker.py" 2>/dev/null && log "Workers encerrados." || warn "Nenhum worker rodando."

# ─── Destrói ContainerLab ────────────────────────────────────────────────────
log "Destruindo ContainerLab..."
if [ -d "$INFRA_DIR/containerlab" ]; then
    cd "$INFRA_DIR/containerlab"
    sudo containerlab destroy -t lab.yml --cleanup 2>/dev/null && log "ContainerLab destruído." \
        || warn "ContainerLab não estava rodando."
fi

# ─── Para infra Temporal ─────────────────────────────────────────────────────
log "Parando infra Temporal (docker compose down)..."
cd "$INFRA_DIR"
docker compose down

log ""
log "Ambiente encerrado com sucesso."
