# Телеграмм бот для парсинга вакансий

## Описание
### Этот проект основанный на телеграмм боте предлагает возможность взаимодействия с API HeadHunter и сохранения в базе данных PostgreSQL. Телеграмм бот предоставляет интерфейс для поиска и взаимодействия с вакансиями.

# Возможности бота
 + Извлечение вакансий из API HeadHunter на основе заданной профессии.
 + Хранение данных в базе данных
 + Работа с базой данных а именно:
    + Сортировка по дате
    + Сортировка по зарплате
    + Поиск по фильтру в названии
    + Поиск по фильтру в описании
 + Взаимодействие с пользователем в телеграмме

# Структура проекта
```
educational-practice/
|
├── init_db/
|    ├── Dockerfile
|    ├── init_db.py
|    └── requirements.txt
├── telegram_bot/
|    ├── Dockerfile
|    ├── telegram_bot.py
|    └── requirements.txt
├── docker-compose.yml
└── README.md
```

# Приступая к работе

## Предварительные требования
 + Docker
 + Создание докера

## Установка
 + Клонировать репозиторий
 ```
 git clone https://github.com/danilprofiru/educational_practice.git
 cd educational-practice
 ```
## Настройка телеграмм бота
 + Создайте бота при помощи https://t.me/BotFather
 + Скопируйте token
 + Создайте файл .env в папке src
 + Вставьте туда TELEGRAM_BOT_TOKEN=ваш токен

## Использование, сборка и запуск контейнеров Docker
```
docker-compose build
docker-compose up
```

После запуска докера, вы можете отправить запрос вашему телеграмм боту, а так же воспользоваться adminer для просмотра базы данных.

## Комманды
 + /start - запуск бота
 + /search - парсинг вакансий по наименованию
 + /job_database - работа с вакансиями из бд

# Лицензия
 Этот проект лицензирован по лицензии MIT - подробности смотрите в файле ЛИЦЕНЗИИ.