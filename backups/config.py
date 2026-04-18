import os
import re

from dotenv import load_dotenv

if DOTENV_PATH := os.getenv("PYTHON_DOTENV_FILE"):
    from decouple import Config, RepositoryEnv

    load_dotenv(DOTENV_PATH)
    config = Config(RepositoryEnv(DOTENV_PATH))
else:
    from decouple import config

    load_dotenv()

from app.logger import get_logger

log = get_logger(__name__)


LOG_LEVEL = config("LOG_LEVEL", default="info")

BOT_TOKEN = config("BOT_TOKEN")

SETTINGS = {
    "BOT:ACCESS_ONLY": config("SETTINGS:BOT:ACCESS_ONLY", default=False, cast=bool),
    "PAYMENT:CRYPTO": config("SETTINGS:PAYMENT:CRYPTO", default=True, cast=bool),
}

# socks5h://127.0.0.1:2080
PROXY = config("PROXY", None)

PARSE_MODE = config("PARSE_MODE", default="HTML")
DATABASE_URL = config(
    "DATABASE_URL", default="sqlite://db.sqlite3"
)  # example: 'mysql://user:pass@localhost:3306/db'
# exmaple: 'sqlite:///marzbot.db'

if DATABASE_URL is None:
    raise ValueError("'DATABASE_URL' environment variable has to be set!")

BOT_USERNAME = config("BOT_USERNAME", default="marzdemobot")

DEFAULT_USERNAME_PREFIX = config("DEFAULT_USERNAME_PREFIX", default="Marzdemo")

if not re.match(r"^(?!_)[A-Za-z0-9_]+$", DEFAULT_USERNAME_PREFIX):
    raise ValueError(
        "DEFAULT_USERNAME_PREFIX must be less than 20 characters and [0-9A-Za-z] and underscores in between"
    )

# --- БЛОК НАСТРОЕК ROBOKASSA (НОВОЕ) ---
ROBOKASSA_LOGIN = config("ROBOKASSA_LOGIN", default="твой_логин_магазина")
ROBOKASSA_PASS_1 = config("ROBOKASSA_PASS_1", default="твой_пароль_1")
ROBOKASSA_PASS_2 = config("ROBOKASSA_PASS_2", default="твой_пароль_2")
IS_TEST = config("IS_TEST", default=1, cast=int)
# --------------------------------------

PAYMENTS_DISCOUNT_ON = config(
    "PAYMENTS_DISCOUNT_ON", default=400000, cast=int
)  # payments higher than this amount will have a discount, set 0 for no discount
PAYMENTS_DISCOUNT_ON_PERCENT = config(
    "PAYMENTS_DISCOUNT_ON_PERCENT", default=6, cast=int
)  # default: 6 percent free credit for payments more than 400,000t


if PAYMENTS_DISCOUNT_ON:
    FREE_CREDIT_ON_TEXT = f"🔥 Все платежи свыше {PAYMENTS_DISCOUNT_ON:,} руб. получают бонус {PAYMENTS_DISCOUNT_ON_PERCENT}% на баланс😉"
else:
    FREE_CREDIT_ON_TEXT = ""

NP_API_URL = config("NP_API_URL", default="https://api.nowpayments.io/v1")
NP_API_KEY = config("NP_API_KEY", default=None)

NP_IPN_CALLBACK_URL = config(
    "NP_IPN_CALLBACK_URL", default="https://rayapardazapi.ir/cryptogw"
)

NP_IPN_SECRET_KEY = config("NP_IPN_SECRET_KEY", default=None)
NP_SUCCESS_URL = config("NP_SUCCESS_URL", default=None)
NP_CANCEL_URL = config("NP_CANCEL_URL", default=None)

TORTOISE_ORM = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "models": {
            "models": [  # put rest of the models as so in the list
                "app.models.user",
                "app.models.server",
                "app.models.service",
                "app.models.proxy",
                "aerich.models",
            ],
            "default_connection": "default",
        },
    },
}

REDIS_HOST = config("REDIS_HOST", default="redis")
REDIS_PORT = config("REDIS_PORT", default=6379)
REDIS_DB = config("REDIS_DB", default=0)


WEBAPP_HOST = config("WEBAPP_HOST", default="127.0.0.1")
WEBAPP_PORT = config("WEBAPP_PORT", default=3333)


FORCE_JOIN_CHATS = {
    chat.split("@")[0]: chat.split("@")[1]
    for chat in config("FORCE_JOIN_CHATS", default="-1001892840605@marzdemo").split(
        "\n"
    )
    if chat
}


def generate_help(text: str) -> str:
    if not text:
        return ""
    return f"~~~~~~~~~~~~~~~~~~~~~~~~\n{text}\n~~~~~~~~~~~~~~~~~~~~~~~~"


_START_TEXT = f"""
👋 Привет!
Добро пожаловать в бота😉

С нашими VPN-сервисами ты всегда будешь на связи в любое время и с любого устройства🌝

💡 Чтобы получать новости, статус серверов и ежедневные бонусы, подписывайся на наш канал:
🆔 @marzdemo

🔍 Если хочешь узнать больше, нажми кнопку <b>«📝 Инструкция»</b>
"""


_FORCE_JOIN_TEXT = f"""
♻️ Для использования бота необходимо быть участником нашего канала.

Подпишись на канал ниже, а затем нажми кнопку «✅ Проверить подписку»👇

🆔 @marzdemo
"""

_SUPPORT_TEXT = """
✋ Добро пожаловать в службу поддержки!

Прежде чем задать вопрос, пожалуйста, изучите раздел «📝 Инструкция», скорее всего, ответ уже там😉

⁉️ Не нашли ответ? Ничего страшного, вы можете связаться с нами по контактам ниже👇

🆔 @govfvck1

💡 Пожалуйста, проявите немного терпения после отправки сообщения. Мы отвечаем всем в порядке очереди🙏
"""

_HELP_TEXT = """
Добро пожаловать в руководство пользователя!

Вы можете пополнить баланс несколькими способами через кнопку «💳 Пополнить баланс».
😃 Инструкции по каждому методу оплаты находятся там же!

После пополнения нажмите «🚀 Купить подписку», выберите подходящий тариф и получите его моментально. Всё очень просто😇

Чтобы посмотреть свои активные подписки, нажмите «💎 Мои подписки»🙃
Здесь отображается весь список. Нажмите на любую подписку, чтобы войти в её настройки и получить данные для подключения😉

Узнать свой баланс можно, нажав на кнопку «👤 Мой аккаунт»🤓

Также вы можете получать бонусный баланс, приглашая друзей в бота😋

💡 Ответы на частые вопросы мы собрали в нашем канале:
<a href='https://t.me'>❔ Частые вопросы</a>

Если вы не нашли ответ здесь или в частых вопросах, смело жмите кнопку «✅ Поддержка». Мы с радостью поможем решить любую проблему!🤗

📞 Если вы реселлер и хотите покупать оптом, свяжитесь с поддержкой для повышения уровня аккаунта и активации специальных функций🤫
"""

_CRYPTO_PAYMENT_HELP = """
❗️ Если вы не знаете, как оплачивать криптовалютой, обязательно посмотрите нашу инструкцию:
<a href='https://t.me/'>❔ Как пополнить баланс криптовалютой</a>
"""


START_TEXT = config("START_TEXT", default=_START_TEXT)
FORCE_JOIN_TEXT = config("FORCE_JOIN_TEXT", default=_FORCE_JOIN_TEXT)
SUPPORT_TEXT = config("SUPPORT_TEXT", default=_SUPPORT_TEXT)
HELP_TEXT = config("HELP_TEXT", default=_HELP_TEXT)

CRYPTO_PAYMENT_HELP = generate_help(
    config("CRYPTO_PAYMENT_HELP", default=_CRYPTO_PAYMENT_HELP)
)
