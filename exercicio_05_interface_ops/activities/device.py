from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def get_interface_state(device_ip: str, interface: str, device_type: str = "eos") -> str:
    """
    Lê o admin-state atual de uma interface. Retorna 'up' ou 'down'.

    Arista EOS   : interfaceStatus "disabled" → down; qualquer outro → up
    Nokia SR Linux: admin-state "disable" → down; "enable" → up
    """
    state = await connect(device_ip, device_type).get_interface_state(interface)
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): {interface} admin-state='{state}'")
    return state


@activity.defn
async def set_interface_state(
    device_ip: str, interface: str, admin_state: str, device_type: str = "eos"
) -> dict:
    """
    Aplica um novo admin-state em uma interface. admin_state: 'up' ou 'down'.

    Arista EOS   → shutdown / no shutdown
    Nokia SR Linux → gNMI: admin-state disable / enable
    """
    await connect(device_ip, device_type).set_interface_state(interface, admin_state)
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): {interface} → '{admin_state}'")
    return {"status": True, "interface": interface, "admin_state": admin_state}


@activity.defn
async def validate_interface_state(
    device_ip: str, interface: str, expected_state: str, device_type: str = "eos"
) -> bool:
    """
    Valida que o admin-state da interface está correto.
    Lança exceção se não bater — isso aciona o rollback no workflow SAGA.
    """
    actual = await connect(device_ip, device_type).get_interface_state(interface)
    if actual != expected_state:
        raise ValueError(f"Validação falhou em {interface}: esperado '{expected_state}', encontrado '{actual}'")
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): {interface} admin-state='{actual}' ✓")
    return True


@activity.defn
async def rollback_interface_state(
    device_ip: str, interface: str, original_state: str, device_type: str = "eos"
) -> dict:
    """
    Restaura o admin-state original (compensação SAGA).
    Chamada automaticamente pelo workflow em caso de falha.
    """
    await connect(device_ip, device_type).set_interface_state(interface, original_state)
    activity.logger.info(f"[ROLLBACK] {device_ip} ({device_type.upper()}): {interface} restaurado → '{original_state}'")
    return {"status": True, "interface": interface, "admin_state": original_state}
