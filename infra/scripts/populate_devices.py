"""
populate_devices.py — Popula os dispositivos do lab com configurações realistas.

Execute uma vez após `clab deploy` para que os exercícios trabalhem com dados
concretos: IPs de interface, prefixos de loopback, eBGP, NTP e descrições.

Endereçamento:
  router-01  Ethernet1  10.0.12.1/30   Loopback0  192.0.2.1/32
  srl-01     ethernet-1/1  10.0.34.1/30  system0  192.0.2.3/32

Uso:
  cd /home/adilson/semanacap/enfrentando-o-temporal
  source .venv/bin/activate
  python infra/scripts/populate_devices.py
"""

import asyncio
import os

from dotenv import load_dotenv

# ── Carrega .env e importa helpers de Nornir ──────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from shared.nornir_helpers import make_eos, make_srl

from nornir.core.task import Result, Task
from nornir_scrapli.tasks import send_configs
from nornir_srl.connections.srlinux import CONNECTION_NAME as SRL_CONN


# ── Configurações do lab ──────────────────────────────────────────────────────

DEVICES = {
    "router-01": {
        "ip": os.getenv("DEVICE_01", "192.168.100.101"),
        "type": "eos",
        "hostname": "router-01",
        "data_iface": "Ethernet1",
        "data_desc": "lab-link",
        "data_ip": "10.0.12.1/30",
        "loopback": "Loopback0",
        "loopback_ip": "192.0.2.1/32",
    },
    "srl-01": {
        "ip": os.getenv("DEVICE_03", "192.168.100.103"),
        "type": "srl",
        "hostname": "srl-01",
        "data_iface": "ethernet-1/1",
        "data_desc": "lab-link",
        "data_ip": "10.0.34.1/30",
        "loopback_ip": "192.0.2.3/32",
    },
}


# ── Tasks EOS ─────────────────────────────────────────────────────────────────

def _eos_populate(task: Task, cfg: dict) -> Result:
    """Aplica toda a configuração realista em um roteador Arista cEOS."""
    iface = cfg["data_iface"]
    configs = [
        # Interface de dados com IP e descrição
        f"interface {iface}",
        f"  description {cfg['data_desc']}",
        f"  ip address {cfg['data_ip']}",
        "  no shutdown",
        "exit",
        # Loopback como router-id e prefixo anunciável
        f"interface {cfg['loopback']}",
        "  description router-id",
        f"  ip address {cfg['loopback_ip']}",
        "exit",
        # NTP (servidor fictício para fins de lab)
        "ntp server 10.0.0.1",
    ]
    task.run(task=send_configs, configs=configs)
    return Result(host=task.host, result={"status": True, "device": cfg["hostname"]}, changed=True)


# ── Tasks SRL ─────────────────────────────────────────────────────────────────

def _srl_populate(task: Task, cfg: dict) -> Result:
    """Aplica toda a configuração realista em um roteador Nokia SR Linux."""
    device = task.host.get_connection(SRL_CONN, task.nornir.config)
    iface = cfg["data_iface"]

    # Interface de dados: descrição + admin-state
    device.set_config(
        input=[{f"/interface[name={iface}]": {
            "description": cfg["data_desc"],
            "admin-state": "enable",
        }}],
        op="update",
        dry_run=False,
    )

    # Subinterface 0 na interface de dados: IP IPv4
    device.set_config(
        input=[{f"/interface[name={iface}]/subinterface[index=0]": {
            "index": 0,
            "admin-state": "enable",
            "ipv4": {
                "admin-state": "enable",
                "address": [{"ip-prefix": cfg["data_ip"]}],
            },
        }}],
        op="update",
        dry_run=False,
    )

    # Associa a subinterface ao network-instance default
    device.set_config(
        input=[{"/network-instance[name=default]/interface[name=" + iface + ".0]": {
            "name": f"{iface}.0",
        }}],
        op="update",
        dry_run=False,
    )

    # system0 (loopback): prefixo do router-id
    device.set_config(
        input=[{"/interface[name=system0]/subinterface[index=0]": {
            "index": 0,
            "ipv4": {
                "admin-state": "enable",
                "address": [{"ip-prefix": cfg["loopback_ip"]}],
            },
        }}],
        op="update",
        dry_run=False,
    )

    # Associa system0 ao network-instance default
    device.set_config(
        input=[{"/network-instance[name=default]/interface[name=system0.0]": {
            "name": "system0.0",
        }}],
        op="update",
        dry_run=False,
    )

    # NTP (servidor fictício para fins de lab)
    # SRL exige network-instance em cada server entry; usa 'mgmt' (interface de gerência).
    device.set_config(
        input=[{"/system/ntp": {
            "admin-state": "enable",
            "server": [{"address": "10.0.0.1", "network-instance": "mgmt"}],
        }}],
        op="update",
        dry_run=False,
    )

    return Result(host=task.host, result={"status": True, "device": cfg["hostname"]}, changed=True)


# ── Populate async ─────────────────────────────────────────────────────────────

async def populate(name: str, cfg: dict):
    """Conecta ao dispositivo e aplica a configuração."""
    print(f"[{name}] Iniciando configuração ({cfg['ip']}, {cfg['type'].upper()})...")
    try:
        if cfg["type"] == "eos":
            nr = make_eos(cfg["ip"])
            res = await asyncio.to_thread(nr.run, task=_eos_populate, cfg=cfg)
        else:
            nr = make_srl(cfg["ip"])
            res = await asyncio.to_thread(nr.run, task=_srl_populate, cfg=cfg)

        multi_result = res["device"]
        if not multi_result.failed:
            print(f"[{name}] ✓ Configuração aplicada")
        else:
            failed = next((r for r in multi_result if r.failed), multi_result[0])
            print(f"[{name}] ✗ Falha: {failed.exception or failed.result}")
    except Exception as e:
        print(f"[{name}] ✗ Erro: {e}")
        raise


async def main():
    print("=" * 60)
    print("Populando dispositivos do lab — NIC.br Semana de Capacitação")
    print("=" * 60)

    await asyncio.gather(
        populate("router-01", DEVICES["router-01"]),
        populate("srl-01",    DEVICES["srl-01"]),
    )

    print()
    print("Resumo da topologia após populate:")
    print("  router-01  Ethernet1  10.0.12.1/30  Lo0  192.0.2.1/32")
    print("  srl-01     eth-1/1    10.0.34.1/30  sys  192.0.2.3/32")


if __name__ == "__main__":
    asyncio.run(main())
