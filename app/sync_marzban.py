import logging

from app.marzban import Marzban
from app.models.server import Server
from app.models.proxy import Proxy
from marzban_client.api.user import get_users_api_users_get

logger = logging.getLogger("__name__")


async def sync_proxies():
    """Удаляет proxies из БД бота, если юзер удалён в Marzban."""
    servers = await Server.all()
    Marzban.init_servers(servers)

    all_marzban_usernames = set()

    for server_id, client in Marzban.servers.items():
        try:
            response = await get_users_api_users_get.asyncio(client=client)
            users = response.users if hasattr(response, 'users') else response
            if isinstance(users, list):
                all_marzban_usernames.update(u.username for u in users)
        except Exception as e:
            logger.error(f"Ошибка получения юзеров с сервера {server_id}: {e}")

    bot_proxies = await Proxy.all()
    deleted = 0
    for proxy in bot_proxies:
        if proxy.username not in all_marzban_usernames:
            await proxy.delete()
            deleted += 1
            logger.info(f"Удалён proxy {proxy.username} — нет в Marzban")

    if deleted:
        logger.info(f"Синхронизация: удалено {deleted} proxies")
    return deleted
