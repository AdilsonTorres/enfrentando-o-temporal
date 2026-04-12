from datetime import datetime

from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def check_device_compliance(
    device_ip: str,
    expected_value: str,
    device_type: str = "eos",
    check_type: str = "hostname",
) -> dict:
    """
    Verifica conformidade do dispositivo de acordo com check_type:

      "hostname"  → hostname deve ser igual a expected_value
      "route"     → rota expected_value (ex: "0.0.0.0/0") deve existir
      "mac_port"  → interface expected_value deve estar UP/connected

    Suporta device_type="eos" (Arista) e "srl" (Nokia SR Linux).
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    device = connect(device_ip, device_type)

    if check_type == "hostname":
        actual_value = await device.get_hostname()
        compliant = actual_value == expected_value

    elif check_type == "route":
        found = await device.check_route(expected_value)
        # Quando a rota não existe, usamos "NOT_FOUND" como placeholder para manter
        # a estrutura de retorno consistente (campo actual_value sempre presente).
        actual_value = expected_value if found else "NOT_FOUND"
        compliant = found

    elif check_type == "mac_port":
        actual_value = await device.get_interface_state(expected_value)
        compliant = actual_value in ("up", "connected")

    else:
        raise ValueError(f"check_type inválido: {check_type!r}. Use 'hostname', 'route' ou 'mac_port'.")

    if compliant:
        activity.logger.info(
            f"[COMPLIANCE OK] {device_ip} ({device_type.upper()}) "
            f"check={check_type} valor='{actual_value}' | {ts}"
        )
    else:
        activity.logger.warning(
            f"[COMPLIANCE FAIL] {device_ip} ({device_type.upper()}) "
            f"check={check_type} esperado='{expected_value}' encontrado='{actual_value}' | {ts}"
        )

    return {
        "compliant": compliant,
        "check_type": check_type,
        "actual_value": actual_value,
        "expected_value": expected_value,
        "device_ip": device_ip,
        "device_type": device_type,
        "checked_at": ts,
    }
