from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def get_device_status(device_ip: str, device_type: str = "eos") -> dict:
    """Coleta status básico do device: hostname, uptime e número de interfaces."""
    device = connect(device_ip, device_type)
    info = await device.get_device_info()
    activity.logger.info(
        f"[MONITOR] {device_ip} ({device_type.upper()}) | "
        f"hostname={info['hostname']} | uptime={info['uptime']}s"
    )
    return {
        "device_ip": device_ip,
        "device_type": device_type,
        "hostname": info["hostname"],
        "uptime": info["uptime"],
        "interface_count": len(info["interfaces"]),
    }
