from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup
import requests

# Токен от чат бота (Скрою для конфиденциальности)
telegram_bot_token = "your_token"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    # Добавляем кнопки поиска по вакансии и ризюме
    button = [
        [
            InlineKeyboardButton('Поиск по вакансии', callback_data='search_job'),
            InlineKeyboardButton('Поиск по ризюме', callback_data='search_resume')
        ]
    ]

    # Инициируем кнопки
    reply_markup = InlineKeyboardMarkup(button)

    # Указываем приветственное сообщение при запуске
    await update.message.reply_text('Привет, я бот по поиску вакансий или резюме на основе сайта hh.ru, для продолжения, пожалуйста, выберите нужную кнопку:', reply_markup=reply_markup)

async def button_upd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    query = update.callback_query
    query.answer()

    if query.data == 'search_job':
        await query.edit_message_text(text="Вы выбрали поиск по вакансии.")
    elif query.data == 'search_resume':
        await query.edit_message_text(text="Вы выбрали поиск по резюме.")   
    

if __name__ == '__main__':

    from telegram.ext import ApplicationBuilder
    import asyncio

    application = ApplicationBuilder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_upd))

    application.initialize()
    application.run_polling()
    
