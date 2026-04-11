import uuid
import config
from aiogram import F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from tortoise.transactions import in_transaction

from app.keyboards.base import CancelUserForm, MainMenu
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.keyboards.user.payment import (
    ChargeMethods,
    ChargePanel,
    SelectPayAmount,
    PayRoboUrl,
)
from app.models.user import Transaction, User, RobokassaPayment
from app.utils.filters import IsJoinedToChannel
from app.utils.settings import Settings

from . import router

class SelectCustomAmountForm(StatesGroup):
    method = State()
    amount = State()

# --- Навигация и отмена ---

@router.message(
    (F.text == MainMenu.back) | (F.text == MainMenu.cancel),
    StateFilter(SelectCustomAmountForm),
)
async def cancel_payment(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌀 Операция отменена.", reply_markup=ReplyKeyboardRemove())

# --- Вход в меню оплаты ---

@router.message(F.text == MainMenu.charge, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.charge))
async def charge(qmsg: Message | CallbackQuery, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        
    text = """
💳 <b>Пополнение баланса</b>

Минимальная сумма пополнения: <b>100 руб.</b>
Выберите удобный способ оплаты или введите сумму вручную.
    """
    if isinstance(qmsg, Message):
        return await qmsg.answer(text, reply_markup=ChargePanel({}).as_markup())
    return await qmsg.message.edit_text(text, reply_markup=ChargePanel({}).as_markup())

# --- Выбор суммы ---

@router.callback_query(ChargePanel.Callback.filter(F.method == ChargeMethods.robokassa))
async def robokassa_select_amount(query: CallbackQuery, user: User):
    text = "💰 <b>Выберите сумму для зачисления:</b>"
    await query.message.edit_text(
        text, reply_markup=SelectPayAmount(method=ChargeMethods.robokassa).as_markup()
    )

@router.callback_query(SelectPayAmount.Callback.filter(F.amount == 0))
async def enter_custom_amount(query: CallbackQuery, user: User, callback_data: SelectPayAmount.Callback, state: FSMContext):
    await state.set_state(SelectCustomAmountForm.amount)
    await state.set_data({"method": callback_data.method})
    await query.message.answer(
        "💴 Введите сумму (только число, в рублях):",
        reply_markup=CancelUserForm(cancel=True).as_markup(resize_keyboard=True)
    )

@router.message(SelectCustomAmountForm.amount)
async def get_custom_amount(message: Message, user: User, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply("❌ Пожалуйста, введите числовое значение.")

    if amount < 100:
        return await message.reply("❌ Минимальная сумма пополнения — 100 руб.")

    data = await state.get_data()
    method = data.get("method")
    await state.clear()
    
    callback_data = SelectPayAmount.Callback(amount=amount, free=0, method=method)
    return await robokassa_pay_logic(message, user, callback_data)

# --- Логика Robokassa ---

@router.callback_query(SelectPayAmount.Callback.filter(F.method == ChargeMethods.robokassa))
async def robokassa_pay_logic(qmsg: CallbackQuery | Message, user: User, callback_data: SelectPayAmount.Callback):
    try:
        async with in_transaction():
            # Исправлено: используем PaymentType вместо Type и Status.waiting
            transaction = await Transaction.create(
                user=user,
                amount=callback_data.amount,
                type=Transaction.PaymentType.robokassa,
                status=Transaction.Status.waiting
            )
            
            # Создаем запись в деталях платежа
            await RobokassaPayment.create(transaction=transaction)
        
        # Подготовка ссылки (пока тестовая)
        merchant_login = "TEST_LOGIN" 
        payment_url = f"https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin={merchant_login}&OutSum={callback_data.amount}&InvId={transaction.id}&Description=VPN_Balance"
        
        text = f"""
✅ <b>Счет успешно сформирован!</b>

💰 Сумма к оплате: <b>{callback_data.amount:,} руб.</b>
🆔 Номер заказа: <code>{transaction.id}</code>

Нажмите кнопку ниже для перехода на страницу оплаты.
        """
        
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=PayRoboUrl(url=payment_url).as_markup())
        return await qmsg.answer(text, reply_markup=PayRoboUrl(url=payment_url).as_markup())
        
    except Exception as e:
        print(f"CRITICAL PAYMENT ERROR: {e}")
        error_text = "❌ Ошибка при создании счета. Попробуйте еще раз."
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(error_text, show_alert=True)
        else:
            await qmsg.answer(error_text)
        raise e

@router.callback_query(F.data == "check_payment_status")
async def check_status(query: CallbackQuery):
    await query.answer("🔄 Платеж проверяется автоматически. Баланс обновится после подтверждения системой.", show_alert=True)
