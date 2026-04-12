# Exercício 2 — SAGA: Configuração com Rollback Automático

## Objetivo

Demonstrar o padrão SAGA para garantir que mudanças de configuração sejam revertidas automaticamente em caso de falha — sem código de rollback manual espalhado pelo script.

## Use Case

Alterar o hostname de um dispositivo com validação posterior. Se a validação falhar, o hostname é restaurado automaticamente ao valor original.

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| SAGA / compensating transactions | `workflow.py` |
| Lista de compensações (LIFO) | `workflow.py` |
| Retry policy por activity | `workflow.py` |
| Notificação Telegram | `activities/notify.py` |

## Padrão SAGA — como funciona

```
PASSO 1: ler hostname atual → registra compensação: restaurar hostname
PASSO 2: aplicar novo hostname
PASSO 3: validar hostname no device

  Se PASSO 3 falhar:
    → executar compensações em ordem inversa
    → restaurar hostname original
    → notificar operador
```

**Por que é melhor que try/except:**
- O try/except não sobrevive a crashes do processo
- O Temporal persiste o estado: mesmo que o worker reinicie no meio do rollback, ele continua de onde parou

## Como executar

```bash
# Terminal 1: worker
cd exercicio_02_saga
python worker.py

# Terminal 2: execução normal (deve ter sucesso)
python run.py

# Terminal 2: forçar falha e ver o rollback
python run.py --force-fail
```

## O que observar no Temporal UI

- Modo normal: ver cada activity (get → apply → validate) completando em sequência
- Modo falha: ver a sequência parar na validação e as activities de rollback sendo executadas em seguida
