from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import KeyboardButton

import config

class MainMenu(ReplyKeyboardBuilder):
    proxies = "💎 Мои подписки"
    purchase = "🚀 Купить подписку"
    account = "👤 Мой аккаунт"
    charge = "💳 Пополнить баланс"
    help = "📝 Инструкция"
    support = "✅ Поддержка"
    faq = "❓ Часто задаваемые вопросы"
    back = "🔙 Назад"
    cancel = "🚫 Отмена"
    main_menu = "📱 Главное меню"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text=self.purchase)
        self.button(text=self.proxies)
        self.button(text=self.account)
        self.button(text=self.charge)
        self.button(text=self.help)
        self.button(text=self.support)
        self.adjust(1, 3, 2)


class CancelUserForm(ReplyKeyboardBuilder):
    def __init__(self, cancel: bool = False, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if cancel:
            self.button(text=MainMenu.cancel)
        else:
            self.button(text=MainMenu.back)
        self.button(text=MainMenu.main_menu)
        self.adjust(1, 1)


class ForceJoin(InlineKeyboardBuilder):
    check = "✅ Проверить подписку"

    class Callback(CallbackData, prefix="check_force_join"):
        pass

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for _, username in config.FORCE_JOIN_CHATS.items():
            self.button(text=f"🆔 @{username}", url=f"https://t.me/{username}")
        self.button(text=self.check, callback_data=self.Callback())
        self.adjust(1, 1)
