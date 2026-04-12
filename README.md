<div class="title-block" style="text-align: center;" align="center">

# Enfrentando o Temporal

**Semana de Capacitação NIC.br**
Adilson Torres — adilson@nic.br

Tutorial hands-on de ~3 horas: Temporal aplicado à automação de redes com Arista cEOS e Nokia SR Linux.

**[Pré-requisitos](#-pré-requisitos) &nbsp;&bull;&nbsp;**
**[Dependências do sistema](#-dependências-do-sistema) &nbsp;&bull;&nbsp;**
**[Imagens do laboratório](#-imagens-do-laboratório) &nbsp;&bull;&nbsp;**
**[Temporal Server](#-temporal-server) &nbsp;&bull;&nbsp;**
**[Laboratório (containerlab)](#-laboratório-containerlab) &nbsp;&bull;&nbsp;**
**[Ambiente Python](#-ambiente-python) &nbsp;&bull;&nbsp;**
**[Exercícios](#-exercícios) &nbsp;&bull;&nbsp;**
**[Referências](#-referências)**

</div>

---

## 📋 Pré-requisitos

**Host recomendado:** Linux 64-bit (Debian/Ubuntu), 16 GB RAM, 50 GB disco, 8 vCPUs ou mais.

Acesso à Internet para download das imagens e dependências.

---

## 🚀 Dependências do sistema

### Git

```bash
apt install git -y
```

Clone do repositório:

```bash
cd /opt
git clone https://github.com/adilsonNIC/enfrentando-o-temporal.git
cd enfrentando-o-temporal
```

### Docker e Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
```

Verifique:

```bash
docker --version
docker compose version
```

### containerlab

```bash
bash -c "$(curl -sL https://get.containerlab.dev)"
```

Verifique:

```bash
containerlab version
```

### uv (gerenciador Python)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Adicione ao PATH se necessário:

```bash
export PATH=$PATH:$HOME/.local/bin
```

---

## 📦 Imagens do laboratório

### Arista cEOS (obrigatório)

A imagem cEOS **não está disponível publicamente** — precisa ser baixada da Arista e importada no Docker manualmente.

📂 **Download:** [Google Drive — Imagens de Laboratório](https://drive.google.com/drive/folders/1uLDcgJuoxOE7c4ZD3WsPwLmvPrJKqeLE)

Arquivo necessário: `cEOS-lab-4.34.2F.tar.xz`

> **Dica:** transfira o arquivo para o host de laboratório via SCP:
> ```bash
> scp cEOS-lab-4.34.2F.tar.xz usuario@<ip-do-host>:/opt/
> ```

Importe a imagem no Docker:

```bash
docker import cEOS-lab-4.34.2F.tar.xz ceos:4.34.2F
```

Verifique:

```bash
docker images | grep ceos
```

### Nokia SR Linux (download automático)

A imagem SR Linux é pública. O containerlab faz o pull automaticamente, mas você pode baixá-la antecipadamente:

```bash
docker pull ghcr.io/nokia/srlinux:latest
```

---

## ⚙️ Temporal Server

Suba o Temporal Server e a UI via Docker Compose:

```bash
cd /opt/enfrentando-o-temporal/infra
docker compose up -d
```

Aguarde os containers subirem (~30 segundos) e acesse a UI:

👉 **http://localhost:8080**

Para verificar:

```bash
docker compose ps
```

Para parar:

```bash
docker compose down
```

---

## 🧪 Laboratório (containerlab)

O laboratório inclui 1 roteador Arista cEOS e 1 nó Nokia SR Linux, conectados entre si.

### Dados de acesso

| Device | IP | Vendor | Usuário | Senha |
|---|---|---|---|---|
| router-01 | 192.168.100.101 | Arista cEOS | admin | admin |
| srl-01 | 192.168.100.103 | Nokia SR Linux | admin | NokiaSrl1! |

### Subir o laboratório

```bash
cd /opt/enfrentando-o-temporal/infra/containerlab
sudo containerlab deploy -t lab.yml
```

### Destruir o laboratório

```bash
sudo containerlab destroy -t lab.yml --cleanup
```

### Listar e inspecionar

```bash
sudo containerlab inspect --all
```

### Acessar um dispositivo via SSH

```bash
# Arista cEOS
ssh admin@192.168.100.101

# Nokia SR Linux
ssh admin@192.168.100.103
```

---

## 🐍 Ambiente Python

### Criar o ambiente virtual e instalar dependências

```bash
cd /opt/enfrentando-o-temporal
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```bash
nano .env
```

Campos principais:

```ini
# Credenciais dos devices
USER_DEVICE=admin
PASSW_DEVICE=admin
PASSW_DEVICE_NOKIA=NokiaSrl1!

# IPs dos devices (ajuste se necessário)
DEVICE_01=192.168.100.101   # Arista router-01
DEVICE_03=192.168.100.103   # Nokia srl-01

# Telegram Bot (para exercícios com notificação)
BOT_TOKEN=<seu_token>
CHAT_ID=<seu_chat_id>
```

> **Telegram:** crie um bot em [@BotFather](https://t.me/botfather) para receber as notificações dos workflows.

### Ativar/desativar o ambiente virtual

```bash
# Ativar
source .venv/bin/activate

# Desativar
deactivate
```

---

## 🖥️ Exercícios

Cada exercício tem um `worker.py` (fica rodando aguardando tarefas) e um `run.py` (dispara o workflow). Use dois terminais.

### Estrutura do projeto

```
shared/                       # Utilitários comuns: device_drivers, nornir_helpers, telegram_bot
infra/                        # Docker Compose (Temporal) + containerlab
exercicio_01_basico/          # Workflow básico: coletar facts do device
exercicio_02_saga/            # SAGA: hostname com rollback automático
exercicio_03_human_loop/      # Human-in-the-Loop: Signal + Query
exercicio_04_schedules/       # Schedules: substituindo o CRON
exercicio_05_interface_ops/   # Interface admin-state: SAGA + aprovação
bonus/
  continue_as_new/            # Monitoramento contínuo sem acumular histórico
  paralelo/                   # Execução paralela em múltiplos devices (EOS + SRL)
```

### Tabela de exercícios

| # | Tema | Conceitos Temporal | Vendor |
|---|---|---|---|
| 01 | Coletar facts do device | `@workflow.defn`, `@activity.defn`, `RetryPolicy` | EOS + SRL |
| 02 | Alterar hostname com rollback | SAGA / compensating transactions | EOS + SRL |
| 03 | Aprovar mudança de interface | `@workflow.signal`, `@workflow.query`, `wait_condition` | EOS + SRL |
| 04 | Compliance periódico | `create_schedule`, `ScheduleSpec`, hostname / rota / MAC | EOS + SRL |
| 05 | Admin-state com aprovação | SAGA + Human-in-the-Loop combinados | EOS + SRL |
| B1 | Monitoramento contínuo | `workflow.continue_as_new()` | EOS + SRL |
| B2 | Banner em EOS + SRL em paralelo | `asyncio.gather` (paralelo cross-vendor) | EOS + SRL |

---

### Exercício 01 — Workflow Básico

```bash
cd exercicio_01_basico

# Terminal 1: worker
python worker.py

# Terminal 2: disparar para Arista
python run.py

# Terminal 2: disparar para Nokia SR Linux
python run.py --nokia
```

---

### Exercício 02 — SAGA (hostname com rollback)

```bash
cd exercicio_02_saga

# Terminal 1
python worker.py

# Terminal 2: fluxo normal
python run.py

# Terminal 2: forçar falha e ver rollback automático
python run.py --force-fail

# Nokia
python run.py --nokia
python run.py --nokia --force-fail
```

---

### Exercício 03 — Human-in-the-Loop

```bash
cd exercicio_03_human_loop

# Terminal 1: worker (inclui bot de aprovação Telegram embutido)
python worker.py
# → Telegram recebe mensagem com botões ✅ Aprovar / ❌ Rejeitar
# → Clique no botão para aprovar ou rejeitar

# Terminal 2: disparar (workflow pausa aguardando aprovação)
python run.py

# Alternativa CLI:
python run.py --status <workflow-id>
python run.py --approve <workflow-id>
python run.py --reject <workflow-id> "Fora da janela de manutenção"

# Nokia
python run.py --nokia
```

---

### Exercício 04 — Schedules (compliance periódico)

```bash
cd exercicio_04_schedules

# Terminal 1
python worker.py

# Criar os 3 tipos de compliance (rodam simultaneamente, a cada 2 minutos)
python run.py --create --check-type hostname   # compliance-router-01-hostname
python run.py --create --check-type route      # compliance-router-01-route
python run.py --create --check-type mac_port   # compliance-router-01-macport

# Nokia SR Linux
python run.py --create --check-type hostname --nokia

# Gerenciar schedules
python run.py --list
python run.py --trigger compliance-router-01-hostname
python run.py --pause   compliance-router-01-hostname
python run.py --resume  compliance-router-01-hostname
python run.py --delete  compliance-router-01-hostname

# Deletar todos os schedules de um device de uma vez
python run.py --delete-all
python run.py --delete-all --nokia
```

---

### Exercício 05 — Interface Admin-State (SAGA + Aprovação)

```bash
cd exercicio_05_interface_ops

# Terminal 1
python worker.py

# Terminal 2: desabilitar interface (workflow pausa aguardando aprovação)
python run.py              # Arista → Ethernet1 → down
python run.py --up         # Arista → Ethernet1 → up
python run.py --nokia      # Nokia  → ethernet-1/1 → down

# Terminal 3: aprovar
python run.py --approve <workflow-id>

# Terminal 3: rejeitar
python run.py --reject <workflow-id> "Motivo"
```

---

### Bonus — Continue-as-New (monitoramento contínuo)

```bash
cd bonus/continue_as_new
python worker.py &
python run.py
```

---

### Bonus — Paralelo (banner em EOS + SRL simultâneos)

```bash
cd bonus/paralelo
python worker.py &
python run.py
```

Aplica banner em router-01 (Arista EOS) e srl-01 (Nokia SR Linux) **em paralelo**.
Observe no Temporal UI: duas activities disparadas no mesmo instante, vendors diferentes.

---

## 🌐 Links Úteis

| Recurso | URL |
|---|---|
| Temporal UI (local) | http://localhost:8080 |
| Documentação Temporal | https://docs.temporal.io |
| Python SDK | https://docs.temporal.io/develop/python |
| Tutoriais interativos | https://learn.temporal.io |
| Comunidade | https://community.temporal.io |
| NAPALM | https://napalm.readthedocs.io |
| PyEAPI (Arista) | https://pyeapi.readthedocs.io |
| Netmiko | https://ktbyers.github.io/netmiko |
| Nokia SR Linux | https://documentation.nokia.com/srlinux |
| containerlab | https://containerlab.dev |

---

## 📚 Referências

- [Slides da apresentação no Drive](https://drive.google.com/drive/folders/1uLDcgJuoxOE7c4ZD3WsPwLmvPrJKqeLE)
- [Projeto anterior: event-driven-automation](https://github.com/wsdoprado/event-driven-automation) — referência de integração com NetBox + FastAPI
- [O que é Temporal](https://docs.temporal.io/temporal)
- [Temporal Python SDK samples](https://github.com/temporalio/samples-python)
