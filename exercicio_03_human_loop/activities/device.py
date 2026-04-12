from shared.device_drivers import connect

from temporalio import activity


@activity.defn
async def get_interface_description(device_ip: str, interface: str, device_type: str = "eos") -> str:
    """
    Lê a descrição atual de uma interface.

    Arista EOS   : Ethernet1, Management0, ...
    Nokia SR Linux: ethernet-1/1, mgmt0, ...
    """
    desc = await connect(device_ip, device_type).get_interface_description(interface)
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): {interface} descrição='{desc}'")
    return desc


@activity.defn
async def apply_interface_description(
    device_ip: str, interface: str, description: str, device_type: str = "eos"
) -> dict:
    """
    Aplica uma nova descrição em uma interface.

    Arista EOS   → interface <if> + description <desc>
    Nokia SR Linux → gNMI: /interface[name=<if>] description
    """
    await connect(device_ip, device_type).set_interface_description(interface, description)
    activity.logger.info(f"[OK] {device_ip} ({device_type.upper()}): {interface} descrição → '{description}'")
    return {"status": True, "interface": interface, "description": description}
