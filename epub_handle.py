import os

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import configparser
import re

import telebot

from google_drive import upload_to_google_drive
from google_sheets import updateSpreadsheet
from sql import get_user_settings
import warnings

# Отключить все предупреждения
warnings.filterwarnings("ignore")


UPLOAD_FOLDER = "uploads"# Папка для загрузок
ANOTHER = "other"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Создаем папку, если она не существует

if not os.path.exists(ANOTHER):
    os.makedirs(ANOTHER)

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

token = config.get('bot', 'token')
admin = config.get('bot', 'AUTHORIZED_CHAT_ID')
CREDENTIALS_FILE = config.get('google', 'CREDENTIALS_FILE')
FOLDER_ID = config.get('google', 'FOLDER_ID')
EMAIL_TO_SHARE = config.get('google', 'EMAIL_TO_SHARE')
bot = telebot.TeleBot(token)  # Создаем экземпляр бота с указанным токеном

from google_service import get_google_service


def readBook(BookName):
    book = epub.read_epub(BookName)
    data = []

    metadata = book.get_metadata('DC', 'title')
    if metadata:
        data.append(metadata[0][0])

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT and item.get_name() == 'title.xhtml':
            content = item.get_content()
            soup = BeautifulSoup(content, 'html.parser')

            size_label = soup.find('b', string='Размер:')
            if size_label:
                size_text = size_label.find_next_sibling(string=True).strip()
                size = re.search(r'\d[\d\s]*', size_text).group().replace(' ', '')
                data.append(size)

            fandom_label = soup.find('b', string='Фэндом:')
            if fandom_label:
                fandom_text = fandom_label.find_next_sibling(string=True).strip()
                fandom_text = re.sub(r'\(кроссовер\)', '', fandom_text)
                fandom_text = re.sub(r'Сакавич Нора «Все ради игры».*?[,)]', 'All for the game', fandom_text)

                data.append(fandom_text)

            status = soup.find('b', string='Статус:')
            if status:
                status_text = status.find_next_sibling(string=True).strip()
                data.append(status_text)

            link = soup.find('a')
            if link and link.get('href'):
                data.append(link.get('href'))

            return data


def document(message):
    if message.document.mime_type == 'application/epub+zip':  # Проверяем, что тип файла - EPUB
        file_info = bot.get_file(message.document.file_id)  # Получаем информацию о файле
        my_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)  # Определяем путь для сохранения файла
        path = os.path.join(ANOTHER, message.document.file_name)  # Определяем путь для сохранения файла
        need = get_user_settings(message)

        try:
            # Загружаем файл из Telegram
            if str(message.chat.id).strip() == str(admin).strip():
                file_path = my_path
                response = bot.download_file(file_info.file_path)
                with open(file_path, 'wb') as file:
                    file.write(response)  # Сохраняем файл на диск
                book_data = readBook(file_path)
            else:
                file_path = path
                response = bot.download_file(file_info.file_path)
                with open(file_path, 'wb') as file:
                    file.write(response)  # Сохраняем файл на диск
                book_data = readBook(file_path)

            # Читаем EPUB файл
            if book_data:
                # Проверяем, существует ли книга в Google Sheets
                service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                              'https://www.googleapis.com/auth/drive'])
                from google_sheets import is_record_exists
                if is_record_exists(service, need[1], need[0], book_data[0]):
                    bot.send_message(message.chat.id, f"Уже есть такой, сорри. \nУже добавляли: \"{book_data[0]}\"")
                else:
                    # Загружаем файл на Google Drive и обновляем Google Sheets
                    drive_service = get_google_service('drive', 'v3', ['https://www.googleapis.com/auth/drive.file'])
                    drive_file_id = upload_to_google_drive(drive_service, file_path, EMAIL_TO_SHARE, FOLDER_ID)
                    if drive_file_id:
                        updateSpreadsheet(service, book_data, need[0], need[1], drive_file_id)
                        bot.send_message(message.chat.id, f"Я всё сделал хозяюшка. \nДобавил: {book_data[0]}")
                    else:
                        bot.send_message(message.chat.id, "Ошибка при загрузке файла на Google Диск.")
            else:
                bot.send_message(message.chat.id, "Не удалось извлечь данные из книги.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте файл .epub.")
