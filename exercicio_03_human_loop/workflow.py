from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# imports_passed_through() é necessário para que importações de activities e módulos
# externos não sejam interceptadas pelo sandbox de determinismo do Temporal.
with workflow.unsafe.imports_passed_through():
    from activities.device import get_interface_description, apply_interface_description
    from activities.notify import send_message


@dataclass
class InterfaceChangeInput:
    device_ip: str
    interface: str
    new_description: str
    workflow_id: str  # para incluir na mensagem de aprovação
    device_type: str = "eos"  # "eos" para Arista, "srl" para Nokia SR Linux


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
)

ACT_TIMEOUT = timedelta(seconds=60)

# Quanto tempo o workflow aguarda aprovação antes de expirar (ex: 24h em produção)
APPROVAL_TIMEOUT = timedelta(minutes=10)


@workflow.defn
class InterfaceChangeApprovalWorkflow:
    """
    Workflow Human-in-the-Loop: aguarda aprovação humana antes de aplicar mudança.

    Conceitos demonstrados:
    - @workflow.signal: recebe eventos externos (aprovação/rejeição)
    - @workflow.query: permite ler o estado atual sem modificá-lo
    - workflow.wait_condition(): pausa a execução até uma condição ser verdadeira
    - O workflow pode aguardar minutos, horas ou dias sem consumir CPU
    """

    def __init__(self):
        self._decision: str | None = None  # "approved" | "rejected"
        self._status: str = "aguardando_aprovacao"

    # ---- Signals: recebem eventos externos ----

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

    # ---- Query: lê o estado atual sem modificar nada ----
    # Diferença chave em relação ao Signal: queries são síncronas, não criam
    # eventos no histórico e não podem alterar o estado do workflow.

    @workflow.query
    def current_status(self) -> str:
        """Retorna o status atual do workflow (sem pausar nem alterar nada)."""
        return self._status

    # ---- Execução principal ----

    @workflow.run
    async def run(self, input: InterfaceChangeInput) -> dict:
        self._status = "lendo_estado_atual"
        ts = workflow.now().strftime("%Y-%m-%d %H:%M:%S")
        workflow.logger.info(
            f"[HUMAN-LOOP] Proposta de mudança: {input.interface} em "
            f"{input.device_ip} ({input.device_type})"
        )

        # Passo 1: ler estado atual da interface
        current_desc = await workflow.execute_activity(
            get_interface_description,
            args=[input.device_ip, input.interface, input.device_type],
            start_to_close_timeout=ACT_TIMEOUT,
            retry_policy=RETRY,
        )

        # Passo 2: notificar operador via Telegram com os detalhes da mudança
        self._status = "aguardando_aprovacao"
        approval_message = (
            f"⚠️  APROVAÇÃO NECESSÁRIA\n"
            f"🆔 Workflow : {input.workflow_id}\n"
            f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
            f"🔌 Interface: {input.interface}\n"
            f"📝 Atual    : '{current_desc}'\n"
            f"➡️  Nova     : '{input.new_description}'\n"
            f"⏰ Timeout  : 10 minutos\n"
            f"\nUse os botões abaixo para aprovar ou rejeitar."
        )

        await workflow.execute_activity(
            send_message,
            args=[approval_message, input.workflow_id],
            start_to_close_timeout=ACT_TIMEOUT,
        )

        workflow.logger.info("[HUMAN-LOOP] Aguardando decisão do operador...")

        # Passo 3: pausar e aguardar o signal de aprovação ou rejeição
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
                    f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )
            return {"status": "expired", "device": input.device_ip}

        # Passo 4: verificar a decisão
        if self._decision.startswith("rejected"):
            # Formato definido no signal reject(): self._decision = f"rejected:{reason}"
            reason = self._decision.split(":", 1)[1] if ":" in self._decision else "N/A"
            await workflow.execute_activity(
                send_message,
                (
                    f"🚫 REJEITADO\n"
                    f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                    f"🔌 Interface: {input.interface}\n"
                    f"💬 Motivo   : {reason}\n"
                    f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                start_to_close_timeout=ACT_TIMEOUT,
            )
            return {"status": "rejected", "reason": reason, "device": input.device_ip}

        # Passo 5: aprovado — aplicar a mudança
        self._status = "aplicando_mudanca"
        workflow.logger.info("[HUMAN-LOOP] Aprovado! Aplicando mudança...")

        result = await workflow.execute_activity(
            apply_interface_description,
            args=[input.device_ip, input.interface, input.new_description, input.device_type],
            start_to_close_timeout=ACT_TIMEOUT,
            retry_policy=RETRY,
        )

        self._status = "concluido"
        await workflow.execute_activity(
            send_message,
            (
                f"✅ MUDANÇA APLICADA\n"
                f"📍 Device   : {input.device_ip} ({input.device_type.upper()})\n"
                f"🔌 Interface: {input.interface}\n"
                f"📝 Descrição: '{input.new_description}'\n"
                f"⏰ Horário  : {workflow.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            start_to_close_timeout=ACT_TIMEOUT,
        )

        workflow.logger.info("[HUMAN-LOOP] Concluído com sucesso")
        return {**result, "status": "success"}
