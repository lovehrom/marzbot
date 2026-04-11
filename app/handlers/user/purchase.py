from aiogram import F
from aiogram.types import CallbackQuery, Message
from tortoise.transactions import in_transaction

from app.keyboards.base import MainMenu
from app.keyboards.user.proxy import Proxies, ProxiesActions
from app.keyboards.user.purchase import PurchaseService, Services, ServicesActions
from app.marzban import Marzban
from app.models.proxy import Proxy
from app.models.service import Service
from app.models.user import Invoice, User
from app.utils import helpers
from app.utils.filters import IsJoinedToChannel
from marzban_client.api.user import add_user_api_user_post
from marzban_client.models.user_create import UserCreate
from marzban_client.models.user_create_inbounds import UserCreateInbounds
from marzban_client.models.user_create_proxies import UserCreateProxies

from . import router
from .proxy import show_proxy


async def can_get_test_service(
    user: User, service: Service, query: CallbackQuery
) -> bool:
    if await user.purchased_services.filter(id=service.id).exists():
        await query.answer(
            "❌ Вы уже активировали этот тестовый период!", show_alert=True
        )
        return False
    return True


@router.message(F.text == MainMenu.purchase, IsJoinedToChannel())
@router.callback_query(Services.Callback.filter(F.action == ServicesActions.show))
async def purchase(qmsg: Message | CallbackQuery, user: User):
    q = Service.filter(server__is_enabled=True, purchaseable=True)
    services = await q.all()
    if not services:
        text = "😢 На данный момент нет доступных тарифных планов!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text, show_alert=True)
        return await qmsg.answer(text)

    text = "📲 <b>Доступные тарифы для покупки:</b>"
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text, reply_markup=Services(services=services).as_markup()
        )
    await qmsg.answer(
        text,
        reply_markup=Services(services=services).as_markup(),
    )


@router.callback_query(
    Services.Callback.filter(F.action == ServicesActions.show_service)
)
async def show_service(
    query: CallbackQuery, user: User, callback_data: Services.Callback
):
    q = Service.filter(
        server__is_enabled=True, purchaseable=True, id=callback_data.service_id
    )
    service = await q.first()
    if not service:
        await query.answer("❌ Тариф не найден!", show_alert=True)
        return await purchase(query, user)
    
    if service.is_test_service and not (
        await can_get_test_service(user, service, query)
    ):
        return

    price = service.get_price()
    # Прямой вывод без кривых хелперов
    duration = f"{service.expire_duration} дней" if service.expire_duration else "Безлимит"
    size = f"{service.data_limit} ГБ" if service.data_limit else "Безлимит"
    
    text = f"""
💎 <b>{service.name}</b>

🕐 Срок действия: {duration}
🖥 Трафик: {size}
💰 Цена: {price:,} руб.
"""
    balance = await user.get_balance()
    text += f"""
💳 Ваш баланс: {balance:,} руб.
💵 К оплате: {price:,} руб.
______________________________
    """
    if balance >= price:
        text += "\n🛍 Для покупки и активации нажмите кнопку ниже 👇"
        return await query.message.edit_text(
            text, reply_markup=PurchaseService(service).as_markup()
        )
    text += "\n😞 Недостаточно средств на балансе. Пополните счет для активации."
    return await query.message.edit_text(
        text, reply_markup=PurchaseService(service, has_balance=False).as_markup()
    )


@router.callback_query(PurchaseService.Callback.filter())
async def purchase_service(
    query: CallbackQuery, user: User, callback_data: PurchaseService.Callback
):
    q = Service.filter(
        server__is_enabled=True, purchaseable=True, id=callback_data.service_id
    )
    service = await q.first()

    if not service:
        await query.answer("❌ Тариф не найден!", show_alert=True)
        return await purchase(query, user)

    if service.is_test_service and not (
        await can_get_test_service(user, service, query)
    ):
        return

    price = service.get_price()
    balance = await user.get_balance()
    if balance < price:
        return await query.answer(
            "⁉️ Недостаточно средств для активации этого тарифа!"
        )

    try:
        async with in_transaction():
            client = Marzban.get_server(service.server_id)
            user_inbounds = UserCreateInbounds.from_dict(service.inbounds)
            user_proxies = UserCreateProxies.from_dict(
                {
                    protocol: service.create_proxy_protocols(protocol)
                    for protocol in service.inbounds
                }
            )
            proxy_obj = UserCreate(
                username=await helpers.generate_proxy_username(user),
                proxies=user_proxies,
                inbounds=user_inbounds,
                data_limit=service.data_limit,
                expire=helpers.get_expire_timestamp(service.expire_duration),
            )
            sv_proxy = await add_user_api_user_post.asyncio(
                client=client, json_body=proxy_obj
            )
            if not sv_proxy:
                return await query.answer(
                    "❌ Ошибка API при создании подписки!",
                    show_alert=True,
                )

            proxy = await Proxy.create(
                username=sv_proxy.username,
                service_id=service.id,
                user_id=user.id,
                cost=price,
                server_id=service.server_id,
            )
            await Invoice.create(
                amount=price,
                type=Invoice.Type.purchase,
                proxy=proxy,
                user=user,
            )

            await query.answer(
                "✅ Подписка успешно активирована!",
                show_alert=True,
            )
            await show_proxy(
                query,
                user,
                callback_data=Proxies.Callback(
                    proxy_id=proxy.id, action=ProxiesActions.show_proxy
                ),
            )
    except Exception as err:
        await query.answer(
            "❌ Техническая ошибка. Обратитесь к администратору.", show_alert=True
        )
        raise err
