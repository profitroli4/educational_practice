FROM python:3.11

WORKDIR /telegram_bot

EXPOSE 8008

COPY /requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "telegram_bot.py" ]

