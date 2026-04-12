"""
Exercício 4 — Schedules: Substituindo o CRON

Uso:
  # Criar schedule de hostname (padrão)
  python run.py --create                              # compliance-router-01-hostname
  python run.py --create --nokia                      # compliance-srl-01-hostname

  # Criar os 3 tipos de compliance para rodar simultaneamente:
  python run.py --create --check-type hostname        # verifica hostname
  python run.py --create --check-type route           # verifica rota 0.0.0.0/0
  python run.py --create --check-type mac_port        # verifica Ethernet1/ethernet-1/1

  # Listar schedules ativos
  python run.py --list

  # Pausar/retomar/forçar execução/deletar por schedule-id:
  python run.py --pause   compliance-router-01-hostname
  python run.py --resume  compliance-router-01-hostname
  python run.py --trigger compliance-router-01-hostname
  python run.py --delete  compliance-router-01-hostname

  # Deletar todos os schedules de um device de uma vez:
  python run.py --delete-all              # router-01
  python run.py --delete-all --nokia      # srl-01
"""

import asyncio
import os
import sys
from datetime import timedelta
from dotenv import load_dotenv
from temporalio.client import Client, ScheduleActionStartWorkflow, ScheduleSpec, ScheduleIntervalSpec
from temporalio.client import Schedule, ScheduleState

from workflow import ComplianceCheckWorkflow, ComplianceCheckInput

load_dotenv("../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01
TASK_QUEUE = "compliance-queue"

# Valor esperado padrão por check_type e device_type
_DEFAULTS = {
    "eos": {
        "hostname": "router-01",
        "route":    "0.0.0.0/0",
        "mac_port": "Ethernet1",
    },
    "srl": {
        "hostname": "srl-01",
        "route":    "0.0.0.0/0",
        "mac_port": "ethernet-1/1",
    },
}

_CHECK_TYPES = ("hostname", "route", "mac_port")


def _get_arg(args, flag):
    """Retorna o valor do argumento --flag <valor>, ou None."""
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            return args[idx + 1]
    return None


async def main():
    client = await Client.connect("localhost:7233")
    args = sys.argv[1:]

    nokia_mode = "--nokia" in args
    device_ip = DEVICE_03 if nokia_mode else DEVICE_01
    device_type = "srl" if nokia_mode else "eos"
    device_name = "srl-01" if nokia_mode else "router-01"

    check_type = _get_arg(args, "--check-type") or "hostname"
    if check_type not in _CHECK_TYPES:
        print(f"[ERRO] --check-type inválido: '{check_type}'. Opções: {_CHECK_TYPES}")
        return

    expected_value = _get_arg(args, "--expected") or _DEFAULTS[device_type][check_type]
    schedule_id = f"compliance-{device_name}-{check_type}"

    # --- Criar schedule ---
    if not args or args[0] in ("--create", "--nokia") or "--check-type" in args:
        if "--list" in args or "--pause" in args or "--resume" in args or "--trigger" in args or "--delete" in args or "--delete-all" in args:
            pass  # cai nos blocos abaixo
        else:
            print(f"Criando schedule '{schedule_id}'...")
            print(f"  Device      : {device_ip} ({device_type.upper()})")
            print(f"  Check type  : {check_type}")
            print(f"  Valor esperado: '{expected_value}'")
            print(f"  Intervalo   : a cada 2 minutos")

            await client.create_schedule(
                schedule_id,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        ComplianceCheckWorkflow.run,
                        ComplianceCheckInput(
                            device_ip=device_ip,
                            expected_value=expected_value,
                            device_type=device_type,
                            check_type=check_type,
                        ),
                        id=f"{schedule_id}-run",
                        task_queue=TASK_QUEUE,
                    ),
                    spec=ScheduleSpec(
                        intervals=[ScheduleIntervalSpec(every=timedelta(minutes=2))],
                    ),
                    state=ScheduleState(
                        note=f"Compliance check periódico: {check_type} de {device_name} ({device_type})",
                    ),
                ),
            )
            print(f"\n[OK] Schedule '{schedule_id}' criado!")
            print(f"Acompanhe no Temporal UI: http://localhost:8080 → Schedules")
            return

    # Para os demais comandos, o schedule_id pode ser passado explicitamente
    if len(args) > 1 and not args[1].startswith("--"):
        schedule_id = args[1]

    # --- Listar schedules ---
    if "--list" in args:
        print("Schedules ativos:")
        async for sched in await client.list_schedules():
            print(f"  - {sched.id}")
        return

    handle = client.get_schedule_handle(schedule_id)

    # --- Pausar ---
    if "--pause" in args:
        await handle.pause(note="Pausado manualmente via run.py")
        print(f"[OK] Schedule '{schedule_id}' pausado")
        return

    # --- Retomar ---
    if "--resume" in args:
        await handle.unpause(note="Retomado via run.py")
        print(f"[OK] Schedule '{schedule_id}' retomado")
        return

    # --- Forçar execução imediata ---
    if "--trigger" in args:
        await handle.trigger()
        print(f"[OK] Execução imediata disparada para '{schedule_id}'")
        return

    # --- Deletar schedule específico ---
    if "--delete" in args:
        await handle.delete()
        print(f"[OK] Schedule '{schedule_id}' deletado")
        return

    # --- Deletar todos os schedules do device ---
    if "--delete-all" in args:
        deleted = 0
        async for sched in await client.list_schedules():
            if sched.id.startswith(f"compliance-{device_name}-"):
                await client.get_schedule_handle(sched.id).delete()
                print(f"[OK] Deletado: {sched.id}")
                deleted += 1
        if deleted == 0:
            print(f"Nenhum schedule encontrado para '{device_name}'")
        return

    print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
