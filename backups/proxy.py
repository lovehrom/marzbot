import io
from datetime import datetime as dt

import qrcode
from aiogram import F, exceptions
from aiogram.filters import Command, CommandObject
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)
from tortoise.transactions import in_transaction

from app.keyboards.base import MainMenu
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.keyboards.user.proxy import (
    ConfirmProxyPanel,
    ConfirmRenew,
    Proxies,
    ProxiesActions,
    ProxyLinks,
    ProxyPanel,
    ProxyPanelActions,
    RenewMethods,
    RenewSelectMethod,
    RenewSelectService,
    ResetPassword,
)
from app.marzban import Marzban
from app.models.proxy import Proxy, ProxyStatus
from app.models.service import Service
from app.models.user import Invoice, User
from app.utils import helpers
from app.utils.filters import IsJoinedToChannel, SuperUserAccess
from marzban_client.api.user import (
    get_user_api_user_username_get,
    modify_user_api_user_username_put,
    remove_user_api_user_username_delete,
    reset_user_data_usage_api_user_username_reset_post,
    revoke_user_subscription_api_user_username_revoke_sub_post,
)
from marzban_client.models.user_modify import UserModify
from marzban_client.models.user_modify_inbounds import UserModifyInbounds
from marzban_client.models.user_modify_proxies import UserModifyProxies
from marzban_client.models.user_status import UserStatus

from . import router

PROXY_STATUS = {
    UserStatus.ACTIVE: "Активен ✅",
    UserStatus.DISABLED: "Отключён ❌",
    UserStatus.LIMITED: "Ограничен 🔒",
    UserStatus.EXPIRED: "Истёк ⏳",
}


class SetCustomNameForm(StatesGroup):
    proxy_id = State()
    user_id = State()
    current_page = State()
    name = State()


class ApiUserError(Exception):
    pass


@router.message(F.text == MainMenu.proxies, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.proxies))
@router.callback_query(Proxies.Callback.filter(F.action == ProxiesActions.show))
async def proxies(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: Proxies.Callback | UserPanel.Callback = None,
):
    if isinstance(callback_data, Proxies.Callback):
        user_id = (
            callback_data.user_id
            if callback_data and callback_data.user_id
            else user.id
        )
        page = callback_data.current_page if callback_data else 0
    else:
        user_id = user.id
        page = 0

    q = Proxy.filter(user_id=user_id).limit(11).offset(0 if page == 0 else page * 10)

    count = await q.count()
    if count < 1:
        text = "У вас пока нет активных подписок 😐😬"
        if isinstance(qmsg, CallbackQuery):
            return qmsg.answer(text, show_alert=True)
        return qmsg.answer(text)

    proxies = await q.prefetch_related("service").all()
    reply_markup = Proxies(
        proxies[:10],
        user_id=user_id,
        current_page=page,
        next_page=True if count > 10 else False,
        prev_page=True if page > 0 else False,
    ).as_markup()
    text = "🔵 Список ваших прокси 👇 (нажмите для управления)"
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=reply_markup,
            )
        return await qmsg.answer(
            text,
            reply_markup=reply_markup,
        )
    except exceptions.TelegramBadRequest as exc:
        await qmsg.answer("❌ Произошла ошибка!")
        raise exc


@router.message(F.text == MainMenu.cancel, StateFilter(SetCustomNameForm))
@router.message(Command("proxy"), SuperUserAccess())
@router.callback_query(Proxies.Callback.filter(F.action == ProxiesActions.show_proxy))
async def show_proxy(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: Proxies.Callback = None,
    state: FSMContext = None,
    command: CommandObject = None,
):
    if command:
        proxy_id, user_id, current_page = None, None, 0
        proxy = await Proxy.filter(username__iexact=command.args).first()
    else:
        proxy_id, user_id, current_page = None, None, None
        if (state is not None) and (await state.get_state() is not None):
            data = await state.get_data()
            proxy_id, user_id, current_page = data.values()
            text = "🌀 Отменено!"
            await state.clear()
            if isinstance(qmsg, CallbackQuery):
                await qmsg.answer(text)
            else:
                await qmsg.answer(text=text, reply_markup=ReplyKeyboardRemove())
        if callback_data:
            proxy_id, user_id, current_page = (
                proxy_id or callback_data.proxy_id,
                user_id or callback_data.user_id,
                current_page or callback_data.current_page,
            )
        proxy = await Proxy.filter(id=proxy_id).first()
    if not proxy:
        return await qmsg.answer("❌ Подписка не найдена!")

    if user_id:
        if (not user.super_user) and (user.id != user_id):
            return
        elif (user.super_user) and (proxy.user_id != user_id):
            await proxy.fetch_related("user")
            if proxy.user.parent_id != user.id:
                return
    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await qmsg.answer(
            f"❌ Ошибка получения данных. Попробуйте позже."
        )
        raise err
    await proxy.fetch_related("service")
    if not sv_proxy:
        proxy.status = ProxyStatus.disabled
        await proxy.save()
        if not user.super_user:
            return await qmsg.answer(
                f"❌ Прокси не найден на сервере! Пожалуйста, свяжитесь с поддержкой.",
                show_alert=True,
            )
        await proxy.refresh_from_db()
        await proxy.service.fetch_related("server")
        text = f"""
❌ Прокси не найден на сервере!

ID: {proxy.id}
Имя: {proxy.custom_name}
ID: {proxy.username}
Стоимость: {proxy.cost:,}

Сервис: {proxy.service.display_name}
        """
        # await proxy.fetch_related("reserve")
        reply_markup = ProxyPanel(
            proxy,
            user_id=user_id,
            current_page=current_page,
            renewable=False
            if proxy.service.one_time_only
            or proxy.service.is_test_service
            or not proxy.service.renewable
            else True,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=reply_markup)
        return await qmsg.answer(text, reply_markup=reply_markup)

    if proxy.status.value != sv_proxy.status.value:
        proxy.status = sv_proxy.status.value
        await proxy.save()
        await proxy.refresh_from_db()
    text = f"""
⭐️ ID: <code>{sv_proxy.username}</code> {f'({proxy.custom_name})' if proxy.custom_name else ''}
🌀 Статус: <b>{PROXY_STATUS.get(sv_proxy.status)}</b>
⏳ Истекает: <b>{helpers.hr_date(sv_proxy.expire) if sv_proxy.expire else '♾'}</b> {f'<i>({helpers.hr_time(sv_proxy.expire - dt.now().timestamp(), lang="ru")})</i>' if sv_proxy.expire and sv_proxy.status != UserStatus.EXPIRED else ''}
📊 Использовано: <b>{helpers.hr_size(sv_proxy.used_traffic, lang='en')}</b>
{f'🔋 Осталось: <b>{helpers.hr_size(sv_proxy.data_limit - sv_proxy.used_traffic ,lang="ru")}</b>' if sv_proxy.data_limit else ''}

🔑 Активные прокси: {', '.join([f'<b>{t.upper()}</b>' for t in [protocol for protocol in sv_proxy.inbounds.additional_properties]])}

🔗 Ссылка подключения: 
<code>{sv_proxy.subscription_url}</code>

❕ Сохраните ссылку для проверки статуса без бота, или нажмите:
<a href='{sv_proxy.subscription_url}'>🔺 Подключение</a>

💡 Для инструкции отправьте /help
"""
    if sv_proxy.status == UserStatus.ACTIVE:
        text += """

💡 Для отключения пользователей нажмите «Сменить пароль»

💡 Для получения ссылок и QR-кода нажмите кнопку ниже 👇
"""
    reply_markup = ProxyPanel(
        proxy,
        user_id=user_id,
        current_page=current_page,
        renewable=False
        if proxy.service.one_time_only
        or proxy.service.is_test_service
        or not proxy.service.renewable
        else True,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=reply_markup)
    return await qmsg.answer(text, reply_markup=reply_markup)


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.remove))
async def remove_proxy(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ Вы уверены, что хотите удалить подписку? Восстановление невозможно!",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.remove,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            f"❌ Ошибка получения данных. Попробуйте позже."
        )
        raise err

    try:
        if sv_proxy:
            await remove_user_api_user_username_delete.asyncio(
                username=sv_proxy.username, client=client
            )
        await proxy.delete()

        await query.answer("✅ Подписка удалена", show_alert=True)
        await proxies(
            query,
            user,
            callback_data=Proxies.Callback(
                user_id=callback_data.user_id,
                action=ProxiesActions.show,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой."
        )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_password)
)
async def reset_password(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    text = """
💡 در این بخش می‌توانید  دسترسی افراد متصل را قطع کنید!

Два способа:
1️⃣ Сменить пароль: меняет только пароль, пользователь может переподключиться по ссылке
2️⃣ Сменить ссылку: меняет ссылку подключения, старая перестанет работать

Для полного отключения используйте оба способа 🫡
"""
    await query.message.edit_text(
        text,
        reply_markup=ResetPassword(
            proxy_id=callback_data.proxy_id,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
        ).as_markup(),
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_uuid)
)
async def reset_uuid(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ Все подключённые пользователи будут отключены! Продолжить?",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.reset_uuid,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            f"❌ Ошибка получения данных. Попробуйте позже."
        )
        raise err
    try:
        await proxy.fetch_related("service")
        sv_proxy = await modify_user_api_user_username_put.asyncio(
            username=sv_proxy.username,
            client=client,
            json_body=UserModify(
                proxies=UserModifyProxies.from_dict(
                    {
                        protocol: proxy.service.create_proxy_protocols(protocol)
                        for protocol in sv_proxy.proxies.additional_properties
                    }
                )
            ),
        )

        await query.answer("✅ Пароль изменён", show_alert=True)

        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой."
        )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_subscription)
)
async def reset_subscription(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ Старая ссылка подключения перестанет работать! Продолжить?",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.reset_subscription,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            f"❌ Ошибка получения данных. Попробуйте позже."
        )
        raise err
    try:
        await revoke_user_subscription_api_user_username_revoke_sub_post.asyncio(
            username=sv_proxy.username,
            client=client,
        )

        await query.answer("✅ Ссылка подключения изменена", show_alert=True)

        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой."
        )


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links))
async def proxy_links(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ Ошибка получения данных. Попробуйте позже.",
            show_alert=True,
        )
    links = "\n\n".join([f"<code>{link}</code>" for link in sv_proxy.links])
    text = f"""
🔑 Активные прокси: {', '.join(f'<b>{protocol.upper()}</b>' for protocol in sv_proxy.inbounds.additional_properties)}:
    🔗 Ссылки подключения:
    
{links}

💡 Нажмите на ссылку чтобы скопировать 👆

💡 Для инструкции отправьте /help

📷 Для получения QR-кода нажмите кнопку ниже 👇
    """
    await query.message.edit_text(
        text,
        reply_markup=ProxyLinks(
            proxy=proxy, current_page=callback_data.current_page, user_id=user_id
        ).as_markup(),
    )


def gen_qr(text: str) -> qrcode.QRCode:
    qr = qrcode.QRCode(border=6)
    qr.add_data(text)
    return qr


async def generate_qr_code(
    message: Message, links: list[str], username: str
) -> BufferedInputFile:
    photos = list()
    for link in links:
        f = io.BytesIO()
        qr = gen_qr(link)
        qr.make_image().save(f)
        f.seek(0)
        photos.append(
            InputMediaPhoto(
                media=BufferedInputFile(
                    f.getvalue(), filename=f"generated_qr_code_{username}"
                ),
                caption=f"{link.split('://')[0].upper()} ({username})",
            )
        )
    return await message.answer_media_group(
        photos,
    )


async def generate_sub_qr_code(message: Message, link: str, username: str):
    f = io.BytesIO()
    qr = gen_qr(link)
    qr.make_image().save(f)
    f.seek(0)
    await message.answer_photo(
        photo=BufferedInputFile(f.getvalue(), filename=f"generated_qr_code_{username}"),
        caption=f"⛓️ Ссылка и QR-код подключения ({username})",
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links_allqr)
)
async def generate_qrcode_all(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ Ошибка получения данных. Попробуйте позже.",
            show_alert=True,
        )

    await query.answer("♻️ Генерирую QR-код, подождите...")

    await generate_qr_code(query.message, sv_proxy.links, username=proxy.username)


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links_subqr)
)
async def generate_qrcode_sub(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        client = Marzban.get_server(proxy.server_id)
        sv_proxy = await get_user_api_user_username_get.asyncio(
            username=proxy.username, client=client
        )
    except Exception as err:
        await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ Ошибка получения данных. Попробуйте позже.",
            show_alert=True,
        )

    await query.answer("♻️ Генерирую QR-код, подождите...")
    await generate_sub_qr_code(
        query.message, sv_proxy.subscription_url, username=proxy.username
    )


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.renew))
async def renew_proxy(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    q = Service.filter(
        server_id=proxy.server_id,
        renewable=True,
        one_time_only=False,
        server__is_enabled=True,
        is_test_service=False,
    )
    if False:
            pass
    elif True:
            pass

    available_services = await q.all()
    if not available_services:
        text = """
❗️ Продление недоступно для этой подписки
Пожалуйста, свяжитесь с поддержкой.
    """
        return await query.answer(text, show_alert=True)

    text = """
♻️ Здесь можно продлить подписку!

Для продления выберите тариф 👇:
    """
    await query.message.edit_text(
        text,
        reply_markup=RenewSelectService(
            proxy=proxy,
            services=available_services,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
        ).as_markup(),
    )


@router.callback_query(RenewSelectService.Callback.filter())
async def renew_proxy_service(
    query: CallbackQuery, user: User, callback_data: RenewSelectService.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    text = """
✅ Выберите способ продления 👇👇

➖ Мгновенное: новый период начинается сейчас

➖ Резерв: активируется после окончания текущего

Выберите способ продления 👇👇
    """
    await query.message.edit_text(
        text,
        reply_markup=RenewSelectMethod(
            proxy=proxy,
            service_id=callback_data.service_id,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
        ).as_markup(),
    )


@router.callback_query(RenewSelectMethod.Callback.filter(F.method == RenewMethods.now))
async def renew_proxy_now(
    query: CallbackQuery, user: User, callback_data: RenewSelectMethod.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (not user.super_user) and (user.id != user_id):
        return
    elif (user.super_user) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    service = await Service.filter(
        id=callback_data.service_id,
        renewable=True,
        server__is_enabled=True,
        is_test_service=False,
    ).first()
    if not service:
        return await query.answer(
            "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой.",
            show_alert=True,
        )

    price = service.get_price()
        #         price = price
        #     await user.fetch_related("setting")
        #     if user.setting and (discount_percentage := user.setting.discount_percentage):
        #         price = service.get_price(discount_percent=discount_percentage)
        #     else:
        #         price = price

    balance = await user.get_balance()

    if callback_data.confirmed:
        if balance < price:
            return await query.answer(
                "❌ Недостаточно средств!", show_alert=True
            )
        try:
            async with in_transaction():
                await Invoice.create(
                    amount=price,
                    type=Invoice.Type.renew,
                    is_paid=True,
                    proxy=proxy,
                    user=user,
                )
                client = Marzban.get_server(service.server_id)
                updated_user = UserModify(
                    expire=helpers.get_expire_timestamp(service.expire_duration),
                    data_limit=service.data_limit,
                )
                sv_proxy = (
                    await reset_user_data_usage_api_user_username_reset_post.asyncio(
                        username=proxy.username, client=client
                    )
                )
                if not sv_proxy:
                    raise ApiUserError("reset data usage didn't return anything!")
                updated_user = UserModify(
                    expire=helpers.get_expire_timestamp(service.expire_duration),
                    data_limit=service.data_limit,
                )
                if service.id != proxy.service_id:
                    proxy.service_id = service.id
                    updated_user.inbounds = UserModifyInbounds.from_dict(
                        service.inbounds
                    )
                    proxies = {}
                    for protocol in service.inbounds:
                        if protocol in sv_proxy.proxies:
                            proxies.update({protocol: sv_proxy.proxies.get(protocol)})
                        else:
                            proxies.update(
                                {protocol: service.create_proxy_protocols(protocol)}
                            )
                    updated_user.proxies = UserModifyProxies.from_dict(proxies)
                sv_proxy = await modify_user_api_user_username_put.asyncio(
                    username=proxy.username,
                    json_body=updated_user,
                    client=client,
                )
                proxy.status = sv_proxy.status.value
                await proxy.save()
                if not sv_proxy:
                    raise ApiUserError("modify user didn't return anything!")
                await query.answer("✅ Подписка успешно продлена!", show_alert=True)
                return await show_proxy(
                    query,
                    user,
                    callback_data=Proxies.Callback(
                        proxy_id=proxy.id,
                        user_id=callback_data.user_id,
                        action=ProxiesActions.show_proxy,
                        current_page=callback_data.current_page,
                    ),
                )
        except Exception as err:
            await query.answer(
                "❌ Произошла ошибка при выполнении операции! Пожалуйста, свяжитесь с поддержкой.",
                show_alert=True,
            )
            raise err

    text = f"""
🌀 Активировать тариф для этого прокси?

💎 {service.name}
🕐 Длительность: {helpers.hr_time(service.expire_duration, lang="ru") if service.expire_duration else '♾'}
🖥 Трафик: {helpers.hr_size(service.data_limit, lang="ru") if service.data_limit else '♾'}
💰 قیمت: {price:,} руб.
"""
    if price < price:
        text += f"""
~~~~~~~~~~~~~~~~~~~~~~~~
🔥 Ваша скидка: <code>{discount_percentage}</code>%
💰 Со скидкой: <code>{price:,}</code> руб.
~~~~~~~~~~~~~~~~~~~~~~~~
"""
    text += f"""
🏦 Ваш баланс: {balance:,} руб.
💵 К оплате: {price:,} руб.
~~~~~~~~~~~~~~~~~~~~~~~~
    """
    if balance >= price:
        text += "🛍 Для активации нажмите кнопку 👇"
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmRenew(
                proxy=proxy,
                service_id=service.id,
                method=RenewMethods.now,
                user_id=callback_data.user_id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )
    text += "😞 Недостаточно средств! Пополните баланс 👇"
    return await query.message.edit_text(
        text,
        reply_markup=ConfirmRenew(
            proxy=proxy,
            service_id=service.id,
            method=RenewMethods.now,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
            has_balance=False,
        ).as_markup(),
    )
