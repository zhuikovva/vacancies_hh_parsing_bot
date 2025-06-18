import asyncio

from aiogram  import Bot, Dispatcher
from config.config import Config, load_config
from handlers import user_handlers, other_handlers
from database.database import Database
from services.notifier import VacancyNotifier
from keyboards.set_menu import set_main_menu

import logging

# задаем уровень логов
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

# функция для запуска бота
async def main() -> None:
    # загружаем конфиг
    config: Config = load_config()

    # инициализируем бот и диспетчер
    
    bot = Bot(token=config.tg_bot.token)
    dp = Dispatcher()

    # вызываем кнопку menu
    await set_main_menu(bot)

    # Инициализируем БД
    database = Database(config.db)
    await database.connect()
    await database.create_users_table()

    # Запуск фонового нотификатора
    notifier = VacancyNotifier(bot, database)
    asyncio.create_task(notifier.start())

    # Добавляем БД в контекст диспетчера
    dp['db'] = database

    # регистрируем роутеры в диспетчере
    dp.include_router(user_handlers.router)
    dp.include_router(other_handlers.router)

    # пропускаем апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

asyncio.run(main())