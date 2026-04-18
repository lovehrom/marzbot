from aiogram import F
from aiogram.types import CallbackQuery, Message

from app.keyboards.base import MainMenu
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.models.user import User
from app.utils.filters import IsJoinedToChannel

from . import router

ACCOUNT_TYPE = {
    "user": "Пользователь",
    "reseller": "Реселлер",
    "admin": "Админ",
    "super_user": "Суперадмин",
}


@router.message(F.text == MainMenu.account, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.show))
async def account(qmsg: Message | CallbackQuery, user: User):
    balance = await user.get_balance()
    text = f"""
✅ ✅ Информация о вашем аккаунте::

💬 👤 Имя пользователя: {f'@{user.username}' if user.username else '➖'}
📲 🆔 Ваш ID: <code>{user.id}</code>
💲 💰 Баланс: <b>{balance:,}</b> руб.
🔋 🔋 Активных сервисов: <b>{await user.proxies.all().count()}</b>
"""

    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text + "‌‌",
            reply_markup=UserPanel(user=user).as_markup(),
        )
    await qmsg.answer(text + "‌‌", reply_markup=UserPanel(user=user).as_markup())
