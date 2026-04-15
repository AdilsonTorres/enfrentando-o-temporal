#!/usr/bin/env bash
# =============================================================================
# setup_lab.sh — Prepara o ambiente completo para a apresentação
#
# Executa na ordem:
#   1. Sobe a infra Temporal (docker compose)
#   2. Deploy do lab containerlab
#   3. Popula os dispositivos com configurações realistas
#
# Uso:
#   cd /home/adilson/semanacap/enfrentando-o-temporal
#   source .venv/bin/activate
#   bash scripts/setup_lab.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_DIR/infra"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[setup]${NC} $*"; }
err()  { echo -e "${RED}[setup]${NC} $*" >&2; }

# ─── Passo 1: Infra Temporal ──────────────────────────────────────────────────
log "Iniciando infra Temporal (PostgreSQL + Temporal Server + UI)..."
cd "$INFRA_DIR"
docker compose up -d

log "Aguardando Temporal estar saudável (até 60s)..."
for i in $(seq 1 30); do
    if docker compose exec -T temporal tctl --namespace default workflow list >/dev/null 2>&1; then
        log "Temporal OK após ${i}s."
        break
    fi
    sleep 2
    if [ "$i" -eq 30 ]; then
        warn "Temporal pode ainda estar inicializando — continuando mesmo assim."
    fi
done

# ─── Passo 2: ContainerLab ────────────────────────────────────────────────────
log "Fazendo deploy do ContainerLab (router-01, srl-01)..."
cd "$INFRA_DIR/containerlab"

if sudo containerlab inspect -t lab.yml 2>/dev/null | grep -q "router-01"; then
    warn "Lab já está rodando. Pulando deploy."
else
    sudo containerlab deploy -t lab.yml
    log "ContainerLab deployado."
fi

# ─── Passo 3: Aguardar dispositivos ──────────────────────────────────────────
log "Aguardando dispositivos ficarem acessíveis (até 60s)..."
cd "$PROJECT_DIR"
for i in $(seq 1 20); do
    if python -c "
import socket, sys
try:
    s = socket.create_connection(('192.168.100.101', 22), timeout=3)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        log "router-01 acessível após ${i}×3s."
        break
    fi
    sleep 3
    if [ "$i" -eq 20 ]; then
        warn "Dispositivos podem ainda estar inicializando. Verifique o containerlab."
    fi
done

# ─── Passo 4: Populate devices ────────────────────────────────────────────────
log "Populando dispositivos com configurações realistas..."
cd "$PROJECT_DIR"
python infra/scripts/populate_devices.py

log ""
log "=============================================="
log "  Lab pronto para a apresentação!"
log "=============================================="
log ""
log "  Temporal UI : http://localhost:8080"
log "  Dispositivos:"
log "    router-01  192.168.100.101  (Arista cEOS)"
log "    srl-01     192.168.100.103  (Nokia SR Linux)"
log ""
log "  Próximos passos:"
log "    bash scripts/run_exercises.sh      # executa todos os exercícios"
