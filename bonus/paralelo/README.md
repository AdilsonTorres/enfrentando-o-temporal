# Bônus — Execução Paralela: asyncio.gather()

## Objetivo

Demonstrar como executar múltiplas activities em paralelo dentro de um workflow Temporal usando `asyncio.gather()`, reduzindo o tempo total de N × t para aproximadamente t (tempo de 1 device).

## Use Case

Aplicar um banner MOTD em dois dispositivos simultaneamente — um Arista cEOS e um Nokia SR Linux — em vez de um por vez.

## O problema com execução sequencial

```
Sequencial:  [device1: 30s] → [device2: 30s]  = 60s total
Paralelo:    [device1: 30s]
             [device2: 30s]                    = ~30s total
```

## Conceitos abordados

| Conceito | Onde ver |
|---|---|
| `asyncio.gather()` com activities | `workflow.py` |
| `return_exceptions=True` — falha isolada | `workflow.py` |
| `DeviceTarget` (dataclass multi-vendor) | `workflow.py` |
| Resultado por device (sucesso/falha individual) | `workflow.py` |

> **Por que `asyncio.gather()` é seguro aqui?** Ele agenda múltiplas activities no Temporal — não executa I/O diretamente no workflow. O Temporal gerencia a execução em paralelo de forma determinística.

> **`return_exceptions=True`** garante que a falha em um device não cancela os demais. Cada resultado é verificado individualmente.

## Como executar

```bash
# Terminal 1: worker
cd bonus/paralelo
python worker.py

# Terminal 2: disparar
python run.py
```

## O que observar no Temporal UI (http://localhost:8080)

- Duas activities `apply_banner` aparecem como **scheduled simultaneamente** no histórico de eventos
- Ambas completam em paralelo — não em sequência
- Se um device falhar, o outro continua — veja o resultado separado por device

## Estrutura

```
workflow.py          ← MultiBannerWorkflow com asyncio.gather()
activities/
  device.py          ← apply_banner (Arista + Nokia)
worker.py            ← processo que executa workflows e activities
run.py               ← dispara o workflow com lista de devices
```
