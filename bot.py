import os  # Импортируем модуль для работы с файловой системой

import gspread
import telebot  # Импортируем модуль для работы с Telegram Bot API
from telebot import types  # Импортируем классы для создания кнопок и клавиатур в Telegram
from google_service import get_google_service  # Импортируем функцию для получения сервиса Google API
from google_drive import upload_to_google_drive  # Импортируем функцию для загрузки файлов на Google Drive
from google_sheets import is_record_exists, updateSpreadsheet  # Импортируем функции для работы с Google Sheets
from epub_handle import readBook  # Импортируем функцию для чтения EPUB файлов
import re
import configparser

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

token = config.get('bot', 'token')
CREDENTIALS_FILE = config.get('google','CREDENTIALS_FILE')
SPREADSHEET_ID = config.get('google', 'SPREADSHEET_ID')
SHEET_NAME = config.get('google', 'SHEET_NAME')
FOLDER_ID = config.get('google', 'FOLDER_ID')
EMAIL_TO_SHARE = config.get('google', 'EMAIL_TO_SHARE')

ITEMS_PER_PAGE = 4

bot = telebot.TeleBot(token)  # Создаем экземпляр бота с указанным токеном
user_data = {}  # Словарь для хранения состояний пользователей

UPLOAD_FOLDER = "uploads"  # Папка для загрузок
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Создаем папку, если она не существует


# Устанавливаем команды, которые будут отображаться в меню
def set_bot_commands():
    commands = [
        telebot.types.BotCommand('/start', 'Начать работу с ботом'),
        telebot.types.BotCommand('/search', 'Поиск фанфиков'),
        telebot.types.BotCommand('/update', 'Обновить информацию о фанфике'),
        telebot.types.BotCommand('/del', 'Удалить существующие названия')
    ]
    bot.set_my_commands(commands)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id,
                     "Привет, я бот, который поможет следить тебе за потребляемым контенотом. Просто отправь мне файл .epub")

# Функция для нормализации заголовков
def normalize_title(title):
    normalized = title.strip().lower()
    normalized = re.sub(r'\[.*?\]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'\s+', '', normalized)
    return normalized

def delete_existing_titles(service, spreadsheet_id):
    try:
        # Получаем названия из листа Library
        library_response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'Library!B4:B'
        ).execute()
        library_titles = [normalize_title(row[0]) for row in library_response.get('values', []) if row]

        def remove_titles_from_sheet(sheet_name):
            # Получаем названия из указанного листа
            sheet_response = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f'{sheet_name}!B4:B'
            ).execute()
            sheet_titles = [row[0] for row in sheet_response.get('values', []) if row]

            # Удаляем названия, которые уже есть в Library
            updated_titles = [[title] for title in sheet_titles if normalize_title(title) not in library_titles]

            # Обновляем лист
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f'{sheet_name}!B4:B'
            ).execute()
            if updated_titles:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f'{sheet_name}!B4',
                    valueInputOption='RAW',
                    body={'values': updated_titles}
                ).execute()

        # Удаляем названия из листов "ФФ ВРИ" и "Минсоны"
        remove_titles_from_sheet('ФФ ВРИ')
        remove_titles_from_sheet('Минсоны')

    except Exception as e:
        print(f"Произошла ошибка: {e}")


@bot.message_handler(commands=['del'])
def handle_del(message):
    try:
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets'])
        delete_existing_titles(service, SPREADSHEET_ID)
        bot.send_message(message.chat.id, "Удаление завершено успешно, пустые строки удалены.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


@bot.message_handler(commands=['search'])
def handle_search(message):
    try:
        # Подключаемся к Google Sheets
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])

        # Получаем названия всех листов в таблице
        sheets_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_names = [sheet['properties']['title'] for sheet in sheets_metadata['sheets']]

        # Исключаем лист "Library" из поиска
        sheet_names.remove(SHEET_NAME)

        # Создаем инлайн-кнопки для каждого листа
        inline_markup = types.InlineKeyboardMarkup()
        for sheet_name in sheet_names:
            inline_markup.add(types.InlineKeyboardButton(text=sheet_name, callback_data=f"sheet_{sheet_name}"))

        # Отправляем инлайн-кнопки пользователю
        bot.send_message(message.chat.id, "Выберите лист для просмотра:", reply_markup=inline_markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при получении листов: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("sheet_"))
def handle_sheet_selection(call):
    sheet_name = call.data[len("sheet_"):]
    try:
        # Подключаемся к Google Sheets
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])

        # Получаем данные из указанного диапазона на выбранном листе
        response = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!B4:B'
        ).execute()

        # Извлекаем фанфики и форматируем их в виде ('name')
        fanfics = [f"`{row[0]}`" for row in response.get('values', []) if row]

        if fanfics:
            # Формируем текст для сообщения
            message_text = "На этом листе:\n" + "\n".join(fanfics[:100])  # Display up to 100 items
        else:
            message_text = "Нет фанфиков на этом листе."

        # Редактируем сообщение с использованием Markdown
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=message_text,
                              parse_mode='Markdown')

    except Exception as e:
        bot.send_message(call.message.chat.id, f"Произошла ошибка: {e}")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.document.mime_type == 'application/epub+zip':  # Проверяем, что тип файла - EPUB
        file_info = bot.get_file(message.document.file_id)  # Получаем информацию о файле
        file_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)  # Определяем путь для сохранения файла

        try:
            # Загружаем файл из Telegram
            response = bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as file:
                file.write(response)  # Сохраняем файл на диск

            # Читаем EPUB файл
            book_data = readBook(file_path)
            if book_data:
                # Проверяем, существует ли книга в Google Sheets
                service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                              'https://www.googleapis.com/auth/drive'])
                if is_record_exists(service, SHEET_NAME, SPREADSHEET_ID, book_data[0]):
                    bot.send_message(message.chat.id, f"Уже есть такой, сорри. \nУже добавляли: \"{book_data[0]}\"")
                else:
                    # Загружаем файл на Google Drive и обновляем Google Sheets
                    drive_service = get_google_service('drive', 'v3', ['https://www.googleapis.com/auth/drive.file'])
                    drive_file_id = upload_to_google_drive(drive_service, file_path, EMAIL_TO_SHARE, FOLDER_ID)
                    if drive_file_id:
                        updateSpreadsheet(service, book_data, SPREADSHEET_ID, SHEET_NAME, drive_file_id)
                        bot.send_message(message.chat.id, f"Я всё сделал хозяюшка. \nДобавил: {book_data[0]}")
                    else:
                        bot.send_message(message.chat.id, "Ошибка при загрузке файла на Google Диск.")
            else:
                bot.send_message(message.chat.id, "Не удалось извлечь данные из книги.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте файл .epub.")

# Получение названий листов в Google Sheets
def get_sheets_titles(service, spreadsheet_id):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', [])
    sheet_titles = [sheet['properties']['title'] for sheet in sheets]
    sheet_id = [sheet['properties']['sheetId'] for sheet in sheets]
    return sheet_titles, sheet_id

@bot.message_handler(commands=['update'])
def handle_update(message):
    bot.send_message(message.chat.id, "Выберите лист, в котором хотите искать:")

    # Подключаемся к Google Sheets
    service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                  'https://www.googleapis.com/auth/drive'])

    # Получаем названия листов
    sheet_titles, sheet_ids = get_sheets_titles(service, SPREADSHEET_ID)

    # Создаем инлайн-кнопки с названиями листов
    inline_markup = types.InlineKeyboardMarkup()
    i = 0
    for title in sheet_titles:
        inline_markup.add(types.InlineKeyboardButton(text=title, callback_data=f"sheetUp_{str(sheet_ids[i])}"))
        i += 1

    # Отправляем инлайн-кнопки пользователю
    bot.send_message(message.chat.id, "Выберите лист:", reply_markup=inline_markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sheetUp_'))
def handle_sheet_selection(call):
    selected_sheet = call.data[len('sheetUp_'):]  # Получаем выбранное название листа
    chat_id = call.message.chat.id
    # Подключаемся к Google Sheets
    service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                  'https://www.googleapis.com/auth/drive'])

    # Получаем названия листов
    sheet_titles, sheet_ids = get_sheets_titles(service, SPREADSHEET_ID)
    for i in range(0, len(sheet_ids)):
        if int(sheet_ids[i]) == int(selected_sheet):
            selected_sheet_title = sheet_titles[i]
            break
    # Инициализируем 'titles_mapping' для пользователя
    user_data[chat_id] = {'selected_sheet': selected_sheet_title, 'titles_mapping': {}}

    bot.send_message(call.message.chat.id, f"Вы выбрали лист: {selected_sheet_title}. Начинаем вывод данных.")

    # Подключаемся к Google Sheets
    service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                  'https://www.googleapis.com/auth/drive'])

    # Читаем данные из выбранного листа
    response = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{selected_sheet_title}!B4:B'
    ).execute()
    values = response.get('values', [])  # Получаем значения из ответа

    if values:
        # Сохраняем фанфики и создаем titles_mapping
        titles_mapping = {}
        for row in values:
            if row:  # Проверяем, что строка не пустая
                full_title = row[0]
                truncated_title = full_title[:15] + '...' if len(full_title) > 15 else full_title
                titles_mapping[truncated_title] = full_title

        user_data[chat_id]['all_fanfics'] = values
        user_data[chat_id]['titles_mapping'] = titles_mapping  # Сохраняем маппинг
        user_data[chat_id]['current_page'] = 0
        ask_for_fanfic_title(call.message.chat.id)
    else:
        bot.send_message(call.message.chat.id, "Данные не найдены.")

# Отправка данных с пагинацией
def ask_for_fanfic_title(chat_id):
    # Запрашиваем у пользователя название для поиска
    msg = bot.send_message(chat_id, "Введите часть названия фанфика:")
    bot.register_next_step_handler(msg, process_fanfic_title)

def process_fanfic_title(message):
    chat_id = message.chat.id
    text = message.text.lower()  # Приводим текст к нижнему регистру для сравнения
    user_data[chat_id]['search_text'] = text  # Сохраняем текст в данных пользователя
    # Теперь вызываем функцию для отображения только тех фанфиков, которые соответствуют поиску
    send_fanfics_page(chat_id)

def send_fanfics_page(chat_id):
    fanfics = user_data[chat_id].get('all_fanfics', [])
    current_page = user_data[chat_id].get('current_page', 0)
    text = user_data[chat_id].get('search_text', '').lower()  # Получаем текст для поиска и приводим к нижнему регистру

    # Фильтруем фанфики, которые удовлетворяют условию (поисковому запросу)
    filtered_fanfics = [row for row in fanfics if text in row[0].lower()]

    if not filtered_fanfics:
        bot.send_message(chat_id, "Не найдено ни одного фанфика, соответствующего вашему запросу.")
        return

    # Вычисляем начальный и конечный индекс для отображения
    start_index = current_page * ITEMS_PER_PAGE
    end_index = min(start_index + ITEMS_PER_PAGE, len(filtered_fanfics))

    # Берем только текущие фанфики на странице
    current_page_fanfics = filtered_fanfics[start_index:end_index]

    # Создаем инлайн-кнопки для текущей страницы
    message_text = "Найденные фанфики:"
    inline_markup = types.InlineKeyboardMarkup()

    for idx, row in enumerate(current_page_fanfics):
        title = row[0] if row else "Без названия"
        inline_markup.add(types.InlineKeyboardButton(text=title[:15] + '...' if len(title) > 15 else title,
                                                     callback_data=f"fanfic_{start_index + idx}"))

    # Добавляем кнопки навигации, если нужно
    navigation_buttons = []
    if start_index > 0:
        navigation_buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{current_page - 1}"))
    if end_index < len(filtered_fanfics):
        navigation_buttons.append(
            types.InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"page_{current_page + 1}"))
    if navigation_buttons:
        inline_markup.row(*navigation_buttons)

    # Отправляем сообщение с инлайн-кнопками
    if 'message_id' in user_data[chat_id]:
        # Обновляем существующее сообщение
        bot.edit_message_text(chat_id=chat_id, message_id=user_data[chat_id]['message_id'], text=message_text,
                              reply_markup=inline_markup)
    else:
        # Отправляем новое сообщение
        message = bot.send_message(chat_id, message_text, reply_markup=inline_markup)
        user_data[chat_id]['message_id'] = message.message_id


# Обработка нажатий на кнопки пагинации
@bot.callback_query_handler(func=lambda call: call.data.startswith('page_'))
def handle_pagination(call):
    chat_id = call.message.chat.id
    new_page = int(call.data[len('page_'):])  # Получаем новую страницу
    user_data[chat_id]['current_page'] = new_page  # Обновляем текущую страницу
    send_fanfics_page(chat_id)  # Отправляем новую страницу данных

# Обработчики действий
@bot.callback_query_handler(func=lambda call: call.data.startswith('fanfic_'))
def handle_fanfic_selection(call):
    chat_id = call.message.chat.id
    truncated_title = int(call.data[7:])  # Извлекаем обрезанный заголовок
    k = truncated_title % ITEMS_PER_PAGE
    selected_fanfic = call.json['message']['reply_markup']['inline_keyboard'][k][0]['text']
    if selected_fanfic:
        send_fanfic_selection_message(chat_id, selected_fanfic)
    else:
        bot.send_message(chat_id, "Не удалось найти полное название фанфика.")


def send_fanfic_selection_message(chat_id, selected_fanfic):
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sheet = user_data[chat_id]['selected_sheet']
    # Открываем таблицу по ее ID и выбираем нужный лист
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(sheet)
    cell = worksheet.find(user_data[chat_id]['titles_mapping'][selected_fanfic])
    row = cell.row
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(
        types.InlineKeyboardButton(text="Прочитано", callback_data=f"read_{row}"),
        types.InlineKeyboardButton(text="Назад", callback_data="back")
    )
    name = user_data[chat_id]['titles_mapping'][selected_fanfic]
    bot.send_message(chat_id, f"Вы выбрали: {name}", reply_markup=inline_markup)


# Обработка нажатия на кнопку "Прочитано"
@bot.callback_query_handler(func=lambda call: call.data.startswith('read_'))
def handle_fanfic_read(call):
    chat_id = call.message.chat.id
    selected_fanfic = call.data[len('read_'):]  # Получаем строку выбранного фанфика
    # Отправляем меню для оценки фанфика
    send_rating_menu(chat_id, selected_fanfic)


# Функция отправки меню для оценки фанфика
def send_rating_menu(chat_id, selected_fanfic):
    rating_markup = types.InlineKeyboardMarkup()
    name = user_data[chat_id]['all_fanfics'][int(selected_fanfic)-4]
    for i in range(1, 6):
        stars = '⭐' * i
        rating_markup.add(types.InlineKeyboardButton(text=stars, callback_data=f"rate_{selected_fanfic}_{i}"))
    bot.send_message(chat_id, "Оцените произведение:", reply_markup=rating_markup)


# Обработка оценки фанфика
@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_'))
def handle_fanfic_rating(call):
    chat_id = call.message.chat.id
    data = call.data.split('_')
    selected_fanfic = data[1]
    sheet = user_data[chat_id]['selected_sheet']
    rating_stars = '⭐' * int(data[2])
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    # Открываем таблицу по ее ID и выбираем нужный лист
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(sheet)
    row = int(selected_fanfic)
    worksheet.update_cell(row, 1, "TRUE")
    worksheet.update_cell(row, 3, rating_stars)
    name = user_data[chat_id]['all_fanfics'][int(selected_fanfic) - 4]

    bot.send_message(chat_id, f"Вы оценили фанфик '{name[0]}'\n на {rating_stars} звезд.")


@bot.callback_query_handler(func=lambda call: call.data == "back")
def handle_back(call):
    chat_id = call.message.chat.id
    user_query = user_data.get(chat_id, {}).get('search_query', '')
    if user_query:
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])
        response = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{SHEET_NAME}!B4:B'
        ).execute()

        values = response.get('values', [])
        found_fanfics = [row[0] for row in values if row and len(row) > 0 and user_query in row[0].lower()]

        if found_fanfics:
            inline_markup = types.InlineKeyboardMarkup()
            for title in found_fanfics:
                truncated_title = title[:15] + '...' if len(title) > 15 else title

                inline_markup.add(
                    types.InlineKeyboardButton(text=truncated_title, callback_data=f"fanfic_{truncated_title}"))
            bot.send_message(chat_id, "Найдено:", reply_markup=inline_markup)
        else:
            bot.send_message(chat_id, "Совпадений не найдено.")
    else:
        bot.send_message(chat_id, "Нет данных для возврата.")


# Основной цикл для polling бота
if __name__ == "__main__":
    set_bot_commands()
    bot.infinity_polling(timeout = 10, long_polling_timeout = 5)