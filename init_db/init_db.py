import psycopg2
from psycopg2 import sql

def create_tables():
    conn = psycopg2.connect(
        dbname='practice',
        user='danil',
        password='12345',
        host='postgres',
        port='5432'
    )
    cursor = conn.cursor()

    create_vacancies_table_query = """
    CREATE TABLE IF NOT EXISTS vacancies (
        id SERIAL PRIMARY KEY,
        hh_id VARCHAR(50) UNIQUE NOT NULL,
        title TEXT NOT NULL,
        link TEXT NOT NULL,
        employer TEXT,
        salary JSONB,
        date_posted TIMESTAMP,
        description TEXT,
        requirements TEXT
    );
    """
    

    
    cursor.execute(create_vacancies_table_query)
    conn.commit()

    cursor.close()
    conn.close()

if __name__ == '__main__':
    create_tables()