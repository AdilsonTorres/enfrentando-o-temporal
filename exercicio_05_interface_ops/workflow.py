from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities.device import (
        get_interface_state,
        set_interface_state,
        validate_interface_state,
        rollback_interface_state,
    )
    from activities.notify import send_message


@dataclass
class InterfaceAdminStateInput:
    device_ip: str
    interface: str
    new_state: str        # "up" ou "down"
    workflow_id: str      # incluído na mensagem de aprovação para referência
    device_type: str = "eos"  # "eos" → Arista cEOS | "srl" → Nokia SR Linux


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
)

ACT_TIMEOUT = timedelta(seconds=60)
APPROVAL_TIMEOUT = timedelta(minutes=10)


@workflow.defn
class InterfaceAdminStateWorkflow:
    """
    Workflow SAGA + Human-in-the-Loop: altera admin-state de interface com
    aprovação humana e rollback automático em caso de falha.

    Conceitos demonstrados (combinação do ex02 + ex03):
    - @workflow.signal: aprova ou rejeita a mudança
    - @workflow.query: consulta o status sem modificar nada
    - workflow.wait_condition(): pausa até decisão do operador
    - Padrão SAGA: compensação registrada antes da mudança, executada se a
      validação falhar — o estado original é restaurado automaticamente
    """

    def __init__(self):
        self._decision: str | None = None  # "approved" | "rejected:<motivo>"
        self._status: str = "iniciando"

    # ---- Signals ----

    @workflow.signal
    async def approve(self) -> None:
        """Sinal de aprovação: operador aprovou a mudança."""
        workflow.logger.info("[SIGNAL] Mudança aprovada pelo operador")
        self._decision = "approved"
        self._status = "aprovado"

    @workflow.signal
    async def reject(self, reason: str = "sem motivo informado") -> None:
        """Sinal de rejeição: operador rejeitou a mudança."""
        workflow.logger.info(f"[SIGNAL] Mudança rejeitada: {reason}")
        self._decision = f"rejected:{reason}"
        self._status = f"rejeitado: {reason}"

    # ---- Query ----

    @workflow.query
    def current_status(self) -> str:
        """Retorna o status atual do workflow sem modificar nada."""
        return self._status

    # ---- Execução principal ----

    @workflow.run
    async def run(self, input: InterfaceAdminStateInput) -> dict:
        compensations = []
        ts = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
        state_label = "⬇️  DOWN (shutdown)" if input.new_state == "down" else "⬆️  UP (no shutdown)"

        workflow.logger.info(
            f"[EX05] Proposta: {input.interface} → {input.new_state} | "
            f"device={input.device_ip} ({input.device_type})"
        )

        # Passo 1: ler admin-state atual
        self._status = "lendo_estado_atual"
        original_state = await workflow.execute_activity(
            get_interface_state,
            args=[input.device_ip, input.interface, input.device_type],
            start_to_close_timeout=ACT_TIMEOUT,
            retry_policy=RETRY,
        )
        workflow.logger.info(f"[EX05] Estado atual de {input.interface}: '{original_state}'")

        # Passo 2: notificar operador e aguardar aprovação
        self._status = "aguardando_aprovacao"
        await workflow.execute_activity(
            send_message,
            (
                f"⚠️  APROVAÇÃO NECESSÁRIA — Admin-State\n"
                f"🆔 Workflow : {input.workflow_id}\n"
                f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                f"🔌 Interface: {input.interface}\n"
                f"📊 Atual    : '{original_state}'\n"
                f"➡️  Novo     : {state_label}\n"
                f"⏰ Timeout  : 10 minutos\n"
                f"\nPara aprovar:\n"
                f"  python run.py --approve {input.workflow_id}\n"
                f"Para rejeitar:\n"
                f"  python run.py --reject {input.workflow_id} 'motivo'"
            ),
            start_to_close_timeout=ACT_TIMEOUT,
        )

        workflow.logger.info("[EX05] Aguardando decisão do operador...")

        # Passo 3: pausar e aguardar signal
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=APPROVAL_TIMEOUT,
            )
        except Exception:
            self._status = "expirado"
            await workflow.execute_activity(
                send_message,
                (
                    f"⌛ EXPIRADO — sem resposta\n"
                    f"🆔 Workflow : {input.workflow_id}\n"
                    f"📍 Device   : {input.device_ip}\n"
                    f"🔌 Interface: {input.interface}\n"
                    f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )
            return {"status": "expired", "interface": input.interface, "device": input.device_ip}

        # Passo 4: verificar a decisão
        if self._decision.startswith("rejected"):
            reason = self._decision.split(":", 1)[1] if ":" in self._decision else "N/A"
            await workflow.execute_activity(
                send_message,
                (
                    f"🚫 REJEITADO — mudança cancelada\n"
                    f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                    f"🔌 Interface: {input.interface}\n"
                    f"💬 Motivo   : {reason}\n"
                    f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )
            return {
                "status": "rejected",
                "reason": reason,
                "interface": input.interface,
                "device": input.device_ip,
            }

        # Passo 5: aprovado — executar mudança com SAGA
        self._status = "aplicando_mudanca"
        workflow.logger.info("[EX05] Aprovado! Aplicando mudança...")

        try:
            # Registrar compensação antes de alterar
            compensations.append((
                rollback_interface_state,
                input.device_ip, input.interface, original_state, input.device_type,
            ))

            # Aplicar novo admin-state
            await workflow.execute_activity(
                set_interface_state,
                args=[input.device_ip, input.interface, input.new_state, input.device_type],
                start_to_close_timeout=ACT_TIMEOUT,
                retry_policy=RETRY,
            )
            workflow.logger.info(f"[EX05] Admin-state '{input.new_state}' aplicado")

            # Validar — se falhar, lança exceção → aciona compensações abaixo
            await workflow.execute_activity(
                validate_interface_state,
                args=[input.device_ip, input.interface, input.new_state, input.device_type],
                start_to_close_timeout=ACT_TIMEOUT,
                retry_policy=RETRY,
            )
            workflow.logger.info("[EX05] Validação OK")

        except Exception as e:
            ts_fail = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
            workflow.logger.error(f"[EX05] Falha após aprovação: {e}. Iniciando rollback...")

            await workflow.execute_activity(
                send_message,
                (
                    f"❌ SAGA: ROLLBACK ativado!\n"
                    f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                    f"🔌 Interface: {input.interface}\n"
                    f"💥 Erro     : {e}\n"
                    f"🔄 Restaurando estado original '{original_state}'...\n"
                    f"⏰ Horário  : {ts_fail}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )

            for comp_fn, *args in reversed(compensations):
                try:
                    await workflow.execute_activity(
                        comp_fn,
                        args=args,
                        start_to_close_timeout=ACT_TIMEOUT,
                        retry_policy=RETRY,
                    )
                    workflow.logger.info(f"[EX05] Compensação executada: {comp_fn.__name__}")
                except Exception as rb_err:
                    workflow.logger.error(f"[EX05] Falha na compensação: {rb_err}")

            await workflow.execute_activity(
                send_message,
                (
                    f"🔁 SAGA: Rollback concluído\n"
                    f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                    f"🔌 Interface: {input.interface}\n"
                    f"✅ Estado restaurado para '{original_state}'\n"
                    f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )

            return {
                "status": "rollback",
                "interface": input.interface,
                "device": input.device_ip,
                "error": str(e),
            }

        # Passo 6: sucesso
        self._status = "concluido"
        await workflow.execute_activity(
            send_message,
            (
                f"✅ MUDANÇA APLICADA COM SUCESSO\n"
                f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                f"🔌 Interface: {input.interface}\n"
                f"📊 Estado   : {state_label}\n"
                f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            start_to_close_timeout=ACT_TIMEOUT,
        )

        workflow.logger.info("[EX05] Concluído com sucesso")
        return {
            "status": "success",
            "interface": input.interface,
            "final_state": input.new_state,
            "device": input.device_ip,
        }
