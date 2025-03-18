import psycopg2
import json
from datetime import datetime


# Настройка БД
db_name = 'practice'
db_user = 'danil'
db_password = '12345'
db_host = 'postgres'
db_port = '5432'

def get_db_connection():
    """Установка подключения к БД"""
    return psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )

def save_vacancies_to_db(vacancies):
    """Функция для сохранения в бд"""
    conn = get_db_connection()

    cursor = conn.cursor()

    for vacancy in vacancies:
        hh_id = vacancy['hh_id']
        title = vacancy['title']
        link = vacancy['link']
        employer = vacancy.get('employer', None)
        salary = json.dumps(vacancy['salary'])
        date_posted = datetime.strptime(vacancy['date_posted'], '%Y-%m-%dT%H:%M:%S%z')
        description = vacancy.get('description', '')
        requirements = vacancy.get('requirements', '')

        cursor.execute("""
        INSERT INTO vacancies (hh_id, title, link, employer, salary, date_posted, description, requirements)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (hh_id) DO UPDATE
        SET title = EXCLUDED.title,
            link = EXCLUDED.link,
            employer = EXCLUDED.employer,
            salary = EXCLUDED.salary,
            date_posted = EXCLUDED.date_posted,
            description = EXCLUDED.description,
            requirements = EXCLUDED.requirements
        """, (hh_id, title, link, employer, salary, date_posted, description, requirements))

    conn.commit()
    cursor.close()
    conn.close()   

def get_vacancies_count():
    """Функция для проверки количества вакансий в базе данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM vacancies')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_vacancies_from_db(sort_by=None, sort_order=None, filter_by=None, filter_value=None):
    """Функция для получения вакансий из базы данных с фильтрацией и сортировкой"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT hh_id, title FROM vacancies"
    params = []

    if filter_by and filter_value:
        query += f" WHERE {filter_by} ILIKE %s"
        params.append(f"%{filter_value}%")

    if sort_by:
        query += f" ORDER BY {sort_by} {sort_order}"

    cursor.execute(query, params)
    vacancies = cursor.fetchall()
    conn.close()
    return vacancies