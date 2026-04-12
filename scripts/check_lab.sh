#!/usr/bin/env bash
# =============================================================================
# check_lab.sh — Verifica se o lab está pronto para a apresentação
#
# Testa:
#   - Temporal Server e UI
#   - Conectividade SSH com router-01 (Arista cEOS)
#   - Conectividade gNMI com srl-01 (Nokia SR Linux)
#   - Hostnames padrão nos dispositivos
#   - Credenciais Telegram
#
# Uso:
#   cd /home/adilson/semanacap/enfrentando-o-temporal
#   source .venv/bin/activate
#   bash scripts/check_lab.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }

FAILURES=0

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Check Lab — NIC.br Semana de Capacitação   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

cd "$PROJECT_DIR"
source .env 2>/dev/null || true

# ─── Temporal ─────────────────────────────────────────────────────────────────
echo "[ Temporal ]"

if curl -s --max-time 5 "http://localhost:7233" >/dev/null 2>&1 || \
   python -c "import socket; s=socket.create_connection(('localhost',7233),3); s.close()" 2>/dev/null; then
    ok "Temporal Server (localhost:7233)"
else
    fail "Temporal Server não acessível em localhost:7233"
fi

if curl -s --max-time 5 "http://localhost:8080" | grep -q "Temporal" 2>/dev/null; then
    ok "Temporal UI (http://localhost:8080)"
else
    fail "Temporal UI não acessível em http://localhost:8080"
fi

echo ""

# ─── Dispositivos ─────────────────────────────────────────────────────────────
echo "[ Dispositivos ]"

DEVICE_01="${DEVICE_01:-192.168.100.101}"
DEVICE_03="${DEVICE_03:-192.168.100.103}"

if python -c "import socket; s=socket.create_connection(('$DEVICE_01',22),3); s.close()" 2>/dev/null; then
    ok "router-01 ($DEVICE_01) — SSH acessível"
else
    fail "router-01 ($DEVICE_01) — SSH inacessível"
fi

if python -c "import socket; s=socket.create_connection(('$DEVICE_03',57400),3); s.close()" 2>/dev/null; then
    ok "srl-01 ($DEVICE_03) — gNMI (57400) acessível"
else
    fail "srl-01 ($DEVICE_03) — gNMI (57400) inacessível"
fi

echo ""

# ─── Hostnames padrão ─────────────────────────────────────────────────────────
echo "[ Hostnames ]"

python - <<'PYEOF' 2>/dev/null || true
import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv(".env")
sys.path.insert(0, ".")

try:
    from shared.device_drivers import connect

    GREEN = '\033[0;32m'
    RED   = '\033[0;31m'
    NC    = '\033[0m'

    EXPECTED = {
        os.getenv("DEVICE_01", "192.168.100.101"): ("router-01", "eos"),
        os.getenv("DEVICE_03", "192.168.100.103"): ("srl-01",    "srl"),
    }

    async def check(ip, expected_hostname, device_type):
        try:
            actual = await connect(ip, device_type).get_hostname()
            if actual == expected_hostname:
                print(f"  {GREEN}✓{NC} {ip}: hostname='{actual}'")
            else:
                print(f"  {RED}✗{NC} {ip}: hostname='{actual}' (esperado '{expected_hostname}') — execute reset_devices.sh")
        except Exception as e:
            print(f"  {RED}✗{NC} {ip}: erro — {e}")

    async def main():
        await asyncio.gather(*[
            check(ip, exp, dtype)
            for ip, (exp, dtype) in EXPECTED.items()
        ])

    asyncio.run(main())
except ImportError:
    print("  ⚠ Dependências não instaladas — execute: uv pip install -e .")
PYEOF

echo ""

# ─── Telegram ─────────────────────────────────────────────────────────────────
echo "[ Telegram ]"

BOT_TOKEN="${BOT_TOKEN:-}"
CHAT_ID="${CHAT_ID:-}"

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    warn "BOT_TOKEN ou CHAT_ID não configurados no .env"
else
    RESULT=$(curl -s --max-time 5 "https://api.telegram.org/bot${BOT_TOKEN}/getChat?chat_id=${CHAT_ID}" 2>/dev/null)
    if echo "$RESULT" | python -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
        TITLE=$(echo "$RESULT" | python -c "import sys,json; d=json.load(sys.stdin); print(d['result'].get('title','?'))" 2>/dev/null)
        ok "Bot alcança o chat '$TITLE' (CHAT_ID=$CHAT_ID)"
    else
        fail "Bot não consegue alcançar CHAT_ID=$CHAT_ID"
    fi
fi

echo ""

# ─── Resultado final ──────────────────────────────────────────────────────────
if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}✓ Lab pronto para a apresentação!${NC}"
else
    echo -e "${RED}✗ $FAILURES problema(s) encontrado(s). Corrija antes da apresentação.${NC}"
    exit 1
fi
echo ""
