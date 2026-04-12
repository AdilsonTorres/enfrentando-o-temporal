import asyncio
import os
from dotenv import load_dotenv
from temporalio.client import Client

from workflow import DeviceMonitoringWorkflow, MonitoringInput

load_dotenv("../../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")


async def main():
    client = await Client.connect("localhost:7233")

    print(f"Iniciando monitoramento contínuo de {DEVICE_01}")
    print("O workflow vai verificar o device a cada 30 segundos.")
    print("Após 10 iterações, continue_as_new reinicia o histórico automaticamente.")
    print("Observe no Temporal UI: o histórico é substituído, mas o workflow ID permanece o mesmo.")
    print("Acompanhe: http://localhost:8080")

    # start_workflow() dispara e retorna imediatamente (não espera o resultado).
    # execute_workflow() bloquearia até o workflow terminar — inadequado para loops.
    await client.start_workflow(
        DeviceMonitoringWorkflow.run,
        MonitoringInput(device_ip=DEVICE_01, check_count=0, max_checks=10),
        id="monitoring-router-01",
        task_queue="monitoring-queue",
    )

    print("\n[OK] Workflow de monitoramento iniciado!")


if __name__ == "__main__":
    asyncio.run(main())
