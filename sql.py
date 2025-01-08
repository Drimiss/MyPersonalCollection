import configparser
import re
import sqlite3

import telebot

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

token = config.get('bot', 'token')
admin = config.get('bot', 'AUTHORIZED_CHAT_ID')
bot = telebot.TeleBot(token)  # Создаем экземпляр бота с указанным токеном


def add_new_user(chat_id):
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()

    # Проверяем, существует ли уже запись с таким chat_id
    cursor.execute("SELECT * FROM Users WHERE chat = ?", (chat_id,))
    existing_user = cursor.fetchone()

    # Если пользователя нет в базе, добавляем его
    if not existing_user:
        cursor.execute("INSERT INTO Users (chat, exelId, mainList) VALUES (?, '', '')", (chat_id,))
        print(f"Пользователь с chat.id {chat_id} успешно добавлен!")
    else:
        print(f"Пользователь с chat.id {chat_id} уже существует!")

    conn.commit()
    conn.close()


# Функция для инициализации базы данных и добавления пользователя
def init_db():
    # Подключаемся к базе данных (если базы данных нет, она будет создана)
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()

    # Создаем таблицу Users, если она еще не существует
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY,
        chat INTEGER NOT NULL,
        exelId TEXT NOT NULL DEFAULT '',
        mainList TEXT NOT NULL DEFAULT ''
    )
    ''')

    # Сохраняем изменения и закрываем соединение
    conn.commit()
    conn.close()


def connect_db():
    conn = sqlite3.connect('example.db')  # Укажите путь к вашей базе данных
    cursor = conn.cursor()
    return conn, cursor


def update_db(chat_id, exelId=None, mainList=None):
    conn, cursor = connect_db()

    # Если exelId передан, обновим exelId
    if exelId:
        cursor.execute("UPDATE Users SET exelId = ? WHERE chat = ?", (exelId, chat_id))

    # Если mainList передан, обновим mainList
    if mainList:
        cursor.execute("UPDATE Users SET mainList = ? WHERE chat = ?", (mainList, chat_id))

    conn.commit()
    conn.close()


def update_spreadsheet(message):
    try:
        chat_id = message.chat.id
        url = message.text  # Получаем новый exelId от пользователя
        match = re.search(r'/d/([^/]+)/edit', url)
        if match:
            new_exelId = match.group(1)
            update_db(chat_id, exelId=new_exelId)
            bot.send_message(chat_id, "Excel успешно обновлен!")
        else:
            # Если регулярное выражение не сработало
            raise ValueError(
                "Неверная ссылка Excel")  # Это можно сделать, чтобы вызвать ошибку, если формат ссылки неверный
    except Exception as e:
        # Логирование ошибки (если нужно)
        print(f"Error: {e}")
        bot.send_message(chat_id, "Что-то не так. Пожалуйста, отправьте правильную ссылку на Excel.")


def update_sheet_name(message):
    chat_id = message.chat.id
    new_mainList = message.text  # Получаем новое название основного листа от пользователя

    update_db(chat_id, mainList=new_mainList)


def update_user_data(chat_id, column_name, new_value):
    """Функция для универсального обновления данных пользователя в базе данных"""
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()

    # Формируем SQL запрос с подставленным именем столбца и значением
    query = f"UPDATE Users SET {column_name} = ? WHERE chat = ?"

    # Выполняем запрос
    cursor.execute(query, (new_value, chat_id))
    conn.commit()
    conn.close()


def get_user_settings(message):
    try:
        chat_id = message.chat.id
        # Подключаемся к базе данных SQLite
        connection = sqlite3.connect('example.db')  # Укажите путь к вашей БД
        cursor = connection.cursor()

        # Выполняем запрос для получения exelId и mainList для указанного chat_id
        cursor.execute("SELECT exelId, mainList FROM Users WHERE chat = ?", (chat_id,))  # Используем параметр chat_id

        # Извлекаем все строки с результатами
        rows = cursor.fetchall()

        # Возвращаем список кортежей (exelId, mainList)
        result = []
        for row in rows:
            result.append(row[0])  # Добавляем exelId
            result.append(row[1])  # Добавляем mainList

        return result

    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
        return []

    finally:
        if connection:
            connection.close()


def get_user_settings2(chat_id):
    try:

        # Подключаемся к базе данных SQLite
        connection = sqlite3.connect('example.db')  # Укажите путь к вашей БД
        cursor = connection.cursor()

        # Выполняем запрос для получения exelId и mainList для указанного chat_id
        cursor.execute("SELECT exelId, mainList FROM Users WHERE chat = ?", (chat_id,))  # Используем параметр chat_id

        # Извлекаем все строки с результатами
        rows = cursor.fetchall()

        # Возвращаем список кортежей (exelId, mainList)
        result = []
        for row in rows:
            result.append(row[0])  # Добавляем exelId
            result.append(row[1])  # Добавляем mainList

        return result

    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
        return []

    finally:
        if connection:
            connection.close()
