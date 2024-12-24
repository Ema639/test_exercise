from aiogram import Bot, Dispatcher, types
import asyncio
from aiogram.filters import Command
from aiogram import F
import logging
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import TOKEN
import aiosqlite
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

EMAIL_ADDRESS = 'test@mail.ru'  # Ваш email на Mail.ru
EMAIL_PASSWORD = 'password'  # Ваш пароль от почты или пароль приложения
ADMIN_EMAILS = ['admin1@example.com', 'admin2@example.com']  # Замените на реальные адреса


# Определение состояний
class Form(StatesGroup):
    waiting_for_email_message = State()


# Создание базы данных и таблицы
def create_db():
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY
        )
    ''')
    connection.commit()
    connection.close()


# Функция для очистки таблицы users
def clear_users_table():
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()

    cursor.execute('DELETE FROM users;')  # Удаляем все записи из таблицы
    connection.commit()

    connection.close()


# Стартовая клавиатура
def start_keyboard():
    markup = InlineKeyboardBuilder()
    markup.add(InlineKeyboardButton(text="Оплата 💲", url="https://payment-provider.com/test"))
    markup.add(InlineKeyboardButton(text="Отправить сообщение на электронную почту ✉️", callback_data="send_message"))
    return markup.adjust(1).as_markup()


# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    # Подключение к базе данных
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()

    # Проверяем, есть ли пользователь в базе данных
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if user is None:
        # Если пользователь новый, добавляем его в БД
        cursor.execute('INSERT INTO users (id) VALUES (?)', (user_id,))
        connection.commit()
        await message.answer("Добро пожаловать! Это ваше первое сообщение.")
    else:
        await message.answer("Вы уже использовали команду /start.")

    # Закрытие соединения
    connection.close()
    await message.answer(text="Привет, этот бот для тестового задания! "
                              "\n\n Выберите действие:", reply_markup=start_keyboard())


async def check_users():
    async with aiosqlite.connect('users.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM users;')
        count = await cursor.fetchone()
        print(f"Количество пользователей: {count[0]}")


@dp.callback_query(F.data == 'send_message')
async def process_send_message(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.from_user.id, "Введите ваше сообщение для отправки на почту:")

    # Переход к состоянию ожидания сообщения от пользователя
    await state.set_state(Form.waiting_for_email_message)  # Установка состояния


@dp.message(Form.waiting_for_email_message)
async def handle_send_email(message: types.Message, state: FSMContext):
    email_message = message.text  # Получаем текст сообщения от пользователя

    try:
        await send_email(email_message)  # Отправляем email асинхронно
        await message.answer("Ваше сообщение отправлено на электронную почту.")
    except Exception as e:
        logging.error(f"Ошибка при отправке email: {e}")
        await message.answer("Произошла ошибка при отправке сообщения на электронную почту.")

    await state.clear()  # Завершение состояния


async def send_email(message_body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['Subject'] = 'Сообщение от Telegram бота'

    msg.attach(MIMEText(message_body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL('smtp.mail.ru', 465) as server:  # Используем SSL для подключения
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)  # Вход в почтовый ящик
            for admin_email in ADMIN_EMAILS:
                msg['To'] = admin_email  # Устанавливаем адрес получателя для каждого администратора
                server.send_message(msg)  # Отправка сообщения
                logging.info(f"Email отправлен успешно на {admin_email}.")

    except Exception as e:
        logging.error(f"Ошибка при отправке email: {e}")
        raise e  # Пробрасываем исключение выше


async def main():
    create_db()
    clear_users_table()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
