import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8690392643:AAHsZFFvcjb91nBtYDIfxR7F3n3YHXlOD4s"
ADMIN_ID = 6965500581  # Вставь сюда свой Telegram ID (узнай у @userinfobot)
CARD_NUMBER = "2200 1536 1202 1924"  # Номер карты Альфа Банк
CARD_NAME = "Альфа Банк"
# ====================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранилище подписок и заявок
subscriptions = {}  # user_id: expire_date
pending_payments = {}  # user_id: {"tariff": ..., "days": ..., "price": ...}

TARIFFS = {
    "7": {"name": "7 дней", "days": 7, "price": 799},
    "30": {"name": "30 дней", "days": 30, "price": 1499},
    "90": {"name": "3 месяца", "days": 90, "price": 3499},
}

class PaymentState(StatesGroup):
    waiting_screenshot = State()

# ==================== КОМАНДЫ ====================

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="📅 Моя подписка", callback_data="my_sub")],
    ])
    await message.answer(
        "👋 Привет! Это бот приватки VORTEXX\n\n"
        "Здесь ты можешь купить доступ к закрытой группе где лежат:\n"
        "🎨 Пак для фотошопа 33 ГБ\n"
        "🎓 Курсы по аватаркам и баннерам\n"
        "💰 Способы найти первых клиентов\n"
        "📅 Живые звонки с Вортексом\n\n"
        "Выбери действие 👇",
        reply_markup=kb
    )

@dp.callback_query(F.data == "buy")
async def buy(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 дней — 799₽", callback_data="tariff_7")],
        [InlineKeyboardButton(text="30 дней — 1499₽", callback_data="tariff_30")],
        [InlineKeyboardButton(text="3 месяца — 3499₽", callback_data="tariff_90")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
    ])
    await callback.message.edit_text("Выбери тариф 👇", reply_markup=kb)

@dp.callback_query(F.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff_key = callback.data.split("_")[1]
    tariff = TARIFFS[tariff_key]
    
    pending_payments[callback.from_user.id] = tariff_key
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил, отправить скрин", callback_data="send_screenshot")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy")],
    ])
    
    await callback.message.edit_text(
        f"💳 Оплата — {tariff['name']} за {tariff['price']}₽\n\n"
        f"Переведи {tariff['price']}₽ на карту:\n"
        f"🏦 {CARD_NAME}\n"
        f"💳 <code>{CARD_NUMBER}</code>\n\n"
        f"После оплаты нажми кнопку ниже и отправь скриншот чека 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "send_screenshot")
async def request_screenshot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentState.waiting_screenshot)
    await callback.message.edit_text("📸 Отправь скриншот оплаты следующим сообщением 👇")

@dp.message(PaymentState.waiting_screenshot, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    tariff_key = pending_payments.get(user_id)
    
    if not tariff_key:
        await message.answer("❌ Ошибка, начни заново — /start")
        return
    
    tariff = TARIFFS[tariff_key]
    
    # Уведомление админу
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{user_id}_{tariff_key}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{user_id}")],
    ])
    
    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"💰 Новая оплата!\n\n"
                f"👤 Пользователь: @{username} (ID: {user_id})\n"
                f"📦 Тариф: {tariff['name']} — {tariff['price']}₽\n\n"
                f"Подтвердить оплату?",
        reply_markup=kb
    )
    
    await state.clear()
    await message.answer("✅ Скриншот отправлен! Ожидай подтверждения — обычно до 15 минут 🕐")

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    tariff_key = parts[2]
    tariff = TARIFFS[tariff_key]
    
    # Добавляем подписку
    expire_date = datetime.now() + timedelta(days=tariff["days"])
    subscriptions[user_id] = expire_date
    
    link = "https://t.me/+uEkFhFCBsIowOTI1"
    
    await bot.send_message(
        user_id,
        f"✅ Оплата подтверждена!\n\n"
        f"📦 Тариф: {tariff['name']}\n"
        f"📅 Доступ до: {expire_date.strftime('%d.%m.%Y')}\n\n"
        f"🔗 Ссылка для вступления (одноразовая):\n{link}\n\n"
        f"Добро пожаловать в приватку VORTEXX! 🔥"
    )
    
    await callback.message.edit_caption(
        callback.message.caption + f"\n\n✅ ПОДТВЕРЖДЕНО — доступ выдан до {expire_date.strftime('%d.%m.%Y')}"
    )

@dp.callback_query(F.data.startswith("decline_"))
async def decline_payment(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    await bot.send_message(
        user_id,
        "❌ Оплата не подтверждена.\n\n"
        "Возможно скриншот нечёткий или сумма не совпадает.\n"
        "Попробуй снова — /start"
    )
    
    await callback.message.edit_caption(callback.message.caption + "\n\n❌ ОТКЛОНЕНО")

@dp.callback_query(F.data == "my_sub")
async def my_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    expire = subscriptions.get(user_id)
    
    if expire and expire > datetime.now():
        days_left = (expire - datetime.now()).days
        text = f"✅ Твоя подписка активна\n📅 Осталось: {days_left} дней\n⏰ До: {expire.strftime('%d.%m.%Y')}"
    else:
        text = "❌ У тебя нет активной подписки\n\nНажми /start чтобы купить доступ"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="📅 Моя подписка", callback_data="my_sub")],
    ])
    await callback.message.edit_text(
        "👋 Привет! Это бот приватки VORTEXX\n\n"
        "Выбери действие 👇",
        reply_markup=kb
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())