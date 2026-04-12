from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def get_current_hostname(device_ip: str, device_type: str = "eos") -> str:
    """Lê o hostname atual do dispositivo."""
    hostname = await connect(device_ip, device_type).get_hostname()
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): hostname='{hostname}'")
    return hostname


@activity.defn
async def apply_hostname(device_ip: str, new_hostname: str, device_type: str = "eos") -> dict:
    """
    Aplica um novo hostname no dispositivo.

    Arista EOS  → hostname <nome>
    Nokia SRL   → gNMI: /system/name host-name
    """
    await connect(device_ip, device_type).set_hostname(new_hostname)
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): hostname → '{new_hostname}'")
    return {"status": True, "hostname": new_hostname}


@activity.defn
async def validate_hostname(device_ip: str, expected_hostname: str, device_type: str = "eos") -> bool:
    """
    Valida que o hostname está correto.
    Lança exceção se não bater — isso aciona o rollback no workflow SAGA.
    """
    actual = await connect(device_ip, device_type).get_hostname()
    if actual != expected_hostname:
        raise ValueError(f"Validação falhou: esperado '{expected_hostname}', encontrado '{actual}'")
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): hostname '{actual}' ✓")
    return True


@activity.defn
async def rollback_hostname(device_ip: str, original_hostname: str, device_type: str = "eos") -> dict:
    """
    Restaura o hostname original (compensação SAGA).
    Chamada automaticamente pelo workflow em caso de falha.
    """
    await connect(device_ip, device_type).set_hostname(original_hostname)
    activity.logger.info(f"[ROLLBACK] {device_ip} ({device_type.upper()}): hostname restaurado → '{original_hostname}'")
    return {"status": True, "hostname": original_hostname}
