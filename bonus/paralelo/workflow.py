import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import List
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities.device import apply_banner


@dataclass
class DeviceTarget:
    ip: str
    device_type: str = "eos"  # "eos" → Arista | "srl" → Nokia SR Linux


@dataclass
class MultiBannerInput:
    devices: List[DeviceTarget]
    banner_text: str


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=3,
)


@workflow.defn
class MultiBannerWorkflow:
    """
    Workflow de execução paralela: aplica banner em múltiplos devices simultaneamente.

    Conceito:
    - asyncio.gather() executa várias activities em paralelo.
    - Reduz o tempo total: N devices em ~1x o tempo de 1 device (não N×).
    - Resultados individuais: cada device pode ter sucesso ou falha independente.

    Exemplo com 2 devices (EOS + SRL em paralelo):
    - Sequencial: 30s + 30s = 60s
    - Paralelo   : max(30s, 30s) = 30s
    """

    @workflow.run
    async def run(self, input: MultiBannerInput) -> dict:
        labels = [f"{d.ip} ({d.device_type.upper()})" for d in input.devices]
        workflow.logger.info(
            f"[PARALELO] Aplicando banner em {len(input.devices)} devices em paralelo: {labels}"
        )

        # Criar uma coroutine para cada device
        tasks = [
            workflow.execute_activity(
                apply_banner,
                args=[device.ip, input.banner_text, device.device_type],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RETRY,
            )
            for device in input.devices
        ]

        # Executar todas em paralelo e aguardar os resultados.
        # asyncio.gather() aqui agenda as activities (não bloqueia no I/O diretamente),
        # por isso é seguro em workflows Temporal.
        # return_exceptions=True garante que uma falha não cancele os outros devices.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Processar resultados (separar sucessos de falhas)
        summary = {"success": [], "failed": []}
        for device, result in zip(input.devices, results):
            label = f"{device.ip} ({device.device_type.upper()})"
            if isinstance(result, Exception):
                summary["failed"].append({"device": label, "error": str(result)})
                workflow.logger.error(f"[PARALELO] Falha em {label}: {result}")
            else:
                summary["success"].append(label)
                workflow.logger.info(f"[PARALELO] Sucesso em {label}")

        workflow.logger.info(
            f"[PARALELO] Concluído: {len(summary['success'])} OK, "
            f"{len(summary['failed'])} falha(s)"
        )

        return summary
