import os
from xml import etree

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import configparser
import re

import telebot

from google_drive import upload_to_google_drive
from google_sheets import addSpreadsheet
from sql import get_user_settings

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
# bot = telebot.TeleBot(token)  # Создаем экземпляр бота с указанным токеном

from google_service import get_google_service

# Функция для классификации метаданных
def classify_metadata(metadata):
    if 'http://calibre.kovidgoyal.net/2009/metadata' in metadata:
        return "type_1"
    elif 'http://purl.org/dc/elements/1.1/' in metadata and 'rights' in metadata['http://purl.org/dc/elements/1.1/']:
        return "type_2"
    else:
        return "unknown"



def readBook(BookName):
    book = epub.read_epub(BookName)
    data = []

    # Получаем метаданные

    # Классифицируем тип данных
    metadata_type = classify_metadata(book.metadata)
    print(metadata_type)
    # Используем match-case для обработки различных типов данных
    match metadata_type:
        case "type_1":
            data = process_type_1(book)
            # Обработка первого типа
            # data = process_type_1(book, data)
        case "type_2":
            # Обработка второго типа
            data = process_type_2(book)
        case _:
            print("Неизвестный тип данных.")

    return data

def process_type_2(book):
    data = []

    print(classify_metadata(book.metadata))

    info = book.get_metadata('DC', 'title')

    if info:
        data.append(info[0][0])

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
                fandom_text = re.sub(r'Сакавич Нора «Все ради игры»', 'All for the game', fandom_text)

                data.append(fandom_text)

            status = soup.find('b', string='Статус:')
            if status:
                status_text = status.find_next_sibling(string=True).strip()
                data.append(status_text)

            link = soup.find('a')
            if link and link.get('href'):
                data.append(link.get('href'))

            print(data)
            return data


def extract_link_from_text(text):
    # Ищем ссылку, которая начинается с "http" и заканчивается на символ, не являющийся пробелом или символом ">"
    link = re.search(r'http[s]?://[^\s"<>]+/works/\d+', text)
    if link:
        return link.group(0)
    else:
        return 'Ссылка не найдена'

def extract_fandom_from_text(text):
    # Очищаем текст от HTML-тегов
    soup = BeautifulSoup(text, 'html.parser')
    fandom_text = soup.get_text()

    # Используем регулярное выражение для поиска фандома
    fandom_match = re.search(r'Fandom:\s*([^\n]+)', fandom_text)
    if fandom_match:
        return fandom_match.group(1).strip()  # Убираем лишние пробелы по краям
    return 'Фандом не найден'

def process_type_1(book):
    data = []

    # 1. Записываем название произведения
    if 'http://purl.org/dc/elements/1.1/' in book.metadata:
        metadata = book.metadata['http://purl.org/dc/elements/1.1/']
        if 'title' in metadata and len(metadata['title']) > 0:
            title = metadata['title'][0][0]
            print(title)  # Выводим название для проверки
            data.append(title)

    # 2. Добавляем пустую строку в data[1]
    data.append('')

    # 3. Извлекаем фандом из текста
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_body_content().decode('utf-8')  # Преобразуем в строку
            fandom = extract_fandom_from_text(content)
            fandom = re.sub(r'All For The Game - Nora Sakavic', 'All for the game', fandom)

            data.append(fandom)
            break  # Прерываем, как только нашли фандом

    # 4. Проверяем статус "завершён" или "в процессе" по главам
    chapter_status = "в процессе"
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_body_content()
            soup = BeautifulSoup(content, 'html.parser')
            chapter_tag = soup.find('p', string=re.compile(r'Chapters?:\s*\d+/(\d+)'))
            if chapter_tag:
                # Проверяем количество глав (например, 136/?)
                chapter_info = chapter_tag.string.split(':')[1].strip()
                total_chapters = chapter_info.split('/')
                if len(total_chapters) == 2 and total_chapters[0] == total_chapters[1]:
                    chapter_status = "завершён"
                    break

    data.append(chapter_status)  # Записываем статус

    # 5. Извлекаем ссылку из текста
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_body_content().decode('utf-8')  # Преобразуем в строку
            link = extract_link_from_text(content)
            data.append(link)
            break  # Выходим, после того как нашли первую ссылку

    return data


def extract_preface_chapter(book):
    # Попытка найти первую главу "Preface"
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_body_content()
            soup = BeautifulSoup(content, 'html.parser')
            preface_chapter = soup.find('h1', string='Preface')
            if preface_chapter:
                return preface_chapter.find_next('p').get_text()  # Возвращаем текст после заголовка "Preface"
    return 'Preface не найдена'


def document(message):
    need = get_user_settings(message)
    if message.document.mime_type == 'application/epub+zip' and (need[0]!='' and need[1]!=1):  # Проверяем, что тип файла - EPUB
        file_info = bot.get_file(message.document.file_id)  # Получаем информацию о файле
        my_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)  # Определяем путь для сохранения файла
        path = os.path.join(ANOTHER, message.document.file_name)  # Определяем путь для сохранения файла

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
                        addSpreadsheet(service, book_data, need[0], need[1], drive_file_id)
                        bot.send_message(message.chat.id, f"Я всё сделал хозяюшка. \nДобавил: {book_data[0]}")
                    else:
                        bot.send_message(message.chat.id, "Ошибка при загрузке файла на Google Диск.")
            else:
                bot.send_message(message.chat.id, "Не удалось извлечь данные из книги.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")

    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте файл .epub.")
