import asyncpg
from config.config import DatabaseConfig
from database.queries import GET_EXISTING_IDS, INSERT_VACANCY
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: asyncpg.Pool 

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            user=self.config.db_user,
            password=self.config.db_password,
            host=self.config.db_host,
            database=self.config.database,
            port=self.config.db_port,
            # добавление для нелокальной базы
            ssl="require",
            statement_cache_size=0,
            min_size=5,
            max_size=10,
        )
    
    async def create_users_table(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                update_interval INT DEFAULT 60,
                last_check TIMESTAMP DEFAULT NOW()
                )
            ''')

    
    async def update_user_settings(self, chat_id: int, interval: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (chat_id, update_interval)
                VALUES ($1, $2)
                ON CONFLICT (chat_id) DO UPDATE
                SET update_interval = EXCLUDED.update_interval
            ''', chat_id, interval)


    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT * FROM users')
        
    
    async def get_new_vacancies(self, last_check: datetime):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM vacancies_hh WHERE published_at > $1',
                last_check
            )


    async def get_recent_vacancies(self, limit: int = 10) -> list[asyncpg.Record]:
        if not self.pool:
            raise ConnectionError("Database connection not established.")

        async with self.pool.acquire() as conn:
            query = """
            SELECT * 
            FROM vacancies_hh 
            ORDER BY published_at 
            DESC LIMIT $1
            """
            return await conn.fetch(query, limit)
    
    async def get_existing_ids(self) -> set:
        async with self.pool.acquire() as conn:
            records = await conn.fetch(GET_EXISTING_IDS)
            return {r['id'] for r in records}
        
    async def get_last_published_time(self):
        async with self.pool.acquire() as conn:
            try:
                last_time = await conn.fetchval(
                    'SELECT MAX(published_at) FROM vacancies_hh'
                )
                if last_time is None:
                    return datetime.now(timezone.utc)
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                return last_time 
            
            except Exception as e:
                logger.error(f"Error fetching last published time: {e}")
                return datetime.now(timezone.utc)
                
        
    async def insert_vacancy(self, vacancy: dict):
        async with self.pool.acquire() as conn:
            await conn.execute(
                    INSERT_VACANCY, 
                    int(vacancy['id']),
                    vacancy['vacancy_name'],
                    vacancy.get('schedule'),
                    vacancy.get('experience'),
                    vacancy.get('city'),
                    vacancy.get('employer'),
                    vacancy.get('salary_from'),
                    vacancy.get('salary_to'),
                    vacancy.get('type'),
                    vacancy.get('url'),
                    vacancy.get('key_skills', ''),
                    vacancy.get('professional_role', ''),
                    vacancy.get('description'),
                    vacancy.get('published_at'),
                    vacancy.get('experience_cat', 1),
                    vacancy.get('grade', 'Не указано'),
                    vacancy.get('predicted_salary', None),
            )

    async def add_user(self, chat_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO users (chat_id) 
                VALUES ($1)
                ON CONFLICT (chat_id) DO UPDATE
                SET last_check = NOW()
                ''',
                chat_id
            )   

    async def unsubscribe_user(self, chat_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'DELETE FROM users WHERE chat_id = $1',
                chat_id
            )

    async def get_user(self, chat_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM users WHERE chat_id = $1',
                chat_id
            )