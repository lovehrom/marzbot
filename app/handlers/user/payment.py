import uuid
import config
from aiogram import F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from tortoise.transactions import in_transaction

from app.keyboards.base import CancelUserForm, MainMenu
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.keyboards.user.payment import (
    ChargeMethods,
    ChargePanel,
    SelectPayAmount,
    PayYooUrl,
)
from app.models.user import Transaction, User, YookassaPayment
from app.utils.filters import IsJoinedToChannel

from . import router


class SelectCustomAmountForm(StatesGroup):
    method = State()
    amount = State()


@router.message(
    (F.text == MainMenu.back) | (F.text == MainMenu.cancel),
    StateFilter(SelectCustomAmountForm),
)
async def cancel_payment(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == MainMenu.charge, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.charge))
async def charge(qmsg: Message | CallbackQuery, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    text = (
        "Пополнение баланса\n\n"
        "Минимальная сумма пополнения: 100 руб.\n"
        "Выберите удобный способ оплаты или введите сумму вручную."
    )
    if isinstance(qmsg, Message):
        return await qmsg.answer(text, reply_markup=ChargePanel({}).as_markup())
    return await qmsg.message.edit_text(text, reply_markup=ChargePanel({}).as_markup())


@router.callback_query(ChargePanel.Callback.filter(F.method == ChargeMethods.yookassa))
async def yookassa_select_amount(query: CallbackQuery, user: User):
    text = "Выберите сумму для зачисления:"
    await query.message.edit_text(
        text, reply_markup=SelectPayAmount(method=ChargeMethods.yookassa).as_markup()
    )


@router.callback_query(SelectPayAmount.Callback.filter(F.amount == 0))
async def enter_custom_amount(query: CallbackQuery, user: User, callback_data: SelectPayAmount.Callback, state: FSMContext):
    await state.set_state(SelectCustomAmountForm.amount)
    await state.set_data({"method": callback_data.method})
    await query.message.answer(
        "Введите сумму (только число, в рублях):",
        reply_markup=CancelUserForm(cancel=True).as_markup(resize_keyboard=True)
    )


@router.message(SelectCustomAmountForm.amount)
async def get_custom_amount(message: Message, user: User, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply("Пожалуйста, введите числовое значение.")
    if amount < 100:
        return await message.reply("Минимальная сумма пополнения - 100 руб.")
    data = await state.get_data()
    method = data.get("method")
    await state.clear()
    callback_data = SelectPayAmount.Callback(amount=amount, free=0, method=method)
    return await yookassa_pay_logic(message, user, callback_data)


@router.callback_query(SelectPayAmount.Callback.filter(F.method == ChargeMethods.yookassa))
async def yookassa_pay_logic(qmsg: CallbackQuery | Message, user: User, callback_data: SelectPayAmount.Callback):
    try:
        from payment_clients.yookassa import YooKassaClient

        yookassa = YooKassaClient(
            shop_id=config.YOOKASSA_SHOP_ID,
            secret_key=config.YOOKASSA_SECRET_KEY,
            is_test=config.IS_TEST,
        )

        async with in_transaction():
            transaction = await Transaction.create(
                user=user,
                amount=callback_data.amount,
                type=Transaction.PaymentType.yookassa,
                status=Transaction.Status.waiting,
            )
            bot_link = f"https://t.me/{config.BOT_USERNAME}"
            payment = await yookassa.create_payment(
                amount_rub=callback_data.amount,
                description=f"Пополнение баланса — заказ #{transaction.id}",
                return_url=bot_link,
                metadata={"transaction_id": str(transaction.id)},
            )
            payment_id = payment.get("id", "")
            confirmation_url = ""
            if payment.get("confirmation"):
                confirmation_url = payment["confirmation"].get("confirmation_url", "")
            status = payment.get("status", "")

            yookassa_record = await YookassaPayment.create(
                transaction=transaction,
                yookassa_payment_id=payment_id,
            )
            if status == "succeeded":
                transaction.status = Transaction.Status.finished
                transaction.amount_paid = callback_data.amount
                await transaction.save()
                yookassa_record.status = "succeeded"
                await yookassa_record.save()

        text = (
            f"Счёт успешно сформирован!\n\n"
            f"Сумма к оплате: {callback_data.amount:,} руб.\n"
            f"Номер заказа: {transaction.id}\n\n"
            f"Нажмите кнопку ниже для перехода на страницу оплаты."
        )
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=PayYooUrl(url=confirmation_url, inv_id=transaction.id).as_markup(),
            )
        return await qmsg.answer(
            text,
            reply_markup=PayYooUrl(url=confirmation_url, inv_id=transaction.id).as_markup(),
        )
    except Exception as e:
        from app.logger import get_logger
        get_logger("payment").error(f"CRITICAL PAYMENT ERROR: {e}")
        error_text = "Ошибка при создании счёта. Попробуйте ещё раз."
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(error_text, show_alert=True)
        else:
            await qmsg.answer(error_text)
        raise e


@router.callback_query(F.data.startswith("check_yoo_payment:"))
async def check_yookassa_payment(query: CallbackQuery, user: User):
    inv_id = int(query.data.split(":")[1])
    transaction = await Transaction.get_or_none(id=inv_id, user=user)
    if not transaction:
        return await query.answer("Платёж не найден", show_alert=True)
    if transaction.status == Transaction.Status.finished:
        return await query.answer("Этот платёж уже обработан!", show_alert=True)
    from datetime import datetime as dt, timedelta as td
    if transaction.created_at < dt.utcnow() - td(hours=24):
        transaction.status = Transaction.Status.canceled
        await transaction.save()
        return await query.answer("Срок действия счёта истёк. Создайте новый.", show_alert=True)
    from payment_clients.yookassa import YooKassaClient
    yookassa = YooKassaClient(
        shop_id=config.YOOKASSA_SHOP_ID,
        secret_key=config.YOOKASSA_SECRET_KEY,
        is_test=config.IS_TEST,
    )
    bot_link = f"https://t.me/{config.BOT_USERNAME}"
    payment = await yookassa.create_payment(
        amount_rub=transaction.amount,
        description=f"Пополнение баланса — заказ #{transaction.id}",
        return_url=bot_link,
        metadata={"transaction_id": str(transaction.id)},
    )
    confirmation_url = ""
    if payment.get("confirmation"):
        confirmation_url = payment["confirmation"].get("confirmation_url", "")
    yoo_record = await YookassaPayment.get_or_none(transaction=transaction)
    if yoo_record:
        yoo_record.yookassa_payment_id = payment.get("id", yoo_record.yookassa_payment_id)
        await yoo_record.save()
    await query.answer("Ссылка обновлена!", show_alert=False)
    text = (
        f"Повторная ссылка на оплату\n\n"
        f"Сумма: {transaction.amount:,} руб.\n"
        f"Заказ: {transaction.id}\n\n"
        f"Если оплата прошла, но баланс не обновился — подождите пару минут."
    )
    await query.message.edit_text(
        text,
        reply_markup=PayYooUrl(url=confirmation_url, inv_id=transaction.id).as_markup(),
    )
