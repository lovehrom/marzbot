from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.user import account
from app.models.proxy import Proxy, ProxyStatus
from app.models.service import Service

PROXY_STATUS = {
    ProxyStatus.active: "✅",
    ProxyStatus.disabled: "❌",
    ProxyStatus.limited: "🔒",
    ProxyStatus.expired: "⏳",
}


class ProxiesActions(str, Enum):
    show = "show"
    show_proxy = "show_proxy"
    cycle_sort = "cycle_sort"


class Proxies(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prxss"):
        proxy_id: int = 0
        user_id: int | None = None
        parent_id: int | None = None
        action: ProxiesActions
        current_page: int = 0

    def __init__(
        self,
        proxies: list[Proxy],
        user_id: int | None = None,
        parent_id: int | None = None,
        current_page: int = 0,
        next_page: bool = False,
        prev_page: bool = False,
        *args,
        **kwargs,
    ) -> None:
        """proxies should have 'proxy.server' prefetched"""
        super().__init__(*args, **kwargs)
        for proxy in proxies:
            self.button(
                text=f"{PROXY_STATUS.get(proxy.status)} {proxy.custom_name or proxy.service.display_name} ({proxy.username})",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    action=ProxiesActions.show_proxy,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ Назад",
                callback_data=self.Callback(
                    user_id=user_id,
                    parent_id=parent_id,
                    action=ProxiesActions.show,
                    current_page=current_page - 1,
                ),
            )
        if next_page:
            self.button(
                text="➡️ Далее",
                callback_data=self.Callback(
                    user_id=user_id,
                    parent_id=parent_id,
                    action=ProxiesActions.show,
                    current_page=current_page + 1,
                ),
            )
        self.adjust(*[1 for _ in range(11)], 2)


class ProxyPanelActions(str, Enum):
    links = "links"
    reset_password = "reset_password"
    reset_uuid = "reset_uuid"
    reset_subscription = "reset_subscription"
    renew = "renew"
    set_name = "set_name"
    remove = "remove"
    links_allqr = "allqr"
    links_subqr = "subqr"


class ProxyPanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prxpnl"):
        proxy_id: int
        user_id: int | None = None
        current_page: int = 0
        action: ProxyPanelActions
        confirmed: bool = False

    def __init__(
        self,
        proxy: Proxy,
        user_id: int | None = None,
        current_page: int = 0,
        renewable: bool = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if proxy.status == ProxyStatus.active:
            self.button(
                text="🔗 Получить ссылки",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.links,
                ),
            )
            self.button(
                text="🔑 Сменить пароль",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.reset_password,
                ),
            )
        else:
            self.button(
                text="🗑 Удалить 📍 Мои подписки",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.remove,
                ),
            )
        if renewable:
            self.button(
                text="♻️ Продлить",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.renew,
                ),
            )
        self.button(
            text="🔙 Назад",
            callback_data=Proxies.Callback(
                user_id=user_id,
                action=ProxiesActions.show,
                current_page=current_page,
            ),
        )
        if proxy.status == ProxyStatus.active:
            self.adjust(1, 2, 1, 1)
        else:
            self.adjust(1, 1, 1)


class ResetPassword(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy_id: int,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="🔑 Сменить пароль",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy_id,
                user_id=user_id,
                current_page=current_page,
                action=ProxyPanelActions.reset_uuid,
            ),
        )
        self.button(
            text="🔑 Сменить ссылку",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy_id,
                user_id=user_id,
                current_page=current_page,
                action=ProxyPanelActions.reset_subscription,
            ),
        )
        self.button(
            text=f"🔙 Отмена",
            callback_data=Proxies.Callback(
                proxy_id=proxy_id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1)


class ConfirmProxyPanel(InlineKeyboardBuilder):
    def __init__(
        self,
        action: ProxyPanelActions,
        proxy_id: int,
        user_id: int = None,
        current_page: int = 0,
    ) -> None:
        super().__init__()
        self.button(
            text="⚠️ Подтвердить",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy_id,
                user_id=user_id,
                current_page=current_page,
                action=action,
                confirmed=True,
            ),
        )

        self.button(
            text=f"🔙 Отмена",
            callback_data=Proxies.Callback(
                proxy_id=proxy_id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1)


class ProxyLinks(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy: Proxy,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="📱 Qr Code",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                current_page=current_page,
                action=ProxyPanelActions.links_allqr,
            ),
        )
        self.button(
            text="📱 QR-код",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                current_page=current_page,
                action=ProxyPanelActions.links_subqr,
            ),
        )
        self.button(
            text=f"🔙 Назад",
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1, 1)


class RenewSelectService(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="rnwsrvs"):
        proxy_id: int
        service_id: int
        user_id: int | None = None
        current_page: int = 0

    def __init__(
        self,
        proxy: Proxy,
        services: list[Service],
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=service.display_name,
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    service_id=service.id,
                    user_id=user_id,
                    current_page=current_page,
                ),
            )
        self.button(
            text=f"🔙 Назад",
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1, 1, 1)


class RenewMethods(str, Enum):
    now = "now"


class RenewSelectMethod(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="rnwmethod"):
        proxy_id: int
        service_id: int
        user_id: int | None = None
        current_page: int = 0
        method: RenewMethods
        confirmed: bool = False

    def __init__(
        self,
        proxy: Proxy,
        service_id: int,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="♻️ Мгновенное продление",
            callback_data=self.Callback(
                proxy_id=proxy.id,
                service_id=service_id,
                user_id=user_id,
                current_page=current_page,
                method=RenewMethods.now,
            ),
        )
        self.button(
            text=f"🔙 Назад",
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1, 1)


class ConfirmRenew(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy: Proxy,
        service_id: int,
        method: RenewMethods,
        user_id: int | None = None,
        current_page: int = 0,
        has_balance: bool = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if has_balance:
            self.button(
                text="✅ Активировать",
                callback_data=RenewSelectMethod.Callback(
                    proxy_id=proxy.id,
                    service_id=service_id,
                    user_id=user_id,
                    current_page=current_page,
                    method=method,
                    confirmed=True,
                ),
            )
        else:
            self.button(
                text="💳 Пополнить баланс",
                callback_data=account.UserPanel.Callback(
                    action=account.UserPanelAction.charge
                ),
            )
        self.button(
            text="🔙 Назад",
            callback_data=RenewSelectService.Callback(
                proxy_id=proxy.id,
                service_id=service_id,
                user_id=user_id,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1)
