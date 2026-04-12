# Exercício 3 — Human-in-the-Loop

## Objetivo

Demonstrar como um workflow pode pausar e aguardar uma decisão humana antes de aplicar uma mudança crítica na rede — sem polling, sem scripts de aprovação ad hoc.

## Use Case

Propor a alteração da descrição de uma interface, notificar o operador via Telegram com botões interativos, e aguardar aprovação antes de aplicar.

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| `@workflow.signal` (aprovação/rejeição) | `workflow.py` |
| `@workflow.query` (consultar estado) | `workflow.py` |
| `workflow.wait_condition()` | `workflow.py` |
| Timeout de aprovação | `workflow.py` |
| Telegram inline keyboard (botões) | `activities/notify.py`, `telegram_bot.py` |

## Como funciona

```
1. Workflow lê estado atual da interface
2. Envia mensagem Telegram com os detalhes e botões ✅ Aprovar / ❌ Rejeitar
3. PAUSA — zero CPU, pode aguardar minutos ou dias
4. Operador clica no botão (ou envia --approve / --reject via CLI)
5. Worker recebe o clique e envia o Signal ao Temporal
6. Workflow recebe o Signal e continua (ou cancela)
7. Se aprovado: aplica a mudança
8. Notifica resultado via Telegram
```

## Como executar

```bash
# Terminal 1: worker (inclui o bot de aprovação Telegram embutido)
cd exercicio_03_human_loop
python worker.py
# Saída esperada:
#   Worker Human-in-the-Loop iniciado. Aguardando tarefas...
#   🤖 Bot de aprovação ativo (aguardando botões do Telegram...)

# Terminal 2: disparar o workflow (vai pausar esperando aprovação)
python run.py
# → Telegram recebe mensagem com botões ✅ Aprovar / ❌ Rejeitar
# → Clique no botão para aprovar ou rejeitar

# Alternativa CLI (sem Telegram):
python run.py --approve <workflow-id>
python run.py --reject <workflow-id> "Janela de manutenção ainda não abriu"

# Consultar status sem modificar nada:
python run.py --status <workflow-id>

# Nokia SR Linux:
python run.py --nokia
```

## Bot de aprovação Telegram

O bot de aprovação está **embutido no `worker.py`** — ele sobe automaticamente quando você inicia o worker. Não é necessário rodar nenhum processo adicional.

A lógica do bot vive em `shared/telegram_approval_bot.py` e é compartilhada com o exercício 05.

## O que observar no Temporal UI

- Workflow fica com status **Running** enquanto aguarda aprovação
- Ao clicar o botão no Telegram (ou enviar o signal via CLI), veja o evento `WorkflowExecutionSignaled` aparecer no histórico
- Após aprovação: as activities de aplicação são executadas
- Query via `--status`: não cria nenhum evento no histórico (só leitura)
