import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import init_db, add_participant, get_all_participants, remove_participant

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# --- НАСТРОЙКИ ---
BOT_TOKEN = "7908303618:AAGiOBO2H8T4yHeZdtlyRLPrncAmUdaJig4"
CHANNELS = ["@pluggg420_shop", "@pluggg_world"]
MAIN_CHANNEL = "@pluggg420_shop"
TARGET_SUBS = 400
ADMIN_ID = 7509267326

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
from aiogram.client.default import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()
last_post_msg_id = None
finalized = False

# --- FSM состояния для /post ---
class PostStates(StatesGroup):
    waiting_photo = State()
    waiting_text = State()

# --- Команда /start ---
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять участие", callback_data="join")]
    ])
    await message.answer(
        "🎉 Прими участие в конкурсе!\n\nНажми кнопку ниже и будь подписан на оба канала.",
        reply_markup=kb
    )

# --- Команда /post для создания поста админом ---
@dp.message(F.text == "/post")
async def cmd_post_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Недостаточно прав.")
        return
    await message.answer("📸 Отправь фото или напиши 'нет' если без фото:")
    await state.set_state(PostStates.waiting_photo)

@dp.message(F.text.casefold() == "нет", PostStates.waiting_photo)
async def post_no_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=None)
    await message.answer("✍️ Введи текст поста:")
    await state.set_state(PostStates.waiting_text)

@dp.message(F.photo, PostStates.waiting_photo)
async def post_with_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("✍️ Введи текст поста:")
    await state.set_state(PostStates.waiting_text)

@dp.message(PostStates.waiting_text)
async def post_text_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo = data.get("photo")
    text = message.text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Принять участие ({len(get_all_participants())})", callback_data="join")]
    ])

    global last_post_msg_id
    try:
        if photo:
            msg = await bot.send_photo(chat_id=MAIN_CHANNEL, photo=photo, caption=text, reply_markup=kb)
        else:
            msg = await bot.send_message(chat_id=MAIN_CHANNEL, text=text, reply_markup=kb)
        last_post_msg_id = msg.message_id
        await message.answer("✅ Пост опубликован.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при публикации: {e}")
    await state.clear()

# --- Проверка подписки ---
async def is_subscribed(user_id: int) -> (bool, list):
    missing = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return len(missing) == 0, missing

# --- Обработка нажатия "Принять участие" ---
@dp.callback_query(F.data == "join")
async def callback_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    full_name = callback.from_user.full_name

    subscribed, missing = await is_subscribed(user_id)
    if not subscribed:
        await callback.answer("❗ Ты должен подписаться на все каналы!", show_alert=True)
        # Если был в участниках — удалим
        if user_id in get_all_participants():
            remove_participant(user_id)
        return

    if user_id in get_all_participants():
        await callback.answer("✅ Ты уже участвуешь!", show_alert=True)
        return

    add_participant(user_id, full_name, username)
    await callback.answer("✅ Участие принято!", show_alert=True)
    await update_post_button()

# --- Обновляем кнопку под постом с количеством участников ---
async def update_post_button():
    global last_post_msg_id
    if last_post_msg_id is None:
        return
    count = len(get_all_participants())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Принять участие ({count})", callback_data="join")]
    ])
    try:
        await bot.edit_message_reply_markup(chat_id=MAIN_CHANNEL, message_id=last_post_msg_id, reply_markup=kb)
    except Exception:
        pass

# --- Проверяем количество подписчиков и объявляем итоги ---
async def check_subscribers_job():
    global finalized
    if finalized:
        return
    try:
        chat = await bot.get_chat(MAIN_CHANNEL)
        count = await chat.get_member_count()
        if isinstance(count, int) and count >= TARGET_SUBS:
            finalized = True
            await announce_winners()
    except Exception as e:
        logging.error(f"Ошибка проверки подписчиков: {e}")
        await bot.send_message(ADMIN_ID, f"Ошибка проверки подписчиков: {e}")

# --- Объявление победителей ---
async def announce_winners():
    participants = get_all_participants()
    if len(participants) < 5:
        await bot.send_message(ADMIN_ID, "Недостаточно участников для пяти призовых мест.")
        return

    winners = random.sample(participants, 5)
    prizes = [
        "🥇 1 место — брелок",
        "🥈 2 место — брелок",
        "🥉 3 место — брелок",
        "4 место — 100 грн",
        "5 место — 100 грн"
    ]
    text = "<b>🏆 Итоги конкурса!</b>\n\n"
    for i, uid in enumerate(winners):
        text += f"{prizes[i]} — <a href='tg://user?id={uid}'>Победитель {i+1}</a>\n"

    await bot.send_message(MAIN_CHANNEL, text)
    for uid in participants:
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass

# --- Запуск бота ---
async def main():
    init_db()
    scheduler.add_job(check_subscribers_job, "interval", seconds=30)
    scheduler.start()
    await bot.send_message(ADMIN_ID, "🤖 Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())