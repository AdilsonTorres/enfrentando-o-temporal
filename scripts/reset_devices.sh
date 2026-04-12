#!/usr/bin/env bash
# =============================================================================
# reset_devices.sh — Restaura os dispositivos ao estado inicial
#
# Útil para:
#   - Resetar após um exercício que mudou o hostname
#   - Preparar o lab para uma nova execução da apresentação
#   - Corrigir estado inconsistente após falha de rollback
#
# Hostnames restaurados:
#   router-01  192.168.100.101
#   srl-01     192.168.100.103
#
# Uso:
#   cd /home/adilson/semanacap/enfrentando-o-temporal
#   source .venv/bin/activate
#   bash scripts/reset_devices.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[reset]${NC} $*"; }

cd "$PROJECT_DIR"

log "Restaurando hostnames padrão..."

python - <<'PYEOF'
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv(".env")

sys.path.insert(0, ".")
from shared.device_drivers import connect

DEVICES = {
    "router-01": {"ip": os.getenv("DEVICE_01", "192.168.100.101"), "type": "eos", "hostname": "router-01"},
    "srl-01":    {"ip": os.getenv("DEVICE_03", "192.168.100.103"), "type": "srl", "hostname": "srl-01"},
}


async def reset(name, cfg):
    target = cfg["hostname"]
    try:
        device = connect(cfg["ip"], cfg["type"])
        current = await device.get_hostname()
        if current == target:
            print(f"  ✓ {name} ({cfg['ip']}): hostname já é '{target}' — sem alteração")
            return
        await device.set_hostname(target)
        print(f"  → {name} ({cfg['ip']}): '{current}' → '{target}'")
    except Exception as e:
        print(f"  ✗ {name} ({cfg['ip']}): ERRO — {e}")


async def main():
    print("\nVerificando e restaurando hostnames:")
    await asyncio.gather(*[reset(n, c) for n, c in DEVICES.items()])
    print()


asyncio.run(main())
PYEOF

log "Dispositivos restaurados."
log ""
log "Estado esperado:"
log "  router-01  192.168.100.101  hostname=router-01"
log "  srl-01     192.168.100.103  hostname=srl-01"
