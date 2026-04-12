from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities import get_device_status


@dataclass
class MonitoringInput:
    device_ip: str
    device_type: str = "eos"    # "eos" para Arista, "srl" para Nokia SR Linux
    check_count: int = 0        # quantas verificações já foram feitas
    max_checks: int = 100       # após este número, continue_as_new reinicia o histórico


RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=5))


@workflow.defn
class DeviceMonitoringWorkflow:
    """
    Workflow de monitoramento contínuo com Continue-as-New.

    Problema sem Continue-as-New:
    - Workflows de longa duração acumulam um histórico enorme de eventos.
    - Isso aumenta memória, latência e custo de armazenamento.

    Solução — Continue-as-New:
    - Após N iterações, o workflow "reinicia" com um novo histórico,
      mas preserva o estado essencial (neste caso: check_count).
    - O workflow ID permanece o mesmo — parece contínuo externamente.
    - Ideal para: monitoramento, polling, health-check loops.
    """

    @workflow.run
    async def run(self, input: MonitoringInput) -> None:
        workflow.logger.info(
            f"[MONITOR] Iteração #{input.check_count} — "
            f"{input.device_ip} ({input.device_type})"
        )

        # Verificar status do device
        status = await workflow.execute_activity(
            get_device_status,
            args=[input.device_ip, input.device_type],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )

        workflow.logger.info(
            f"[MONITOR] {status['hostname']} ({status['device_type'].upper()}) — "
            f"uptime: {status['uptime']}s | interfaces: {status['interface_count']}"
        )

        # workflow.sleep() cria um timer durável no Temporal — ele sobrevive a
        # reinicializações do worker. asyncio.sleep() perderia a contagem se o
        # processo fosse reiniciado; workflow.sleep() não.
        await workflow.sleep(timedelta(seconds=30))

        # Após max_checks iterações, reinicia a contagem (limpa o histórico)
        next_count = input.check_count + 1
        if next_count >= input.max_checks:
            workflow.logger.info(
                f"[MONITOR] {next_count} iterações concluídas — reiniciando histórico (continue_as_new)"
            )
            next_count = 0

        # continue_as_new sempre chamado: mantém o workflow rodando eternamente
        # sem acumular histórico. O workflow ID permanece o mesmo externamente.
        workflow.continue_as_new(
            MonitoringInput(
                device_ip=input.device_ip,
                device_type=input.device_type,
                check_count=next_count,
                max_checks=input.max_checks,
            )
        )
