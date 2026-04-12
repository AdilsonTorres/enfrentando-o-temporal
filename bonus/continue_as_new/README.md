# Bônus — Continue-as-New: Monitoramento Contínuo

## Objetivo

Demonstrar `workflow.continue_as_new()` para executar loops infinitos sem acumular histórico indefinidamente — o padrão correto para polling e monitoramento de longa duração no Temporal.

## Problema

Workflows de longa duração acumulam um histórico de eventos enorme. Após milhares de iterações, isso aumenta:
- O tempo de replay (recovery após crash do worker)
- O consumo de memória
- O custo de armazenamento

## Solução — Continue-as-New

Após `max_checks` iterações, o workflow encerra e **reinicia imediatamente** com um novo histórico — mas preservando o estado essencial (`check_count`). O workflow ID permanece o mesmo externamente.

```
Iteração 1 → 2 → ... → max_checks
                           ↓
                    continue_as_new()   ← novo histórico, mesmo ID
                           ↓
                     Iteração 0 → 1 → ...  (recomeça)
```

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| `workflow.continue_as_new()` | `workflow.py` |
| `workflow.sleep()` vs `asyncio.sleep()` | `workflow.py` |
| `start_workflow()` vs `execute_workflow()` | `run.py` |

> **`workflow.sleep()` é durável**: sobrevive a reinicializações do worker. `asyncio.sleep()` seria perdido se o processo morresse.

> **`start_workflow()`** dispara e retorna imediatamente — ideal para loops infinitos. `execute_workflow()` bloquearia esperando um resultado que nunca chega.

## Como executar

```bash
# Terminal 1: worker
cd bonus/continue_as_new
python worker.py

# Terminal 2: iniciar o monitoramento (não bloqueia)
python run.py
```

O workflow verifica o device a cada 30 segundos. Após 10 iterações (`max_checks=10` no `run.py`), `continue_as_new` reinicia o histórico automaticamente.

## O que observar no Temporal UI (http://localhost:8080)

1. Workflow permanece em **Running** indefinidamente
2. A cada 10 iterações, o histórico é reiniciado (contador de eventos volta a zero)
3. O **workflow ID** (`monitoring-router-01`) não muda entre os reinícios
4. Compare o histórico antes e depois do `continue_as_new` — o histórico antigo desaparece

## Estrutura

```
workflow.py    ← DeviceMonitoringWorkflow com continue_as_new
activities.py  ← get_device_status (lê hostname, uptime, contagem de interfaces)
worker.py      ← processo que executa workflows e activities
run.py         ← inicia o monitoramento com start_workflow()
```
