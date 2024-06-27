from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import psycopg2
import logging
import subprocess

# Токен от чат бота (Скрою для конфиденциальности)
telegram_bot_token = "your token"

# Настройка БД
db_name = 'practice'
db_user = 'danil'
db_password = '12345'
db_host = 'postgres'
db_port = '5432'

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Парсер для API hh.ru
def fetch_job_listings(job_title, page=0, per_page=10):
    url = "https://api.hh.ru/vacancies"
    params = {
        'text': job_title,
        'page': page,
        'per_page': per_page
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        job_listings = []

        for item in data['items']:
            job_listings.append({
                'hh_id': item.get('id'),
                'title': item.get('name'),
                'link': item.get('alternate_url'),
                'employer': item.get('employer', {}).get('name'),
                'salary': item.get('salary'),
                'date_posted': item.get('published_at'),
                'description': item.get('snippet', {}).get('responsibility'),
                'requirements': item.get('snippet', {}).get('requirement')
            })
        return job_listings, data.get('pages', 0)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return [], 0

# Функция для сохранения в бд

def save_vacancies_to_db(vacancies):
    conn = psycopg2.connect(
        dbname = db_name,
        user = db_user,
        password = db_password,
        host = db_host,
        port = db_port
    )

    cursor = conn.cursor

    for vacancy in vacancies:
        hh_id = vacancy['id']
        title = vacancy['name']
        link = vacancy['alternate_url']
        employer = vacancy.get('employer', {}).get('name')
        salary = json.dumps(vacancy['salary'])
        date_posted = datetime.strptime(vacancy['published_at'], '%Y-%m-%dT%H:%M:%S%z')
        description = vacancy['snippet']['responsibility']
        requirements = vacancy['snippet']['requirement']

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

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот для поиска вакансий. Нажмите /search для поиска вакансий."
    )

# Обработчик команды /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Введите название профессии для поиска:")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    job_title = update.message.text
    await update.message.reply_text(f"Ищем вакансии для {job_title}...")

    # Запускаем парсер
    result = parse_vacancies(job_title)

    # Проверяем, успешно ли был выполнен парсинг
    if result:
        await update.message.reply_text("Вакансии найдены и сохранены в базе данных.")
        await show_vacancies(update, context, 1)
    else:
        await update.message.reply_text("Не удалось найти вакансии.")

# Функция для отображения вакансий
async def show_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cursor = conn.cursor()
    offset = (page - 1) * 10

    cursor.execute("SELECT hh_id, title FROM vacancies ORDER BY date_posted DESC LIMIT 10 OFFSET %s", (offset,))
    rows = cursor.fetchall()

    conn.close()

    if rows:
        message = "Вакансии:\n"
        buttons = []

        for idx, (hh_id, title) in enumerate(rows, start=1):
            message += f"{idx}. {title}\n"
            buttons.append([InlineKeyboardButton(text=str(idx), callback_data=f"detail_{hh_id}")])

        buttons.append([InlineKeyboardButton(text="Следующая страница", callback_data=f"page_{page+1}")])
        if page > 1:
            buttons.append([InlineKeyboardButton(text="Предыдущая страница", callback_data=f"page_{page-1}")])

        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Больше вакансий нет.")

# Обработчик для inline-кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await show_vacancies(update, context, page)
    elif data.startswith("detail_"):
        hh_id = data.split("_")[1]
        await show_vacancy_detail(update, context, hh_id)

# Функция для отображения подробной информации о вакансии
async def show_vacancy_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, hh_id: str) -> None:
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cursor = conn.cursor()

    cursor.execute("SELECT title, link, employer, salary, date_posted, description, requirements FROM vacancies WHERE hh_id = %s", (hh_id,))
    vacancy = cursor.fetchone()

    conn.close()

    if vacancy:
        title, link, employer, salary, date_posted, description, requirements = vacancy
        message = f"*{title}*\n\n"
        message += f"*Компания:* {employer}\n"
        message += f"*Зарплата:* {salary}\n"
        message += f"*Дата публикации:* {date_posted}\n\n"
        message += f"*Описание:*\n{description}\n\n"
        message += f"*Требования:*\n{requirements}\n\n"

        buttons = [[InlineKeyboardButton(text="Ссылка на вакансию", url=link)]]
        buttons.append([InlineKeyboardButton(text="Назад", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text("Вакансия не найдена.")

def parse_vacancies(job_title):
    try:
        # Получаем список вакансий
        vacancies = fetch_job_listings(job_title)

        # Сохраняем вакансии в БД
        save_vacancies_to_db(vacancies)

        print(f"Fetched and saved {len(vacancies)} vacancies.")
        return True
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return False

def main() -> None:
    application = ApplicationBuilder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
