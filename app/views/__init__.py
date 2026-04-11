from aiogram import Dispatcher
from aiohttp import web
import config
from app.logger import get_logger

logger = get_logger("webapp")
webapp = web.Application()
webapp_runner: web.TCPSite = None

async def on_startup() -> None:
    from . import payment
    
    # Очищаем старые маршруты, если они были, и добавляем новые
    webapp.add_routes(payment.routes)
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    
    global webapp_runner
    # ВАЖНО: слушаем 0.0.0.0, чтобы Docker мог прокинуть трафик
    webapp_runner = web.TCPSite(
        runner, host="0.0.0.0", port=config.WEBAPP_PORT
    )
    await webapp_runner.start()
    logger.info(f"=== Webapp started on port {config.WEBAPP_PORT} ===")

async def on_shutdown() -> None:
    if webapp_runner:
        await webapp_runner.stop()

def setup_webapp(dp: Dispatcher) -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
