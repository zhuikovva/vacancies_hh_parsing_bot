from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram import Router
from lexicon.lexicon import LEXICON_RU
from database.database import Database
from zoneinfo import ZoneInfo

router = Router()

@router.message(CommandStart())
async def process_start_command(message: Message):
    await message.answer(text=LEXICON_RU['/start'])

@router.message(Command(commands='help'))
async def process_help_command(message: Message):
    await message.answer(text=LEXICON_RU['/help'])

@router.message(Command('subscribe'))
async def subscribe(message: Message, db: Database):
    chat_id = message.chat.id
    await db.add_user(chat_id)
    await message.answer("Вы успешно подписаны на обновления вакансий!")


@router.message(Command('unsubscribe'))
async def unsubscribe(message: Message, db: Database):
    chat_id = message.chat.id
    await db.unsubscribe_user(chat_id)
    await message.answer("Вы отписаны от обновлений вакансий.")


@router.message(Command('status'))
async def status(message: Message, db: Database):
    user = await db.get_user(message.chat.id)
    if user:
        await message.answer(
            f"Текущие настройки:\n"
            f"Интервал проверки: {user['update_interval']} мин\n"
            f"Последняя проверка: {user['last_check'].astimezone(ZoneInfo("Europe/Moscow"))}"
        )
    else:
        await message.answer("Вы не подписаны на обновления.")

@router.message(Command('set_interval'))
async def set_interval(message: Message, db: Database):
    try:
        interval = int(message.text.split()[-1])
        if interval < 5:
            await message.answer("Интервал должен быть не менее 5 минут.")
            return
        
        await db.update_user_settings(message.chat.id, interval)
        await message.answer(f"Интервал обновления успешно установлен на {interval} минут.")
    except:
        await message.answer("Использование: /set_interval <минуты>")

