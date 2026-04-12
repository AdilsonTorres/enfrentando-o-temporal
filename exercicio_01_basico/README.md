# Exercício 1 — Workflow Básico

## Objetivo

Entender os blocos fundamentais do Temporal: Workflow, Activity, Worker e RetryPolicy.

## Use Case

Coletar informações básicas (hostname, OS version, uptime, interfaces) de um dispositivo Arista cEOS usando NAPALM.

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| `@workflow.defn` / `@workflow.run` | `workflow.py` |
| `@activity.defn` | `activities.py` |
| `workflow.execute_activity()` | `workflow.py` |
| `RetryPolicy` (tentativas automáticas) | `workflow.py` |
| Worker + Task Queue | `worker.py` |
| Client (dispara o workflow) | `run.py` |

## Como executar

```bash
# Terminal 1: subir o Temporal
cd ../infra && docker compose --env-file .env up -d

# Terminal 2: iniciar o worker
cd exercicio_01_basico
python worker.py

# Terminal 3: disparar o workflow
python run.py
```

## O que observar no Temporal UI (http://localhost:8080)

1. Acesse o namespace `default`
2. Encontre o workflow `device-info-router-01`
3. Veja o **histórico de eventos**: ActivityTaskScheduled, ActivityTaskStarted, ActivityTaskCompleted
4. Para testar o **retry**: pare o container do device e execute `python run.py` — veja as tentativas automáticas
   ```bash
   # Para o device
   docker stop clab-enfrentando-o-temporal-router-01

   # Execute o workflow e observe os retries no Temporal UI
   python run.py

   # Religa o device
   docker start clab-enfrentando-o-temporal-router-01
   ```
   > **Aguardar ~3-5 minutos** após `docker start` para o cEOS reinicializar.
   > Confirmar com `ssh admin@192.168.100.101` antes de continuar.

## Estrutura

```
workflow.py      ← define o fluxo de execução
activities.py    ← código que toca o device (NAPALM)
worker.py        ← processo que executa workflows e activities
run.py           ← dispara o workflow
```
