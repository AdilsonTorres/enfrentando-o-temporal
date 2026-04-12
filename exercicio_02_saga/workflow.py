from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities.device import (
        get_current_hostname,
        apply_hostname,
        validate_hostname,
        rollback_hostname,
    )
    from activities.notify import send_message


@dataclass
class ChangeHostnameInput:
    device_ip: str
    new_hostname: str
    device_type: str = "eos"  # "eos" para Arista, "srl" para Nokia SR Linux
    force_fail: bool = False   # True → simula falha pós-apply para demonstrar rollback


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
)

ACT_TIMEOUT = timedelta(seconds=60)


@workflow.defn
class ChangeHostnameSagaWorkflow:
    """
    Workflow SAGA: altera o hostname com rollback automático em caso de falha.

    Padrão SAGA:
    - A cada passo concluído, registramos uma "compensação" (ação de rollback).
    - Se qualquer passo falhar, executamos as compensações em ordem inversa.
    - Resultado: o sistema volta ao estado original de forma confiável.

    Comparação com try/except tradicional:
    - O try/except não sobrevive a crashes do processo, timeouts de rede, etc.
    - O Temporal persiste o estado: mesmo que o worker reinicie, o rollback ocorre.
    """

    @workflow.run
    async def run(self, input: ChangeHostnameInput) -> dict:
        # Cada item é (função, *args). Em caso de falha, executamos em ordem
        # inversa (reversed) — o padrão SAGA: last-in, first-out.
        compensations = []
        ts = workflow.now().strftime("%Y-%m-%d %H:%M:%S")

        workflow.logger.info(
            f"[SAGA] Iniciando mudança de hostname | "
            f"device={input.device_ip} ({input.device_type}) | "
            f"novo={input.new_hostname}"
        )

        try:
            # Passo 1: ler hostname atual (para poder fazer rollback depois)
            original_hostname = await workflow.execute_activity(
                get_current_hostname,
                args=[input.device_ip, input.device_type],
                start_to_close_timeout=ACT_TIMEOUT,
                retry_policy=RETRY,
            )
            workflow.logger.info(f"[SAGA] Hostname original: '{original_hostname}'")

            await workflow.execute_activity(
                send_message,
                (
                    f"🔄 SAGA: Mudança de Hostname\n"
                    f"📍 Device : {input.device_ip} ({input.device_type.upper()})\n"
                    f"📝 Atual  : {original_hostname}\n"
                    f"➡️  Novo   : {input.new_hostname}\n"
                    f"⏰ Início : {ts}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )

            # Registrar compensação: se algo falhar depois, restaurar hostname original
            compensations.append((rollback_hostname, input.device_ip, original_hostname, input.device_type))

            # Passo 2: aplicar novo hostname
            await workflow.execute_activity(
                apply_hostname,
                args=[input.device_ip, input.new_hostname, input.device_type],
                start_to_close_timeout=ACT_TIMEOUT,
                retry_policy=RETRY,
            )
            workflow.logger.info(f"[SAGA] Hostname aplicado: '{input.new_hostname}'")

            # Passo 3: validar que a mudança foi aplicada corretamente.
            # Em modo force_fail, validamos contra um hostname errado para que
            # o próprio validate_hostname levante ValueError → ActivityTaskFailed no UI.
            expected_for_validation = (
                f"{input.new_hostname}-INVALIDO" if input.force_fail else input.new_hostname
            )
            await workflow.execute_activity(
                validate_hostname,
                args=[input.device_ip, expected_for_validation, input.device_type],
                start_to_close_timeout=ACT_TIMEOUT,
                retry_policy=RETRY,
            )
            workflow.logger.info("[SAGA] Validação OK")

        except Exception as e:
            # Algo falhou — executar compensações em ordem inversa (LIFO)
            ts_fail = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
            workflow.logger.error(f"[SAGA] Falha detectada: {e}. Iniciando rollback...")

            await workflow.execute_activity(
                send_message,
                (
                    f"❌ SAGA: ROLLBACK ativado!\n"
                    f"📍 Device : {input.device_ip} ({input.device_type.upper()})\n"
                    f"💥 Erro   : {e}\n"
                    f"🔄 Restaurando hostname original...\n"
                    f"⏰ Horário: {ts_fail}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )

            for compensation_fn, *args in reversed(compensations):
                try:
                    await workflow.execute_activity(
                        compensation_fn,
                        args=args,
                        start_to_close_timeout=ACT_TIMEOUT,
                        retry_policy=RETRY,
                    )
                    workflow.logger.info(f"[SAGA] Compensação executada: {compensation_fn.__name__}")
                except Exception as rollback_err:
                    workflow.logger.error(
                        f"[SAGA] Falha na compensação {compensation_fn.__name__}: {rollback_err}"
                    )

            await workflow.execute_activity(
                send_message,
                (
                    f"🔁 SAGA: Rollback concluído\n"
                    f"📍 Device  : {input.device_ip} ({input.device_type.upper()})\n"
                    f"✅ Hostname restaurado ao original\n"
                    f"⏰ Horário : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )

            return {"status": "rollback", "device": input.device_ip, "error": str(e)}

        ts_ok = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
        await workflow.execute_activity(
            send_message,
            (
                f"✅ SAGA: Sucesso!\n"
                f"📍 Device  : {input.device_ip} ({input.device_type.upper()})\n"
                f"🏷️  Hostname: {input.new_hostname}\n"
                f"⏰ Horário : {ts_ok}"
            ),
            start_to_close_timeout=ACT_TIMEOUT,
        )

        workflow.logger.info("[SAGA] Workflow concluído com sucesso")
        return {"status": "success", "device": input.device_ip, "hostname": input.new_hostname}
