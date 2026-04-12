from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities.compliance import check_device_compliance
    from activities.notify import send_message


@dataclass
class ComplianceCheckInput:
    device_ip: str
    expected_value: str       # hostname, prefixo de rota ou interface (dependendo de check_type)
    device_type: str = "eos"  # "eos" → Arista, "srl" → Nokia SR Linux
    check_type: str = "hostname"  # "hostname" | "route" | "mac_port"


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
)

ACT_TIMEOUT = timedelta(seconds=60)

_CHECK_LABELS = {
    "hostname": "Hostname",
    "route":    "Rota",
    "mac_port": "Porta/Interface",
}


@workflow.defn
class ComplianceCheckWorkflow:
    """
    Workflow de compliance: verifica periodicamente se um atributo do device
    está conforme o esperado. Executado via Schedule (substitui o CRON).

    check_type suportados:
      "hostname"  → hostname == expected_value
      "route"     → rota expected_value existe na tabela de roteamento
      "mac_port"  → interface expected_value está UP/connected

    Vantagens do Schedule sobre CRON:
    - Visibilidade completa no Temporal UI (histórico de cada execução)
    - Pause/resume sem editar crontab
    - Retry automático se o device estiver indisponível
    - Sem perda de execuções se o servidor reiniciar
    """

    @workflow.run
    async def run(self, input: ComplianceCheckInput) -> dict:
        ts = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
        label = _CHECK_LABELS.get(input.check_type, input.check_type)
        workflow.logger.info(
            f"[COMPLIANCE] {input.device_ip} ({input.device_type.upper()}) | "
            f"check={input.check_type} esperado='{input.expected_value}' | {ts}"
        )

        result = await workflow.execute_activity(
            check_device_compliance,
            args=[input.device_ip, input.expected_value, input.device_type, input.check_type],
            start_to_close_timeout=ACT_TIMEOUT,
            retry_policy=RETRY,
        )

        if not result["compliant"]:
            alert = (
                f"🚨 COMPLIANCE ALERT\n"
                f"📍 Device   : {input.device_ip} ({result['device_type'].upper()})\n"
                f"🔍 Tipo     : {label}\n"
                f"✅ Esperado : {result['expected_value']}\n"
                f"❌ Encontrado: {result['actual_value']}\n"
                f"⏰ Horário  : {result['checked_at']}"
            )
            workflow.logger.warning(alert)
            await workflow.execute_activity(
                send_message,
                alert,
                start_to_close_timeout=ACT_TIMEOUT,
            )

        else:
            workflow.logger.info(
                f"[COMPLIANCE OK] {input.device_ip} ({input.device_type.upper()}) — "
                f"{label} '{result['actual_value']}' ✓ | {result['checked_at']}"
            )

        return result
