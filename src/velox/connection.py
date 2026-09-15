import httpx

from .config import ServerConfig


async def check_server(config: ServerConfig) -> tuple[str, str, str]:
    """
    Check connectivity to the Jellyfin server via /System/Info.

    :param config: Server connection configuration
    :returns: (status, server_name, version) where status is one of
        "online", "offline", "unauthorized", or "not_configured"
    """
    if not config.url or not config.api_key:
        return "not_configured", "", ""
    headers = {"Authorization": f'MediaBrowser Token="{config.api_key}"'}
    try:
        async with httpx.AsyncClient(
            base_url=config.url.rstrip("/"), headers=headers, timeout=5
        ) as client:
            info = await client.get("/System/Info")
    except httpx.HTTPError:
        return "offline", "", ""
    if info.status_code == 401:
        return "unauthorized", "", ""
    if info.status_code >= 400:
        return "offline", "", ""
    try:
        data = info.json()
    except ValueError:
        return "offline", "", ""
    return (
        "online",
        data.get("ServerName") or data.get("serverName") or "Unknown",
        data.get("Version") or data.get("version") or "Unknown",
    )
