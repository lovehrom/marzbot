from enum import Enum
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.models.service import Service

# Определяем экшены здесь, чтобы не зависеть от импортов и не ловить круговые ошибки
class ServicesActions(str, Enum):
    show = "show"
    show_service = "show_service"
    purchase = "purchase"

class Services(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="servicss"):
        service_id: int = 0
        action: ServicesActions

    def __init__(self, services: list[Service], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=service.display_name,
                callback_data=self.Callback(
                    service_id=service.id, action=ServicesActions.show_service
                )
            )
        self.adjust(1)

class PurchaseService(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prchssrv"):
        service_id: int = 0

    def __init__(self, service: Service, has_balance: bool = True, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if has_balance:
            self.button(
                text="🛒 Купить подписку", 
                callback_data=self.Callback(service_id=service.id)
            )
        else:
            # МАКСИМАЛЬНО ТОЧНЫЙ КОЛБЭК: префикс 'account' и экшен 'charge'
            # Это именно то, что бот ждет в account.py
            self.button(
                text="💳 Пополнить баланс", 
                callback_data="account:charge" 
            )
        
        self.button(
            text="⬅️ Назад", 
            callback_data=Services.Callback(action=ServicesActions.show).pack()
        )
        self.adjust(1)

