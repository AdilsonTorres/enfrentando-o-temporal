"""
shared/device_drivers.py — Abstração vendor-agnostic para Arista cEOS e Nokia SR Linux.

Centraliza toda a lógica de acesso aos devices. Os exercícios chamam métodos
simples como `device.get_hostname()` sem precisar saber nada sobre Nornir,
Scrapli, gNMI, ou diferenças entre vendors.

Uso nos exercícios:
    from shared.device_drivers import connect

    device = connect(device_ip, device_type)   # "eos" ou "srl"
    hostname = await device.get_hostname()
"""

import asyncio
import json
from datetime import datetime, timezone

from nornir_scrapli.tasks import send_command, send_configs
from nornir_srl.connections.srlinux import CONNECTION_NAME as SRL_CONN

from shared.nornir_helpers import make_eos, make_srl, srl_parse


# ── Utilitário interno ─────────────────────────────────────────────────────────

async def _run_nornir(nr, task_fn, **kwargs):
    """Executa um task Nornir em thread e retorna o resultado do host 'device'."""
    res = await asyncio.to_thread(nr.run, task=task_fn, **kwargs)
    host_result = res["device"]
    if host_result.failed:
        exc = host_result[0].exception
        if exc is None:
            raise RuntimeError(str(host_result[0].result))
        # NornirSubTaskError envolve a causa real (ex: conexão SSH recusada).
        # Propaga a exceção original para mensagem clara no Temporal UI.
        if hasattr(exc, "result") and exc.result[0].exception is not None:
            raise exc.result[0].exception
        raise exc
    return host_result[0].result


# ── Arista cEOS (Scrapli / SSH) ───────────────────────────────────────────────

class EOSDevice:
    """Operações de rede para Arista cEOS via Scrapli/SSH."""

    def __init__(self, ip: str):
        self._nr = make_eos(ip)
        self._ip = ip

    async def get_hostname(self) -> str:
        """Lê o hostname configurado no device."""
        def _task(task):
            raw = task.run(task=send_command, command="show hostname | json").result
            return json.loads(raw).get("hostname", "")
        return await _run_nornir(self._nr, _task)

    async def set_hostname(self, name: str) -> None:
        """Aplica um novo hostname. Levanta exceção em caso de falha de conexão."""
        def _task(task):
            task.run(task=send_configs, configs=[f"hostname {name}"])
        await _run_nornir(self._nr, _task)

    async def get_device_info(self) -> dict:
        """Retorna hostname, os_version, uptime (segundos) e lista de interfaces."""
        def _task(task):
            ver = json.loads(task.run(task=send_command, command="show version | json").result)
            hn = json.loads(task.run(task=send_command, command="show hostname | json").result)
            intfs = json.loads(task.run(task=send_command, command="show interfaces | json").result)
            return {
                "hostname": hn.get("hostname", ver.get("hostname", "")),
                "os_version": ver.get("version", ""),
                "uptime": int(ver.get("uptime", 0)),
                "interfaces": list(intfs.get("interfaces", {}).keys()),
            }
        return await _run_nornir(self._nr, _task)

    async def get_interface_description(self, interface: str) -> str:
        """Lê o campo description de uma interface (ex: 'uplink-to-srl-01')."""
        def _task(task):
            data = json.loads(task.run(task=send_command, command=f"show interfaces {interface} | json").result)
            return data.get("interfaces", {}).get(interface, {}).get("description", "")
        return await _run_nornir(self._nr, _task)

    async def set_interface_description(self, interface: str, description: str) -> None:
        """Aplica um novo description em uma interface."""
        def _task(task):
            task.run(task=send_configs, configs=[f"interface {interface}", f"description {description}"])
        await _run_nornir(self._nr, _task)

    async def get_interface_state(self, interface: str) -> str:
        """Retorna 'up' ou 'down' com base no admin-state da interface."""
        def _task(task):
            data = json.loads(task.run(task=send_command, command=f"show interfaces {interface} | json").result)
            status = data.get("interfaces", {}).get(interface, {}).get("interfaceStatus", "")
            return "down" if status == "disabled" else "up"
        return await _run_nornir(self._nr, _task)

    async def set_interface_state(self, interface: str, state: str) -> None:
        """state: 'up' → no shutdown | 'down' → shutdown"""
        def _task(task):
            cmd = "shutdown" if state == "down" else "no shutdown"
            task.run(task=send_configs, configs=[f"interface {interface}", cmd])
        await _run_nornir(self._nr, _task)

    async def check_route(self, prefix: str) -> bool:
        """Retorna True se o prefixo existe na tabela de roteamento."""
        def _task(task):
            raw = task.run(task=send_command, command=f"show ip route {prefix} | json").result
            routes = json.loads(raw).get("vrfs", {}).get("default", {}).get("routes", {})
            return prefix in routes
        return await _run_nornir(self._nr, _task)

    async def apply_banner(self, text: str) -> None:
        """Aplica um banner MOTD no device."""
        def _task(task):
            task.run(task=send_configs, configs=["banner motd", text, "EOF"])
        await _run_nornir(self._nr, _task)


# ── Nokia SR Linux (nornir-srl / gNMI) ────────────────────────────────────────

class SRLDevice:
    """Operações de rede para Nokia SR Linux via nornir-srl/gNMI."""

    def __init__(self, ip: str):
        self._nr = make_srl(ip)
        self._ip = ip

    async def get_hostname(self) -> str:
        """Lê o hostname configurado no device."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            return srl_parse(device.get(paths=["/system/name"], datatype="config")).get("host-name", "")
        return await _run_nornir(self._nr, _task)

    async def set_hostname(self, name: str) -> None:
        """Aplica um novo hostname via gNMI. Levanta exceção em caso de falha."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            device.set_config(
                input=[{"/system/name": {"host-name": name}}],
                op="update",
                dry_run=False,
            )
        await _run_nornir(self._nr, _task)

    async def get_device_info(self) -> dict:
        """Retorna hostname, os_version, uptime (segundos) e lista de interfaces."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            hostname = srl_parse(device.get(paths=["/system/name"], datatype="config")).get("host-name", "")
            os_version = device.get_info()["sys_info"][0].get("software-version", "")
            chassis = srl_parse(device.get(paths=["/platform/chassis"], datatype="state"))
            uptime = 0
            last_booted = chassis.get("last-booted", "")
            if last_booted:
                try:
                    boot_time = datetime.fromisoformat(last_booted.replace("Z", "+00:00"))
                    uptime = int((datetime.now(timezone.utc) - boot_time).total_seconds())
                except Exception:
                    pass
            raw_interfaces = device.get(paths=["/interface"], datatype="state")[0]
            interfaces = [i["name"] for i in raw_interfaces.get("interface", []) if "name" in i] if isinstance(raw_interfaces, dict) else []
            return {"hostname": hostname, "os_version": os_version, "uptime": uptime, "interfaces": interfaces}
        return await _run_nornir(self._nr, _task)

    async def get_interface_description(self, interface: str) -> str:
        """Lê o campo description de uma interface."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            return srl_parse(device.get(paths=[f"/interface[name={interface}]"], datatype="config")).get("description", "")
        return await _run_nornir(self._nr, _task)

    async def set_interface_description(self, interface: str, description: str) -> None:
        """Aplica um novo description em uma interface via gNMI."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            device.set_config(
                input=[{f"/interface[name={interface}]": {"description": description}}],
                op="update",
                dry_run=False,
            )
        await _run_nornir(self._nr, _task)

    async def get_interface_state(self, interface: str) -> str:
        """Retorna 'up' ou 'down' com base no admin-state da interface."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            raw = srl_parse(device.get(paths=[f"/interface[name={interface}]"], datatype="state")).get("admin-state", "enable")
            return "down" if raw == "disable" else "up"
        return await _run_nornir(self._nr, _task)

    async def set_interface_state(self, interface: str, state: str) -> None:
        """state: 'up' → enable | 'down' → disable"""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            srl_value = "disable" if state == "down" else "enable"
            device.set_config(
                input=[{f"/interface[name={interface}]": {"admin-state": srl_value}}],
                op="update",
                dry_run=False,
            )
        await _run_nornir(self._nr, _task)

    async def check_route(self, prefix: str) -> bool:
        """Retorna True se o prefixo existe na tabela de roteamento."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            escaped = prefix.replace("/", "%2F")
            path = f"/network-instance[name=default]/route-table/ipv4-unicast/route[ipv4-prefix={escaped}]"
            try:
                result = srl_parse(device.get(paths=[path], datatype="state"))
                return result.get("ipv4-prefix", "") == prefix
            except Exception:
                return False
        return await _run_nornir(self._nr, _task)

    async def apply_banner(self, text: str) -> None:
        """Aplica um banner de login no device via gNMI."""
        def _task(task):
            device = task.host.get_connection(SRL_CONN, task.nornir.config)
            device.set_config(
                input=[{"/system/banner": {"login-banner": text}}],
                op="update",
                dry_run=False,
            )
        await _run_nornir(self._nr, _task)


# ── Factory ────────────────────────────────────────────────────────────────────

def connect(ip: str, device_type: str) -> EOSDevice | SRLDevice:
    """
    Retorna um driver de device pronto para usar.

    device_type="eos" → EOSDevice (Arista cEOS via Scrapli/SSH)
    device_type="srl" → SRLDevice (Nokia SR Linux via gNMI)
    """
    if device_type == "eos":
        return EOSDevice(ip)
    elif device_type == "srl":
        return SRLDevice(ip)
    else:
        raise ValueError(f"device_type inválido: {device_type!r}. Use 'eos' ou 'srl'.")
