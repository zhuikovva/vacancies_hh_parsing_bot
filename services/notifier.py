import asyncio
import aiohttp
from aiogram import Bot
from database.database import Database
from datetime import datetime, timezone
from services.hh_parser import fetch_hh_ids, fetch_vacancy, process_vacancy
import logging

logger = logging.getLogger(__name__)

class VacancyNotifier:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.is_running = True

    async def start(self):
        while self.is_running:
            try:
                users = await self.db.get_all_users()
                #logger.info(f"[NOTIFIER] Проверяю {len(users)} пользователей")
                for user in users:
                    chat_id = user['chat_id']
                    last_check = user['last_check']
                    interval = user['update_interval']

                    # Приводим last_check к aware формату
                    if last_check.tzinfo is None:
                        last_check = last_check.replace(tzinfo=timezone.utc)

                    now = datetime.now(timezone.utc)

                    if (now - last_check).total_seconds() >= interval * 60:
                        await self.check_and_notify(user)

                    await asyncio.sleep(5)  

                await asyncio.sleep(60)  

            except Exception as e:
                logger.error("[NOTIFIER] Ошибка в основном цикле", exc_info=True)
    
    async def update_vacancies_from_api(self):
        try:
            last_published = await self.db.get_last_published_time()
            logger.info(f"[FETCH] Запрашиваем вакансии с {last_published}")

            async with aiohttp.ClientSession() as session:
                new_ids = await fetch_hh_ids(session, date_from=last_published)
                existing_ids = await self.db.get_existing_ids()
                ids_to_process = [id for id in new_ids if id not in existing_ids]

                for vac_id in ids_to_process:
                    raw_vacancy = await fetch_vacancy(session, vac_id)
                    processed = process_vacancy(raw_vacancy)
                    await self.db.insert_vacancy(processed)

        except Exception as e:
            logger.error(f"[NOTIFIER] Ошибка при обновлении вакансий: {e}", exc_info=True)

    async def check_and_notify(self, user):
        
        chat_id = user['chat_id']
        last_check = user['last_check']
        interval = user['update_interval']

        logger.debug(f"[DEBUG] user['last_check']: {last_check}, тип: {type(last_check)}")

        if last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        logger.info(f"[NOTIFY] Проверка пользователя {chat_id}:")
        logger.info(f"  - Интервал: {interval} мин")
        logger.info(f"  - Последняя проверка: {last_check}")
        logger.info(f"  - Текущее время: {now}")
        logger.info(f"  - Прошло времени: {(now - last_check).total_seconds()} сек")

        if (now - last_check).total_seconds() >= interval * 60:
            try:
                check_start_time = now
                logger.debug(f"[DEBUG] Фильтруем вакансии с published_at > {last_check}")
                await self.update_vacancies_from_api()
                
                new_vacancies = await self.db.get_new_vacancies(last_check)

                logger.info(f"  - Найдено новых вакансий: {len(new_vacancies)}")

                if new_vacancies:
                    await self.send_vacancies(chat_id, new_vacancies)
                await self.update_last_check(chat_id, check_start_time)
            except Exception as e:
                logger.error(f"[NOTIFY] Ошибка при обработке вакансии {e}", exc_info=True)

    async def send_vacancies(self, chat_id: int, vacancies):
        for vacancy in vacancies:
            message = self.format_vacancy(vacancy)
            try:
                await self.bot.send_message(chat_id, message, parse_mode='HTML')
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"[NOTIFIER] Не удалось отправить вакансию: {e}")

    def format_vacancy(self, vacancy) -> str:
        salary_info = ""
        if vacancy.get("salary_from"):
            salary_info = f"💵 Зарплата: {vacancy['salary_from']} – {vacancy['salary_to'] or '?'}"
        else:
            salary_info = f"💸 Примерная зарплата: {vacancy['predicted_salary']}"

        
        return (
            f"🔥 <b>{vacancy['vacancy_name']}</b>\n"
            f"🏢 {vacancy.get('employer', 'Работодатель не указан')}\n"
            f"📍 {vacancy.get('city', 'Город не указан')}\n"
            f"{salary_info}\n"
            f"🎯 Грейд: {vacancy.get('grade', 'Не определен')}\n"
            f"🔗 <a href='{vacancy.get('url', '#')}'>Подробнее</a>"
        )

    async def update_last_check(self, chat_id: int, new_time=None):
        if new_time is None:
            new_time = datetime.now(timezone.utc)
        
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE users SET last_check = $1 WHERE chat_id = $2',
                    new_time,
                    chat_id
                )
        except (asyncpg.exceptions.ConnectionDoesNotExistError,
                asyncpg.exceptions.ConnectionClosedError) as e:
            logger.error(f"[NOTIFIER] Соединение потеряно: {e}")
            await self.db.connect()
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE users SET last_check = $1 WHERE chat_id = $2',
                    new_time,
                    chat_id
                )