"""
Shared Nornir utilities — usadas por todos os exercícios.

Elimina a duplicação das funções factory _nr_eos/_nr_srl e do parser
de respostas gNMI do SR Linux que apareciam em cada arquivo activities/device.py.
"""

import os

from nornir.core import Nornir
from nornir.core.inventory import ConnectionOptions, Defaults, Groups, Host, Hosts, Inventory
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.plugins.runners import SerialRunner

USER_DEVICE = os.getenv("USER_DEVICE", "admin")
PASSW_DEVICE = os.getenv("PASSW_DEVICE", "admin")
PASSW_DEVICE_NOKIA = os.getenv("PASSW_DEVICE_NOKIA", "NokiaSrl1!")

# Registra plugins de conexão (scrapli, srlinux) para que nr.run() funcione
# sem precisar chamar InitNornir.
ConnectionPluginRegister.auto_register()


def make_eos(device_ip: str) -> Nornir:
    """Nornir com Scrapli para Arista cEOS (SSH)."""
    hosts = Hosts({"device": Host(
        name="device",
        hostname=device_ip,
        username=USER_DEVICE,
        password=PASSW_DEVICE,
        platform="arista_eos",
        connection_options={
            "scrapli": ConnectionOptions(
                extras={"auth_strict_key": False},
            )
        },
    )})
    return Nornir(
        inventory=Inventory(hosts=hosts, groups=Groups(), defaults=Defaults()),
        runner=SerialRunner(),
    )


def make_srl(device_ip: str) -> Nornir:
    """Nornir com nornir-srl para Nokia SR Linux (gNMI, porta 57400)."""
    hosts = Hosts({"device": Host(
        name="device",
        hostname=device_ip,
        username=USER_DEVICE,
        password=PASSW_DEVICE_NOKIA,
        platform="srlinux",
        connection_options={"srlinux": ConnectionOptions(port=57400, extras={})},
    )})
    return Nornir(
        inventory=Inventory(hosts=hosts, groups=Groups(), defaults=Defaults()),
        runner=SerialRunner(),
    )


def srl_parse(resp) -> dict:
    """
    Extrai o dicionário de dados de uma resposta gNMI do nornir-srl.

    resp é uma lista onde resp[0] é um dict {path_str: value}.
    O value pode ser um dict direto ou uma lista com um único dict.

    Exemplos:
        resp = [{"interface": {"name": "ethernet-1/1", "description": "uplink"}}]
        resp = [{"interface": [{"name": "ethernet-1/1", "description": "uplink"}]}]
    """
    data = next(iter(resp[0].values()), {})
    return data[0] if isinstance(data, list) and data else data
