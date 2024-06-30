from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import psycopg2
import logging
import subprocess
import requests
import json
from datetime import datetime
import re

# Токен от чат бота (Скрою для конфиденциальности)
telegram_bot_token = "your token"

# Настройка БД
db_name = 'practice'
db_user = 'danil'
db_password = '12345'
db_host = 'localhost'
db_port = '5432'

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функция для сохранения в бд
def save_vacancies_to_db(vacancies):
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )

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

def remove_html_tags(text):
    if text is None:
        return ''
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

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
        vacancies = []
        for item in data['items']:
            # Убираем декорации текста
            description = remove_html_tags(item.get('snippet', {}).get('responsibility', ''))
            requirements = remove_html_tags(item.get('snippet', {}).get('requirement', ''))

            salary_info = item.get('salary')

            vacancies.append({
                'hh_id': item.get('id'),
                'title': item.get('name'),
                'link': item.get('alternate_url'),
                'employer': item.get('employer', {}).get('name'),
                'salary': salary_info if salary_info else {},
                'date_posted': item.get('published_at'),
                'description': description,
                'requirements': requirements
            })

        total_pages = data.get('pages', 1)
        return vacancies, total_pages
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return [], 0

# Функция для проверки количества вакансий в базе данных
def get_vacancies_count():
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM vacancies')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Функция для получения вакансий из базы данных с фильтрацией и сортировкой
def get_vacancies_from_db(sort_by=None, sort_order=None, filter_by=None, filter_value=None):
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
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

# Функция для разбиения списка вакансий на страницы.
def paginate_vacancies(vacancies, page=1, per_page=10):
    if not isinstance(page, int):
        raise TypeError(f"Expected 'page' to be int, got {type(page).__name__}")
    
    start = (page - 1) * per_page
    end = start + per_page
    return vacancies[start:end]

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Привет! Я бот для поиска вакансий на основе API hh.ru. Чтобы найти вакансии напиши или нажми /search, или же я могу работать с бд при помощи /job_database"
        )
    else:
        logger.warning("Update object does not contain a message.")

# Обработчик команды /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['first_search'] = True
    await update.message.reply_text("Введите название профессии для поиска:")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if context.user_data.get('expecting_job_title'):
        await handle_job_title(update, context)

    elif context.user_data.get('expecting_pages_count'):
        await handle_pages_count(update, context)

    elif context.user_data.get('filter_type'):
        await handle_filter_message(update, context)

    elif context.user_data.get('first_search'):
        job_title = update.message.text
        context.user_data['first_search'] = False
        await update.message.reply_text(f"Ищем вакансии подходящие к названию: {job_title}...")

        # Запускаем парсер для первой страницы
        vacancies, _ = fetch_job_listings(job_title, page=0)

        # Проверяем, успешно ли был выполнен парсинг
        if vacancies:
            # Сохраняем вакансии в БД
            context.user_data['job_title'] = job_title
            save_vacancies_to_db(vacancies)
            await update.message.reply_text("Вакансии найдены и сохранены в базе данных.")
            await show_vacancies(update, context, 1, job_title, action_type="show_vacancy", sort_type=None, sort_by=None, sort_order=None,
            filter_by=None, filter_value=None)
        else:
            await update.message.reply_text("Не удалось найти вакансии.")

async def handle_filter_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    filter_by = context.user_data.get('filter_type')
    filter_value = update.message.text
    context.user_data['filter_type'] = False

    job_title = ""
    await show_vacancies(update, context, 1, job_title, action_type="showFILTER", sort_type=None, sort_by=None, sort_order=None, 
                         filter_by=filter_by, filter_value=filter_value)

    

# Обработчик команды /job_database
async def job_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    count = get_vacancies_count()

    if count < 100:
        context.user_data['expecting_job_title'] = True
        # Запрашиваем наименование профессии
        await update.message.reply_text(f"В БД слишком мало вакансий, а именно: {count}. Требуется минимум 100, поэтому, пожалуйста, введите название профессии для поиска вакансий:")
    else:
        context.user_data['expecting_job_title'] = False
        await show_vacancies(update, context, 1, job_title=None, action_type="show", sort_type=None, sort_by=None, sort_order=None,
        filter_by=None, filter_value=None)

# Обработчик для получения названия профессии от пользователя
async def handle_job_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_job_title'):
        job_title = update.message.text
        context.user_data['job_title'] = job_title
        context.user_data['expecting_job_title'] = False
        await update.message.reply_text(f"Ищем вакансии подходящие к названию профессии: {job_title}...")

        # Запрашиваем количество страниц
        await update.message.reply_text("Введите количество страниц для загрузки (от 5 до 20 страниц, в странице по 10 вакансий):")
        context.user_data['expecting_pages_count'] = True

# Обработчик для получения количества страниц от пользователя
async def handle_pages_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_pages_count'):
        try:
            pages_count = int(update.message.text)
            if 5 <= pages_count <= 20:
                context.user_data['pages_count'] = pages_count
                job_title = context.user_data['job_title']

                # Запускаем парсинг вакансий с указанными параметрами
                for page in range(pages_count):
                    vacancies = parse_vacancies(job_title, page=page)
                    save_vacancies_to_db(vacancies)
                await update.message.reply_text(f"Загружено {pages_count} страниц вакансий.")

                # Переходим к следующему шагу
                del context.user_data['expecting_job_title']
                del context.user_data['expecting_pages_count']
                await show_vacancies(update, context, 1, job_title=None, action_type="show", sort_type=None, sort_by=None, 
                sort_order=None, filter_by=None, filter_value=None)
            else:
                await update.message.reply_text("Количество страниц должно быть от 5 до 20. Попробуйте еще раз.")
        except ValueError:
            await update.message.reply_text("Введите число.")

# Функция для отображения вакансий
async def show_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int, job_title: str, action_type,
 sort_type: str, sort_by: str = "title", sort_order: str = "asc", filter_by: str = "", filter_value: str = "") -> None:
    action_type = action_type

    if action_type in ['show_vacancy', 'next', 'prev', 'back']:
        vacancies = parse_vacancies(job_title, page)

        if vacancies:
            message = "Вакансии:\n"
            buttons = []

            for idx, vacancy in enumerate(vacancies, start=(page - 1) * 10 + 1):
                hh_id = vacancy['hh_id']
                buttons.append([InlineKeyboardButton(text=f"{str(idx)}. {vacancy['title']}", 
                callback_data=f"detail_{hh_id}_{page}_{job_title}")])

            buttons.append([InlineKeyboardButton(text="Следующая страница", 
            callback_data=f"next_{page+1}_{job_title}")])
            if page > 1:
                buttons.append([InlineKeyboardButton(text="Предыдущая страница", 
                callback_data=f"prev_{page-1}_{job_title}")])

            reply_markup = InlineKeyboardMarkup(buttons)
            query = update.callback_query
            if query:
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    if action_type in ['show', 'nextDB', 'prevDB', 'backDB']:
        job_title = None
        all_vacancies = get_vacancies_from_db()  # Получить полный список вакансий
        vacancies = paginate_vacancies(all_vacancies, page)  # Получить вакансии для текущей страницы

        if vacancies:
            message = "Вакансии:\n"
            buttons = []

            for idx, vacancy in enumerate(vacancies, start=(page - 1) * 10 + 1):
                hh_id = vacancy[0]
                buttons.append([InlineKeyboardButton(text=f"{str(idx)}. {vacancy[1]}", callback_data=f"detailDB_{hh_id}_{page}")])

            # Кнопки для пагинации
            if len(all_vacancies) > page * 10:
                buttons.append([InlineKeyboardButton(text="Следующая страница", callback_data=f"nextDB_{page+1}")])
            if page > 1:
                buttons.append([InlineKeyboardButton(text="Предыдущая страница", callback_data=f"prevDB_{page-1}")])
            
            # Кнопки для сортировки
            buttons.append([InlineKeyboardButton(text="Сортировать по зарплате", callback_data=f"sort_salary_{page}_asc")])
            buttons.append([InlineKeyboardButton(text="Сортировать по дате", callback_data=f"sort_date_{page}_asc")])
            buttons.append([InlineKeyboardButton(text="Поиск по фильтру", callback_data="filter")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            query = update.callback_query
            if query:
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    if action_type in ["sort", "nextSORT", "prevSORT", "backSORT"]:
        all_vacancies = get_vacancies_from_db(sort_by=sort_by, sort_order=sort_order)  # Получить полный список вакансий
        vacancies = paginate_vacancies(all_vacancies, page)  # Получить вакансии для текущей страницы

        if vacancies:
            message = "Вакансии:\n"
            buttons = []

            for idx, vacancy in enumerate(vacancies, start=(page - 1) * 10 + 1):
                hh_id = vacancy[0]
                buttons.append([InlineKeyboardButton(text=f"{str(idx)}. {vacancy[1]}", callback_data=f"detailSORT_{hh_id}_{page}_{sort_type}_{sort_by}_{sort_order}")])

            # Кнопки для пагинации
            if len(all_vacancies) > page * 10:
                buttons.append([InlineKeyboardButton(text="Следующая страница", 
                callback_data=f"nextSORT_{page+1}_{sort_type}_{sort_by}_{sort_order}")])
            if page > 1:
                buttons.append([InlineKeyboardButton(text="Предыдущая страница", 
                callback_data=f"prevSORT_{page-1}_{sort_type}_{sort_by}_{sort_order}")])
            
            # Кнопки для сортировки
            new_button_text = f"Сортировать по зарплате {'по убыванию' if sort_order == 'desc' else 'по возрастанию'}" if sort_by == "salary" else f"Сортировать по дате {'по убыванию' if sort_order == 'desc' else 'по возрастанию'}"
            buttons.append([InlineKeyboardButton(text=new_button_text, 
            callback_data=f"sort_{sort_type}_{page}_{sort_order}")])

            # Кнопка для сброса сортировки
            buttons.append([InlineKeyboardButton(text="Сброс сортировки", callback_data=f"show")])
                        
            
            reply_markup = InlineKeyboardMarkup(buttons)
            query = update.callback_query
            if query:
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    if action_type in ["nextFILTER", "prevFILTER", "backFILTER", "showFILTER"]:
        all_vacancies = get_vacancies_from_db(filter_by=filter_by, filter_value=filter_value)  # Получить полный список вакансий
        vacancies = paginate_vacancies(all_vacancies, page)  # Получить вакансии для текущей страницы

        if vacancies:
            message = "Вакансии:\n"
            buttons = []

            for idx, vacancy in enumerate(vacancies, start=(page - 1) * 10 + 1):
                hh_id = vacancy[0]
                buttons.append([InlineKeyboardButton(text=f"{str(idx)}. {vacancy[1]}", 
                callback_data=f"detailFILTER_{hh_id}_{page}_{filter_by}_{filter_value}")])

            # Кнопки для пагинации
            if len(all_vacancies) > page * 10:
                buttons.append([InlineKeyboardButton(text="Следующая страница", 
                callback_data=f"nextFILTER_{page+1}_{filter_by}_{filter_value}")])
            if page > 1:
                buttons.append([InlineKeyboardButton(text="Предыдущая страница", 
                callback_data=f"prevFILTER_{page-1}_{filter_by}_{filter_value}")])

            # Кнопка для сброса поиска по фильтру
            buttons.append([InlineKeyboardButton(text="Сброс поиска по фильтру", callback_data=f"filter")])
                        
            reply_markup = InlineKeyboardMarkup(buttons)
            query = update.callback_query
            if query:
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# Обработчик для inline-кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Ответ на callback, чтобы не появлялось предупреждение

    data = query.data.split("_")
    print(f"Received data: {data}")  # Временное логирование для диагностики

    action_type = data[0]
    try:
        if action_type in ['next', 'prev', 'back', 'nextDB', 'prevDB', 'backDB']:
            try:
                page = int(data[1])
                job_title = "_".join(data[2:])
                await show_vacancies(update, context, page, job_title, action_type, sort_type=None, sort_by=None, sort_order=None, 
                filter_by=None, filter_value=None)
            except (IndexError, ValueError):
                await query.edit_message_text(f"Некорректные данные для кнопки {action_type}.")

        elif action_type in ['nextSORT', 'prevSORT', 'backSORT']:
            try:
                page = int(data[1])
                sort_type = data[2]
                if data[3] == 'date':
                    sort_by = "date_posted"
                else:
                    sort_by = data[3]
                if data[4] == "posted":
                    sort_order = data[5]
                else:
                    sort_order = data[4]
                job_title = ""
                await show_vacancies(update, context, page, job_title, action_type, sort_type, sort_by, sort_order, 
                filter_by=None, filter_value=None)
            except (IndexError, ValueError):
                await query.edit_message_text(f"Некорректные данные для кнопки {action_type}.")

        elif action_type in ['nextFILTER', 'prevFILTER', 'backFILTER']:
            try:
                page = int(data[1])
                filter_by = data[2]
                filter_order = data[3]
                job_title = ""
                await show_vacancies(update, context, page, job_title, action_type, sort_type=None, sort_by=None, sort_order=None, 
                filter_by=filter_by, filter_value=filter_order)
            except (IndexError, ValueError):
                await query.edit_message_text(f"Некорректные данные для кнопки {action_type}.")
            
        elif action_type == "sort":
            try:
                sort_type = data[1]
                sort_order = data[3]
                job_title = ""
                
                if sort_type == "date":  # Обработка случая сортировки по дате
                    sort_by = "date_posted"
                else:  # Обработка случая сортировки по зарплате
                    sort_by = "salary"

                new_sort_order = "desc" if sort_order == "asc" else "asc"
                sort_order = new_sort_order
                await show_vacancies(update, context, 1, job_title, action_type, sort_type, sort_by, sort_order, 
                filter_by=None, filter_value=None)
            except (IndexError, ValueError) as e:
                await query.edit_message_text(f"Некорректные данные для кнопки {action_type}: {str(e)}.")
        
        elif action_type in ["detail", "detailDB"]:
            try:
                hh_id = data[1]
                page = int(data[2]) if len(data) > 2 else 1
                job_title = data[3] if len(data) > 3 else ""
                await show_vacancy_detail(update, context, hh_id, page, job_title, action_type, sort_type=None, sort_by=None, sort_order=None,
                filter_by=None, filter_value=None)
            except (IndexError, ValueError) as e:
                await query.edit_message_text(f"Некорректные данные для кнопки detail: {str(e)}")
        
        elif action_type == "detailSORT":
            try:
                hh_id = data[1]
                page = int(data[2]) if len(data) > 2 else 1
                job_title = ""
                sort_type = data[3]
                if data[4] == 'date':
                    sort_by = "date_posted"
                else:
                    sort_by = data[4]
                if data[5] == "posted":
                    sort_order = data[6]
                else:
                    sort_order = data[5]
                await show_vacancy_detail(update, context, hh_id, page, job_title, action_type, sort_type, sort_by, sort_order,
                filter_by=None, filter_value=None)
            except (IndexError, ValueError) as e:
                await query.edit_message_text(f"Некорректные данные для кнопки detail: {str(e)}")

        elif action_type == "detailFILTER":
            try:
                hh_id = data[1]
                page = int(data[2]) if len(data) > 2 else 1
                job_title = ""
                sort_type = None
                sort_by = None
                sort_order = None
                filter_by = data[3]
                filter_value = data[4]
                await show_vacancy_detail(update, context, hh_id, page, job_title, action_type, sort_type, sort_by, sort_order,
                filter_by, filter_value)
            except (IndexError, ValueError) as e:
                await query.edit_message_text(f"Некорректные данные для кнопки detail: {str(e)}")
            

        elif action_type == "filter":
            buttons = [
                [InlineKeyboardButton(text="По названию", callback_data="filter-title")],
                [InlineKeyboardButton(text="По описанию", callback_data="filter-description")],
                [InlineKeyboardButton(text="Назад", callback_data=f"show")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            if query.message.text != "Выберите параметр для фильтрации:" or query.message.reply_markup.inline_keyboard != reply_markup.inline_keyboard:
                await query.edit_message_text("Выберите параметр для фильтрации:", reply_markup=reply_markup)
            else:
                await query.answer("Сообщение и разметка не изменились", show_alert=True)

        elif action_type in ["filter-title", "filter-description"]:
            context.user_data['filter_type'] = action_type.split("-")[1]
            new_message = "Введите ключевое слово для фильтрации по названию:" if context.user_data['filter_type'] == 'title' else "Введите ключевое слово для фильтрации по описанию:"
            if query.message.text != new_message:
                await query.edit_message_text(new_message)
            else:
                await query.answer("Сообщение не изменилось", show_alert=True)

        elif action_type == "show":
            try:
                job_title = ""
                await show_vacancies(update, context, 1, job_title, action_type, sort_type=None, sort_by=None, sort_order=None,
                filter_by=None, filter_value=None)
            except (IndexError, ValueError) as e:
                await query.edit_message_text(f"Некорректные данные для кнопки show: {str(e)}")
        
        else:   
            await query.edit_message_text(f"Неизвестный тип действия: {action_type}.")

    except Exception as e:
        print(f"Error: {e}")
        await query.edit_message_text(f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте еще раз.")  

# Функция для отображения подробной информации о вакансии
async def show_vacancy_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, hh_id: str, page: int, job_title: str, action_type: str,
 sort_type: str, sort_by: str, sort_order: str, filter_by: str, filter_value: str) -> None:
    query = update.callback_query
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

    action_type = action_type
    sort_type = sort_type
    sort_by = sort_by
    sort_order = sort_order

    if vacancy:
        title, link, employer, salary, date_posted, description, requirements = vacancy
        salary_info = salary
        
        # Форматируем информацию о зарплате
        if salary_info:
            if salary_info.get('from') and salary_info.get('currency'):
                salary_text = f"От {salary_info['from']} {salary_info['currency']}"
            else:
                salary_text = "Не указана"
        else:
            salary_text = "Не указана"

        message = f"*{title}*\n\n"
        message += f"*Компания:* {employer}\n"
        message += f"*Зарплата:* {salary_text}\n"
        message += f"*Дата публикации:* {date_posted}\n\n"
        message += f"*Описание:*\n{description}\n\n"
        message += f"*Требования:*\n{requirements}\n\n"

        buttons = [[InlineKeyboardButton(text="Ссылка на вакансию", url=link)]]
        if action_type == "detail":
            buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"back_{page}_{job_title}")])
        elif action_type == "detailDB":
            buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"backDB_{page}_{job_title}")])
        elif action_type == "detailSORT":
            buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"backSORT_{page}_{sort_type}_{sort_by}_{sort_order}")])
        elif action_type == "detailFILTER":
            buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"backFILTER_{page}_{filter_by}_{filter_value}")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await query.edit_message_text("Вакансия не найдена.")

def parse_vacancies(job_title, page=0):
    try:
        # Получаем список вакансий
        vacancies, _ = fetch_job_listings(job_title, page)

        # Сохраняем вакансии в БД
        save_vacancies_to_db(vacancies)

        print(f"Fetched and saved {len(vacancies)} vacancies.")
        return vacancies
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return []

def main() -> None:
    application = ApplicationBuilder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("job_database", job_database))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
