from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def get_device_info(device_ip: str, device_type: str = "eos") -> dict:
    """
    Coleta informações básicas do dispositivo: hostname, OS, uptime e interfaces.

    device_type="eos" → Arista cEOS (Scrapli/SSH)
    device_type="srl" → Nokia SR Linux (nornir-srl/gNMI)
    """
    device = connect(device_ip, device_type)
    data = await device.get_device_info()
    activity.logger.info(
        f"[OK] {device_ip} ({device_type.upper()}) — "
        f"hostname={data['hostname']} | os={data['os_version']} | "
        f"uptime={data['uptime']}s | interfaces={len(data['interfaces'])}"
    )
    return {"data": data, "status": "success"}
