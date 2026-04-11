from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from app.keyboards.user.account import UserPanel, UserPanelAction

class ChargeMethods(str, Enum):
    robokassa = "robokassa"
    # Другие методы можно добавить сюда позже (например, lavas или cryptomus)

class ChargePanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="payment"):
        method: ChargeMethods

    def __init__(self, settings: dict[str, bool], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Для тестов выводим Robokassa всегда, либо можно привязать к PAYMENT:CRYPTO в .env
        self.button(
            text="💳 Банковская карта (Robokassa)",
            callback_data=self.Callback(method=ChargeMethods.robokassa),
        )
        self.adjust(1)


class SelectPayAmount(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="payslctam"):
        amount: int
        free: int = 0
        method: ChargeMethods

    def __init__(self, method: ChargeMethods, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Установили адекватные суммы для пополнения
        amount_list = [
            100,
            250,
            500,
            1000,
            2500,
            5000,
        ]
        for amount in amount_list:
            free = int(
                0
                if (not config.PAYMENTS_DISCOUNT_ON)
                or (amount < config.PAYMENTS_DISCOUNT_ON)
                else amount * (config.PAYMENTS_DISCOUNT_ON_PERCENT / 100)
            )
            self.button(
                text=f"{amount:,} руб."
                if not free
                else f"{amount:,} руб. (+{free:,} 🔥)",
                callback_data=self.Callback(amount=amount, free=free, method=method),
            )
        
        self.button(
            text="✍️ Своя сумма",
            callback_data=self.Callback(amount=0, method=method),
        )

        self.button(
            text="🔙 Назад",
            callback_data=UserPanel.Callback(action=UserPanelAction.charge),
        )
        self.adjust(2, 2, 2, 1, 1)


class PayRoboUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="💳 Оплатить счет", url=url)
