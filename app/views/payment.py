import json
from datetime import datetime as dt
import config
from aiohttp import web
from app.models.user import Transaction, User, YookassaPayment
from app.logger import get_logger

logger = get_logger("yookassa_webhook")
routes = web.RouteTableDef()


@routes.post('/yookassa/webhook')
async def yookassa_webhook_view(request: web.Request):
    try:
        body = await request.text()
        signature = request.headers.get("Content-Signature", "")
        if signature.startswith("sha256="):
            signature = signature[7:]

        from payment_clients.yookassa import YooKassaClient
        yookassa = YooKassaClient(
            shop_id=config.YOOKASSA_SHOP_ID or "",
            secret_key=config.YOOKASSA_SECRET_KEY or "",
        )
        if not yookassa.verify_webhook_signature(body, signature):
            logger.warning("YooKassa: invalid webhook signature")
            return web.Response(text="bad signature", status=400)

        data = json.loads(body)
        event_type = data.get("event")
        payment_data = data.get("object", {})
        payment_id = payment_data.get("id", "")
        status = payment_data.get("status", "")
        metadata = payment_data.get("metadata", {}) or {}
        transaction_id = metadata.get("transaction_id")

        logger.info(f"YooKassa webhook: event={event_type} payment_id={payment_id} status={status} txn={transaction_id}")

        if not transaction_id:
            logger.warning("YooKassa: no transaction_id in metadata")
            return web.json_response({"error": "no transaction_id"}, status=400)

        transaction = await Transaction.get_or_none(id=int(transaction_id)).prefetch_related("user")
        if not transaction:
            logger.warning(f"YooKassa: transaction {transaction_id} not found")
            return web.json_response({"error": "not found"}, status=404)

        if transaction.status == Transaction.Status.finished:
            logger.info(f"YooKassa: transaction {transaction_id} already finished")
            return web.json_response({"result": "ok"})

        if status == "succeeded":
            amount_value = float(payment_data.get("amount", {}).get("value", 0))
            transaction.status = Transaction.Status.finished
            transaction.amount_paid = int(amount_value)
            transaction.finished_at = dt.utcnow()
            await transaction.save()

            yoo_record = await YookassaPayment.get_or_none(transaction=transaction)
            if yoo_record:
                yoo_record.status = "succeeded"
                yoo_record.yookassa_payment_id = payment_id
                await yoo_record.save()

            logger.info(f"YooKassa: payment SUCCESS User {transaction.user_id}: {int(amount_value)} RUB")

            try:
                from app.main import bot
                await bot.send_message(
                    transaction.user_id,
                    f"Баланс пополнен!\n\nЗачислено: {int(amount_value):,} руб.\nЗаказ: #{transaction_id}"
                )
            except Exception as e:
                logger.error(f"YooKassa: telegram notify error: {e}")

        elif status == "canceled":
            transaction.status = Transaction.Status.canceled
            await transaction.save()
            yoo_record = await YookassaPayment.get_or_none(transaction=transaction)
            if yoo_record:
                yoo_record.status = "canceled"
                await yoo_record.save()
            logger.info(f"YooKassa: payment CANCELED transaction {transaction_id}")

        return web.json_response({"result": "ok"})

    except Exception as e:
        logger.error(f"YooKassa: global webhook error: {e}")
        return web.json_response({"error": "internal error"}, status=500)
