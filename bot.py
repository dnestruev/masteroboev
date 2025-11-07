import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)
import aiosqlite

TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ЗДЕСЬ")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "adminpass123")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- ИНИЦИАЛИЗАЦИЯ БАЗЫ ----------------
async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users(
                            user_id INTEGER PRIMARY KEY,
                            is_vip INTEGER DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS admin(
                            user_id INTEGER PRIMARY KEY)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS wallpapers(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            file_id TEXT,
                            access TEXT)""")
        await db.commit()

# ---------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------------
async def is_vip(user_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT is_vip FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 1

async def is_admin(user_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT user_id FROM admin WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# ---------------- КНОПКИ ----------------
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖼 Обои")],
            [KeyboardButton(text="💎 VIP-доступ"), KeyboardButton(text="ℹ️ Инфо")],
            [KeyboardButton(text="⚙️ Админ")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Загрузить обои")],
            [KeyboardButton(text="🚪 Выйти из админки")]
        ],
        resize_keyboard=True
    )

# ---------------- ОБЫЧНЫЕ ПОЛЬЗОВАТЕЛИ ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    async with aiosqlite.connect("database.db") as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (message.from_user.id,))
        await db.commit()
    await message.answer("👋 Привет! Это бот *Мастер обоев* — красивых обоев много! 🎨", reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(F.text == "🖼 Обои")
async def wallpapers(message: types.Message):
    user_vip = await is_vip(message.from_user.id)
    async with aiosqlite.connect("database.db") as db:
        if user_vip:
            async with db.execute("SELECT file_id FROM wallpapers") as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT file_id FROM wallpapers WHERE access='all'") as cursor:
                rows = await cursor.fetchall()
    if not rows:
        await message.answer("😕 Пока нет доступных обоев.")
        return
    for row in rows:
        try:
            await message.answer_photo(row[0])
        except Exception:
            # Если отправка по file_id не проходит, продолжаем
            pass

@dp.message(F.text == "💎 VIP-доступ")
async def vip_info(message: types.Message):
    text = (
        "💎 *VIP-доступ* открывает все обои!\n\n"
        "🪙 23 ₽ / месяц\n"
        "💰 1000 ₽ навсегда\n\n"
        "_Покупка пока вручную — напиши админу._"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Инфо")
async def info(message: types.Message):
    await message.answer("📲 Этот бот создан для рассылки обоев. Админ может загружать обои прямо в чат, выбрав — всем или только VIP.")

# ---------------- АДМИНКА ----------------
@dp.message(F.text == "⚙️ Админ")
async def admin_enter(message: types.Message):
    if await is_admin(message.from_user.id):
        await message.answer("🔐 Добро пожаловать в админку.", reply_markup=admin_menu())
        return
    await message.answer("Введите пароль администратора:")

    @dp.message(F.text)
    async def password_check(msg: types.Message):
        if msg.text == ADMIN_PASSWORD:
            async with aiosqlite.connect("database.db") as db:
                await db.execute("INSERT OR IGNORE INTO admin(user_id) VALUES(?)", (msg.from_user.id,))
                await db.commit()
            await msg.answer("✅ Доступ разрешён.", reply_markup=admin_menu())
        else:
            await msg.answer("❌ Неверный пароль.")
        try:
            dp.message.handlers.unregister(password_check)
        except Exception:
            pass

@dp.message(F.text == "📤 Загрузить обои")
async def admin_upload(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ Только для администратора.")
        return
    await message.answer("📸 Отправь фото для загрузки (в одном сообщении).")

    @dp.message(F.photo)
    async def handle_photo(msg: types.Message):
        file_id = msg.photo[-1].file_id
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Всем", callback_data=f"upload_all:{file_id}")],
            [InlineKeyboardButton(text="💎 Только VIP", callback_data=f"upload_vip:{file_id}")]
        ])
        await msg.answer("📂 Кому выгрузить фото?", reply_markup=buttons)
        try:
            dp.message.handlers.unregister(handle_photo)
        except Exception:
            pass

@dp.callback_query(F.data.startswith("upload_"))
async def upload_choice(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return

    choice, file_id = callback.data.split(":")
    access_value = "all" if choice == "upload_all" else "vip"
    async with aiosqlite.connect("database.db") as db:
        await db.execute("INSERT INTO wallpapers(file_id, access) VALUES(?,?)", (file_id, access_value))
        await db.commit()
    await callback.message.answer(f"✅ Фото сохранено для категории: {'ВСЕМ' if access_value == 'all' else 'VIP'}")
    await callback.answer()

@dp.message(F.text == "🚪 Выйти из админки")
async def admin_exit(message: types.Message):
    # удаляем из таблицы admin при выходе (по желанию)
    async with aiosqlite.connect("database.db") as db:
        await db.execute("DELETE FROM admin WHERE user_id = ?", (message.from_user.id,))
        await db.commit()
    await message.answer("🔙 Вы вышли из админ-панели.", reply_markup=main_menu())

# ---------------- ЗАПУСК ----------------
async def main():
    print("✅ Бот 'Мастер обоев' запущен!")
    await init_db()
    # Bot will run with polling on Render worker (startCommand: python bot.py)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
