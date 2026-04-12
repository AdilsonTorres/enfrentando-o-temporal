from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def apply_banner(device_ip: str, banner_text: str, device_type: str = "eos") -> dict:
    """
    Aplica um banner no dispositivo.

    Arista EOS   → Scrapli: banner motd
    Nokia SR Linux → gNMI: /system/banner login-banner
    """
    await connect(device_ip, device_type).apply_banner(banner_text)
    activity.logger.info(f"[OK] Banner aplicado em {device_ip} ({device_type.upper()})")
    return {"status": True, "device_ip": device_ip, "device_type": device_type}
