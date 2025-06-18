from aiogram.types import Message
from aiogram import F, Router
from lexicon.lexicon import LEXICON_RU
from database.database import Database
from services.hh_parser import fetch_hh_ids, fetch_vacancy, process_vacancy

import aiohttp
import logging

logger = logging.getLogger(__name__)


router = Router()

@router.message(F.text.lower().startswith('начать'))
async def start_parsing(message: Message, db: Database):
    await message.answer(text=LEXICON_RU['начать'])
    try:
        last_published = await db.get_last_published_time()
        logging.info(f"[FETCH] Запрашиваем вакансии с {last_published}")
        
        async with aiohttp.ClientSession() as session:
            new_ids = await fetch_hh_ids(session, date_from=last_published)
            
            existing_ids = await db.get_existing_ids()
            ids_to_process = [id for id in new_ids if id not in existing_ids]

            vacancies_to_send = []
            for vac_id in ids_to_process:
                try:
                    raw_vacancy = await fetch_vacancy(session, vac_id)
                    processed = process_vacancy(raw_vacancy)
                    await db.insert_vacancy(processed)
                    vacancies_to_send.append(processed)
                except Exception as e:
                    logger.error(f"Ошибка при обработке вакансии с ID {vac_id}: {e}", exc_info=True)
                    continue
            

            if vacancies_to_send:
                await message.answer(f"Добавлено {len(ids_to_process)} новых вакансий!")
                response_parts = []
                for vacancy in vacancies_to_send:
                    salary_info = ""
                    if vacancy.get("salary_from"):
                        salary_info = f"💵 Зарплата: {vacancy['salary_from']} – {vacancy['salary_to'] or '?'}"
                    else:
                        salary_info = f"💸 Примерная зарплата: {vacancy['predicted_salary']}"

                    response_parts.append(
                                f"🔥 <b>{vacancy['vacancy_name']}</b>\n"
                                f"🏢 {vacancy.get('employer', 'Работодатель не указан')}\n"
                                f"📍 {vacancy.get('city', 'Город не указан')}\n"
                                f"{salary_info}\n"
                                f"🎯 Грейд: {vacancy.get('grade', 'Не определен')}\n"
                                f"🔗 <a href='{vacancy.get('url', '#')}'>Подробнее</a>"
                            )

                # Разбиваем по 5 вакансий на сообщение
                for i in range(0, len(response_parts), 5):
                    await message.answer('\n\n'.join(response_parts[i:i+5]), parse_mode='HTML')
            else:
                await message.answer("Новых вакансий пока нет.")

    except Exception as e:
        logger.error(f"Произошла критическая ошибка: {e}", exc_info=True)

@router.message(F.text.lower().startswith('да'))
async def process_yes_answer(message: Message, db: Database):

    try:
        vacancies = await db.get_recent_vacancies()
    
        if not vacancies:
            await message.answer('Вакансий не найдено')
            return

    # форматируем вакансии в читаемый вид
        response= []
        for vacancy in vacancies:
            salary_info = ""
            if vacancy.get("salary_from"):
                salary_info = f"💵 Зарплата: {vacancy['salary_from']} – {vacancy['salary_to'] or '?'}"
            else:
                salary_info = f"💸 Примерная зарплата: {vacancy['predicted_salary']}"
            response.append( 
                        f"🔥 <b>{vacancy['vacancy_name']}</b>\n"
                                f"🏢 {vacancy.get('employer', 'Работодатель не указан')}\n"
                                f"📍 {vacancy.get('city', 'Город не указан')}\n"
                                f"{salary_info}\n"
                                f"🎯 Грейд: {vacancy.get('grade', 'Не определен')}\n"
                                f"🔗 <a href='{vacancy.get('url', '#')}'>Подробнее</a>"
            )
        # Разбиваем на сообщения по 5 вакансий
        for i in range(0, len(response), 5):
            await message.answer('\n'.join(response[i:i+5]), parse_mode='HTML')

    except Exception as e:
       logger.error(f"Произошла ошибка при получении вакансий: {str(e)}", exc_info=True)


@router.message(F.text.lower().startswith('нет'))
async def process_no_answer(message: Message):
    await message.answer(text=LEXICON_RU['нет'])

# если не одна из команд не сработала, то выдаем сообщение из another
@router.message()
async def process_another_answer(message: Message):
    await message.answer(text=LEXICON_RU['another'])
