# Exercício 5 — SAGA + Human-in-the-Loop: Admin-State de Interface

## Objetivo

Combinar os dois padrões anteriores — SAGA (ex02) e Human-in-the-Loop (ex03) — em um único workflow: alteração do admin-state de uma interface com aprovação obrigatória do operador e rollback automático se a validação falhar.

## Use Case

Operador solicita ligar ou desligar uma interface de rede. O workflow pausa e aguarda aprovação via signal. Se aprovado, aplica a mudança e valida. Se a validação falhar, a interface é restaurada automaticamente ao estado original (SAGA).

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| `@workflow.signal` (approve / reject) | `workflow.py` |
| `@workflow.query` (current_status) | `workflow.py` |
| `workflow.wait_condition()` — pausa sem CPU | `workflow.py` |
| Padrão SAGA com compensações | `workflow.py` |
| Rollback automático pós-validação | `workflow.py` |
| Notificação Telegram | `activities/notify.py` |

## Fluxo do workflow

```
FASE 1 — Leitura
  Passo 1: ler estado atual da interface (original_state)

FASE 2 — Aprovação
  Passo 2: enviar notificação Telegram pedindo aprovação
  Passo 3: pausar e aguardar signal (timeout: 10 minutos)
    → approved  → avançar para Fase 3
    → rejected  → notificar e terminar
    → timeout   → notificar e terminar

FASE 3 — Aplicação com SAGA
  Passo 4: registrar compensação (restaurar original_state)
  Passo 5: aplicar novo admin-state
  Passo 6: validar interface no device
    → OK        → notificar sucesso
    → Falha     → executar compensações em ordem inversa → rollback
```

## Como executar

```bash
# Terminal 1: worker
cd exercicio_05_interface_ops
python worker.py

# Terminal 2: disparar (pausa aguardando aprovação)
python run.py                              # Arista: Ethernet1 → down
python run.py --up                         # Arista: Ethernet1 → up
python run.py --nokia                      # Nokia: ethernet-1/1 → down
python run.py --nokia --up                 # Nokia: ethernet-1/1 → up

# Terminal 3: aprovar ou rejeitar (enquanto o workflow aguarda)
python run.py --approve <workflow-id>
python run.py --reject  <workflow-id> "Motivo da rejeição"

# Consultar status a qualquer momento
python run.py --status <workflow-id>
```

## O que observar no Temporal UI (http://localhost:8080)

- **Estado `aguardando_aprovacao`**: workflow Running, sem nenhuma activity em execução — sem CPU, sem polling
- **Query em tempo real**: `--status` chama `current_status()` sem modificar o workflow
- **Após aprovação**: ver `set_interface_state` e `validate_interface_state` executando em sequência
- **Com rollback**: interrompa o device após a aprovação — veja `rollback_interface_state` sendo chamada automaticamente

## Estrutura

```
workflow.py          ← SAGA + signals + query
activities/
  device.py          ← get/set/validate/rollback_interface_state
  notify.py          ← send_message (Telegram)
worker.py            ← processo que executa workflows e activities
run.py               ← dispara, aprova, rejeita e consulta status
```
