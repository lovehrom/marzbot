import hashlib
import config
from aiohttp import web
from app.models.user import Transaction, User
from app.logger import get_logger

logger = get_logger("payments")
routes = web.RouteTableDef()

@routes.post('/robokassa/result')
async def robokassa_result_view(request: web.Request):
    try:
        data = await request.post()
        out_sum = data.get("OutSum")
        inv_id = data.get("InvId")
        signature = data.get("SignatureValue")

        if not all([out_sum, inv_id, signature]):
            return web.Response(text="error: missing fields", status=400)

        # Проверка подписи по Password2
        my_sig_str = f"{out_sum}:{inv_id}:{config.ROBOKASSA_PASS_2}"
        my_sig = hashlib.md5(my_sig_str.encode()).hexdigest().upper()

        if signature.upper() == my_sig:
            # Ищем транзакцию. У тебя в модели статус 5 — это finished.
            transaction = await Transaction.get_or_none(id=int(inv_id)).prefetch_related("user")
            
            if transaction and transaction.status == Transaction.Status.waiting:
                # В твоей модели статус 5 — это завершенный платеж
                transaction.status = Transaction.Status.finished
                # Записываем сколько реально оплачено
                transaction.amount_paid = int(float(out_sum))
                await transaction.save()
                
                logger.info(f"Payment SUCCESS for User {transaction.user_id}: {out_sum} RUB")
                
                # Отправляем уведомление пользователю
                try:
                    from app.main import bot
                    await bot.send_message(
                        transaction.user_id, 
                        f"✅ <b>Баланс пополнен!</b>\n\nЗачислено: <b>{out_sum} руб.</b>"
                    )
                except Exception as e:
                    logger.error(f"Telegram notify error: {e}")

                return web.Response(text=f"OK{inv_id}")
            
            # Если транзакция уже завершена, просто отвечаем Робокассе OK
            elif transaction and transaction.status == Transaction.Status.finished:
                return web.Response(text=f"OK{inv_id}")

        logger.warning(f"Signature mismatch for InvId {inv_id}")
        return web.Response(text="bad signature", status=400)

    except Exception as e:
        logger.error(f"Global payment error: {e}")
        return web.Response(text="internal error", status=500)
