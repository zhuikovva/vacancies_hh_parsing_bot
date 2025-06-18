GET_EXISTING_IDS = 'SELECT id FROM vacancies_hh'

INSERT_VACANCY = '''
INSERT INTO vacancies_hh (
    id, vacancy_name, schedule, experience, city, employer,
    salary_from, salary_to, type, url, key_skills, professional_role,
    description, published_at, experience_cat, grade, predicted_salary
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
ON CONFLICT (id) DO NOTHING
'''

