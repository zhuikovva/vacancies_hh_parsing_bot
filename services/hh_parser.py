import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime, timezone
from models.ml_models import MlModels
import pandas as pd
import logging

ml_models = MlModels()

logger =  logging.getLogger(__name__)

def hh_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def fetch_hh_ids(session: aiohttp.ClientSession, date_from: datetime, max_pages: int = 3) -> List[str]:
    ids = []

    for page in range(0, max_pages):
        params = {
            'text': ('name:"data analyst" or "аналитик данных" or "data аналитик"'
                    ' or "продуктовый аналитик" or "Data Analyst" or "Data analyst"'
                    ' or "Аналитик данных" or "BI-аналитик" or "bi-аналитик"'
                    ' not "manager" not "QA-инженер" not "Маркетолог|маркетолог" not "DWH|dwh"'),
            'area': '113',
            'per_page': '100',
            'page': page,
            'professional_role': [10, 156, 164],
            'date_from': hh_datetime(date_from)
        }

        async with session.get('https://api.hh.ru/vacancies', params=params) as response:
            if response.status != 200:
                logger.warning(f"Ошибка при запросе к HH.ru на странице {page}: {response.status}")
                continue

            data = await response.json()
            page_ids = [item['id'] for item in data.get('items', [])]
            ids.extend(page_ids)
            logging.info(f"[HH] Запрос с date_from: {params['date_from']}")

            logging.info(f"[HH] Страница {page} — получено {len(page_ids)} ID")

    return list(set(ids))

async def fetch_vacancy(session:aiohttp.ClientSession, vacancy_id: str) -> Dict[str, Any]:
    url = f'https://api.hh.ru/vacancies/{vacancy_id}'
    async with session.get(url) as response:
        return await response.json()

def process_vacancy(item: Dict[str, Any]) -> Dict[str, Any]:
    description = item.get('description', 'Не указано')
    if description:
        soup = BeautifulSoup(description, 'html.parser')
        description = soup.get_text()

    key_skills = item.get('key_skills')
    raw_skills = (
                [skill['name'] for skill in key_skills] 
                if isinstance(key_skills, list) 
                else key_skills.split(',') 
                if isinstance(key_skills, str) 
                else []
                )
    
    processed_skills = ', '.join(raw_skills) if raw_skills else 'Не указано'

    salary = item.get('salary') or {}

    exp_mapping = {
        'Нет опыта': 0,
        'От 1 года до 3 лет': 1,
        'От 3 до 6 лет': 2,
        'Более 6 лет': 3
    }
    experience_data = item.get('experience') or {}
    raw_experience = experience_data.get('name', 'Нет опыта')
    experience_cat = exp_mapping.get(raw_experience, 0)

    published_at_str = item.get('published_at')
    published_at = None

    if published_at_str:
        try:
            # Парсим строку в datetime с учётом временного пояса
            published_at = datetime.fromisoformat(published_at_str)

            # Если дата не имеет временного пояса — делаем её UTC
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except Exception as e:
            logging.warning(f"[DATE_PARSE] Не удалось распознать published_at: {e}")
            published_at = datetime.now(timezone.utc)
    
    vacancy = {
            'id': item.get('id'),
            'vacancy_name': item.get('name'),
            'schedule': item.get('schedule', {}).get('name') if item.get('schedule') else None,
            'experience': raw_experience,
            'experience_cat': experience_cat,
            'city': item.get('area', {}).get('name') if item.get('area') else None,
            'employer': item.get('employer', {}).get('name') if item.get('employer') else None,
            'salary_from': salary.get('from'),
            'salary_to': salary.get('to'),
            'type': item.get('type', {}).get('name') if item.get('type') else None,
            'url': item.get('alternate_url'),
            'key_skills': processed_skills,
            'professional_role': ', '.join([role['name'] for role in item.get('professional_roles', [])]) or None,
            'description': description,
            'published_at': published_at   
        }

    features_grade = {
        'vacancy_name':  item.get('name'), 
        'schedule': item.get('schedule', {}).get('name') if item.get('schedule') else 'Не указано', 
        'experience': raw_experience,
        'salary_to': salary.get('to'), 
        'key_skills': processed_skills, 
        'description': description, 
    }

    grade = ml_models.predict_grade(pd.DataFrame([features_grade]))
    vacancy['grade'] = grade
    
    features_salary = {
        'vacancy_name':  item.get('name'), 
        'schedule': item.get('schedule', {}).get('name') if item.get('schedule') else 'Не указано', 
        'salary_to': salary.get('to'), 
        'key_skills': processed_skills, 
        'description': description, 
        'grade': grade,
        'experience': raw_experience,
        
    }
    if vacancy['salary_from'] is None:
        predicted_salary = ml_models.predict_salary(pd.DataFrame([features_salary]))
        vacancy['predicted_salary'] = round(predicted_salary, -2).astype(int)

    return vacancy