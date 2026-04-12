# Exercício 4 — Schedules: Substituindo o CRON

## Objetivo

Demonstrar como o Temporal Schedules substitui os CRONs tradicionais com observabilidade, controle e confiabilidade.

## Use Case

Rodar múltiplos checks de compliance simultaneamente, cada um em seu próprio schedule (a cada 2 minutos):

| `--check-type` | O que verifica | Valor padrão |
|---|---|---|
| `hostname` | hostname do device == valor esperado | `router-01` / `srl-01` |
| `route` | prefixo de rota existe na tabela | `0.0.0.0/0` |
| `mac_port` | interface está operacionalmente UP | `Ethernet1` / `ethernet-1/1` |

## Comparação CRON vs Schedule

| | CRON | Temporal Schedule |
|---|---|---|
| Histórico de execuções | Apenas logs do sistema | Visual no Temporal UI |
| Pause/resume | Comentar crontab | `--pause` / `--resume` |
| Retry se falhar | Não | Sim, via RetryPolicy |
| Visibilidade do output | Nenhuma | Input/Output de cada run |
| Execução forçada | `cron.d` reload | `--trigger` |

## Como executar

```bash
# Terminal 1: worker
cd exercicio_04_schedules
python worker.py

# Criar os 3 tipos de compliance para router-01 (rodam simultaneamente):
python run.py --create --check-type hostname   # compliance-router-01-hostname
python run.py --create --check-type route      # compliance-router-01-route
python run.py --create --check-type mac_port   # compliance-router-01-macport

# Nokia SR Linux:
python run.py --create --check-type hostname --nokia
python run.py --create --check-type route --nokia
python run.py --create --check-type mac_port --nokia

# Listar schedules ativos:
python run.py --list

# Forçar execução imediata:
python run.py --trigger compliance-router-01-hostname

# Pausar / retomar:
python run.py --pause  compliance-router-01-hostname
python run.py --resume compliance-router-01-hostname

# Deletar um schedule específico:
python run.py --delete compliance-router-01-hostname

# Deletar todos os schedules de um device de uma vez:
python run.py --delete-all              # router-01
python run.py --delete-all --nokia      # srl-01

# Sobrescrever o valor esperado (opcional):
python run.py --create --check-type route --expected 10.0.0.0/8
```

## Para ver o alerta de compliance

Altere manualmente o hostname do router-01 via SSH:

```
ssh admin@192.168.100.101
configure
hostname router-01-ERRADO
exit
```

Na próxima execução (ou forçada com `--trigger`), o Telegram recebe:
```
🚨 COMPLIANCE ALERT
📍 Device    : 192.168.100.101 (EOS)
🔍 Tipo      : Hostname
✅ Esperado  : router-01
❌ Encontrado: router-01-ERRADO
```

Restaurar depois:
```bash
bash ~/semanacap/enfrentando-o-temporal/scripts/reset_devices.sh
```

## O que observar no Temporal UI

- Menu **Schedules** (lado esquerdo) → ver os 3 schedules criados para o mesmo device
- Clicar em `compliance-router-01-hostname` → ver próxima execução, histórico de runs
- Clicar em uma execução → ver Input/Output completo da activity (compliant, actual_value, check_type)
- Pausar um schedule → no UI aparece "Paused", os outros dois continuam rodando
