from datetime import timedelta
from dataclasses import dataclass
from temporalio import workflow
from temporalio.common import RetryPolicy

# Temporal re-executa o código do workflow para reconstruir o estado (event sourcing).
# imports_passed_through() garante que importações de activities e módulos externos
# não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities import get_device_info


@dataclass
class DeviceInfoInput:
    device_ip: str
    device_type: str = "eos"  # "eos" para Arista cEOS, "srl" para Nokia SR Linux


@workflow.defn
class DeviceInfoWorkflow:
    """
    Workflow básico: coleta informações de um dispositivo de rede.

    Conceitos demonstrados:
    - @workflow.defn e @workflow.run
    - workflow.execute_activity() com timeout
    - RetryPolicy: tentativas automáticas em caso de falha
    - workflow.logger para rastreabilidade no Temporal UI
    """

    @workflow.run
    async def run(self, input: DeviceInfoInput) -> dict:
        workflow.logger.info(
            f"[EX01] Coletando informações de {input.device_ip} (vendor: {input.device_type})"
        )

        # RetryPolicy: define quantas tentativas e com qual intervalo
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,   # 5s, 10s, 20s...
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
        )

        result = await workflow.execute_activity(
            get_device_info,
            args=[input.device_ip, input.device_type],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        workflow.logger.info(
            f"[EX01] Concluído: {result['data']['hostname']} "
            f"({result['data']['os_version']}) — "
            f"uptime {result['data']['uptime']}s"
        )

        return result
