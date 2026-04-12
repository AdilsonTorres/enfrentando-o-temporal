#!/usr/bin/env bash
# =============================================================================
# run_exercises.sh — Executa todos os exercícios para popular o Temporal
#
# Inicia um worker por exercício, executa o workflow correspondente,
# aguarda o resultado e encerra o worker. Ao final, o Temporal UI terá
# histórico de todos os tipos de workflow para visualização na apresentação.
#
# Pré-requisito:
#   - Lab rodando (bash scripts/setup_lab.sh)
#   - Venv ativada (source .venv/bin/activate)
#
# Uso:
#   cd /home/adilson/semanacap/enfrentando-o-temporal
#   source .venv/bin/activate
#   bash scripts/run_exercises.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()     { echo -e "${GREEN}[exercises]${NC} $*"; }
section() { echo -e "\n${CYAN}══════════════════════════════════════════${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}══════════════════════════════════════════${NC}"; }
warn()    { echo -e "${YELLOW}[exercises]${NC} $*"; }

WORKER_PID=""

start_worker() {
    local dir="$1"
    log "Iniciando worker em $dir..."
    cd "$PROJECT_DIR/$dir"
    python worker.py &
    WORKER_PID=$!
    sleep 3  # aguarda worker registrar no Temporal
}

stop_worker() {
    if [ -n "$WORKER_PID" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        kill "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
        WORKER_PID=""
    fi
}

# Garante que workers são encerrados ao sair
trap stop_worker EXIT


# ═══════════════════════════════════════════════════════════════════════════
section "Ex01 — Workflow Básico"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "exercicio_01_basico"

log "Executando para Arista (router-01)..."
cd "$PROJECT_DIR/exercicio_01_basico"
python run.py

log "Executando para Nokia (srl-01)..."
python run.py --nokia

stop_worker
log "Ex01 concluído."


# ═══════════════════════════════════════════════════════════════════════════
section "Ex02 — SAGA (sucesso + rollback)"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "exercicio_02_saga"

log "SAGA — caminho de sucesso (router-01)..."
cd "$PROJECT_DIR/exercicio_02_saga"
python run.py

log "SAGA — caminho de rollback (--force-fail)..."
python run.py --force-fail || true  # rollback retorna código não-zero

log "SAGA — Nokia sucesso (srl-01)..."
python run.py --nokia

stop_worker
log "Ex02 concluído."

# Restaura hostnames após ex02
log "Restaurando hostnames após ex02..."
cd "$PROJECT_DIR"
bash scripts/reset_devices.sh 2>/dev/null || true


# ═══════════════════════════════════════════════════════════════════════════
section "Ex03 — Human-in-the-Loop (aprovação + rejeição)"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "exercicio_03_human_loop"
cd "$PROJECT_DIR/exercicio_03_human_loop"

# Workflow de aprovação
WF_APPROVE="ex03-approve-demo"
log "Iniciando workflow aguardando aprovação (id=$WF_APPROVE)..."
python run.py &
RUN_PID=$!
sleep 4

# Captura o ID do workflow mais recente
WF_ID=$(python - <<'PYEOF'
import asyncio
from temporalio.client import Client
async def main():
    client = await Client.connect("localhost:7233")
    async for wf in client.list_workflows('WorkflowType="InterfaceChangeApprovalWorkflow"'):
        print(wf.id)
        break
asyncio.run(main())
PYEOF
)

if [ -n "$WF_ID" ]; then
    log "Aprovando workflow '$WF_ID'..."
    python run.py --approve "$WF_ID"
fi
wait "$RUN_PID" 2>/dev/null || true

# Workflow de rejeição
log "Iniciando workflow que será rejeitado..."
python run.py &
RUN_PID=$!
sleep 4

WF_ID=$(python - <<'PYEOF'
import asyncio
from temporalio.client import Client
async def main():
    client = await Client.connect("localhost:7233")
    async for wf in client.list_workflows('WorkflowType="InterfaceChangeApprovalWorkflow"'):
        print(wf.id)
        break
asyncio.run(main())
PYEOF
)

if [ -n "$WF_ID" ]; then
    log "Rejeitando workflow '$WF_ID'..."
    python run.py --reject "$WF_ID" "Fora da janela de manutenção"
fi
wait "$RUN_PID" 2>/dev/null || true

stop_worker
log "Ex03 concluído."


# ═══════════════════════════════════════════════════════════════════════════
section "Ex04 — Schedules (compliance)"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "exercicio_04_schedules"
cd "$PROJECT_DIR/exercicio_04_schedules"

# Remove schedules anteriores se existirem
python run.py --delete compliance-router-01 2>/dev/null || true
python run.py --delete compliance-srl-01 2>/dev/null || true

log "Criando schedule para Arista..."
python run.py --create

log "Criando schedule para Nokia..."
python run.py --create --nokia

log "Forçando execução imediata dos schedules..."
python run.py --trigger compliance-router-01
sleep 5
python run.py --trigger compliance-srl-01
sleep 5

log "Listando schedules ativos:"
python run.py --list

stop_worker
log "Ex04 concluído."


# ═══════════════════════════════════════════════════════════════════════════
section "Ex05 — SAGA + Human-in-the-Loop"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "exercicio_05_interface_ops"
cd "$PROJECT_DIR/exercicio_05_interface_ops"

log "Iniciando workflow de interface (admin-down)..."
python run.py &
RUN_PID=$!
sleep 4

WF_ID=$(python - <<'PYEOF'
import asyncio
from temporalio.client import Client
async def main():
    client = await Client.connect("localhost:7233")
    async for wf in client.list_workflows('WorkflowType="InterfaceAdminStateWorkflow"'):
        print(wf.id)
        break
asyncio.run(main())
PYEOF
)

if [ -n "$WF_ID" ]; then
    log "Aprovando workflow '$WF_ID'..."
    sleep 2
    python run.py --approve "$WF_ID"
fi
wait "$RUN_PID" 2>/dev/null || true

# Restaura interface
log "Restaurando interface (admin-up)..."
python run.py --up &
RUN_PID=$!
sleep 4

WF_ID=$(python - <<'PYEOF'
import asyncio
from temporalio.client import Client
async def main():
    client = await Client.connect("localhost:7233")
    async for wf in client.list_workflows('WorkflowType="InterfaceAdminStateWorkflow"'):
        print(wf.id)
        break
asyncio.run(main())
PYEOF
)

if [ -n "$WF_ID" ]; then
    python run.py --approve "$WF_ID"
fi
wait "$RUN_PID" 2>/dev/null || true

stop_worker
log "Ex05 concluído."


# ═══════════════════════════════════════════════════════════════════════════
section "Bônus — Execução Paralela"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "bonus/paralelo"
cd "$PROJECT_DIR/bonus/paralelo"
log "Aplicando banner em paralelo em router-01 e router-02..."
python run.py
stop_worker
log "Bônus paralelo concluído."


# ═══════════════════════════════════════════════════════════════════════════
section "Bônus — Continue-as-New (monitoramento)"
# ═══════════════════════════════════════════════════════════════════════════

start_worker "bonus/continue_as_new"
cd "$PROJECT_DIR/bonus/continue_as_new"
log "Iniciando monitoramento contínuo (fica rodando em background)..."
python run.py &
MONITOR_PID=$!
sleep 5
# Deixa rodando — o worker será encerrado pelo trap EXIT


# ═══════════════════════════════════════════════════════════════════════════
section "Resumo"
# ═══════════════════════════════════════════════════════════════════════════

log ""
log "Todos os exercícios executados com sucesso!"
log ""
log "Workflows disponíveis no Temporal UI:"
log "  http://localhost:8080/namespaces/default/workflows"
log ""
log "Próximo passo:"
log "  bash scripts/generate_screenshots.sh"
