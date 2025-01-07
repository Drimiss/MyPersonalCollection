import random
import configparser
import re

import gspread
import telebot  # Импортируем модуль для работы с Telegram Bot API
from oauth2client.service_account import ServiceAccountCredentials

from telebot import types  # Импортируем классы для создания кнопок и клавиатур в Telegram
from google_service import get_google_service  # Импортируем функцию для получения сервиса Google API
from epub_handle import readBook, document  # Импортируем функцию для чтения EPUB файлов
from sql import init_db, add_new_user, get_user_settings, update_sheet_name, update_spreadsheet, get_user_settings2

import logging

# Отключаем все логи для всей программы
logging.disable(logging.CRITICAL)


config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

token = config.get('bot', 'token')
admin = config.get('bot', 'AUTHORIZED_CHAT_ID')
CREDENTIALS_FILE = config.get('google', 'CREDENTIALS_FILE')
FOLDER_ID = config.get('google', 'FOLDER_ID')
EMAIL_TO_SHARE = config.get('google', 'EMAIL_TO_SHARE')

ITEMS_PER_PAGE = 4

bot = telebot.TeleBot(token)  # Создаем экземпляр бота с указанным токеном
user_data = {}  # Словарь для хранения состояний пользователей


def set_bot_commands():
    commands = [
        telebot.types.BotCommand('/start', 'Начать работу с ботом'),
        telebot.types.BotCommand('/search', 'Поиск фанфиков'),
        telebot.types.BotCommand('/update', 'Обновить информацию о фанфике'),
        telebot.types.BotCommand('/random', 'Выбрать случайное произведение'),
        telebot.types.BotCommand('/add', 'Добавить произведение'),
        telebot.types.BotCommand('/help', 'Помощь'),
        telebot.types.BotCommand('/settings', 'Настройки')
    ]
    bot.set_my_commands(commands)


@bot.message_handler(commands=['del'])
def delete(message):
    if str(message.chat.id).strip() == str(admin).strip():  # Проверка, является ли пользователь администратором
        try:
            delete_existing_titles()
            bot.send_message(message.chat.id, "Удаление завершено успешно, пустые строки удалены.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
    else:
        bot.reply_to(message, "Эта команда доступна только администратору.")


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id,
                     "Привет, я бот, который поможет следить тебе за потребляемым контентом. Я пока умею немного, но очень хочу помочь\n\n"
                     "Вот пример того, как выглядит моя таблица \n"
                     "https://docs.google.com/spreadsheets/d/1UDoYXpHov06Neix4UAcu-E4Kcy-yeDKjJlkR4NbA6OY/edit?usp=sharing\n"
                     
                     "Её можно настроить и добавить фильтры, но это базовая вещь. Cаму структуру советую оставить, потому что бот научен ставить галочки и оценку из списка\n\n\n"
                     
                    "Для начала работы зайди в /settings\n\n"

                     "!!!ВАЖНО!!!\n"
                     "- бот пока работает только с epub\n"
                     "- Library в примере - лист, на который автоматически добалвяются фанфики, когда вы отправляете их в бот")
    init_db()
    # Добавляем нового пользователя или проверяем его существование в базе
    add_new_user(message.chat.id)

@bot.message_handler(commands=['help'])
def send_welcome(message):
    bot.send_message(message.chat.id,
                "/search - "
                "Эта команда выведет список всех листов, на которых вы модете посмотреть все свои произведения\n\n"
                "/random - "
                "Эта команда выберет с любого листа непрочитанное произведение\n\n"
                "/add - "
                "Эта команда позволяет добавлять произведение на выбранный лист\n\n"
                     "/update - "
                "Эта команда поставит оценку произведению от 1 др 5 звезд\n\n"
                     "/help - "
                "Мы находимся здесь, тут ты сможешь вспомнить, что делает каждая кнопка\n\n"
                     "/settings - "
                "Больше не понадобится тебе, если только ты не захочешь сменить основной лист или таблицу в гугл таблице\n\n"
                "Если что-то не так, напишите мне @allDrimiss.\nЯ правда стараюсь(")

@bot.message_handler(commands=['settings'])
def handle_settings(message):
    # Запросим, что именно нужно изменить
    bot.send_message(message.chat.id, "Тебе нужно:\n"
                                      "- указать ссылку на гугл таблицу, где у тебя будет твоя коллекция\n"
                                      "- указать название основного листа (где будут скаченные произведения)\n"
                                      "- дать доступ для редактирования вот этой почте\n admin-369@readbooks-432315.iam.gserviceaccount.com\n\n"
                                      "Это административная почта, я не смогу просматривать твои таблицы")
    send_inline_buttons(message)


def send_inline_buttons(message):
    try:
        markup = types.InlineKeyboardMarkup()

        # Создаем две инлайн кнопки: одна для ввода адреса файла, другая - для ввода названия листа
        button_spreadsheet = types.InlineKeyboardButton('Ссылка на Excel', callback_data='spreadsheet')
        button_sheet_name = types.InlineKeyboardButton('Основная коллекция', callback_data='sheetMain_name')

        markup.add(button_spreadsheet, button_sheet_name)

        # Отправляем сообщение с инлайн кнопками
        bot.send_message(message.chat.id, "Что вы хотите изменить?", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, "Что-то не так. Попробуйте еще раз.")

# Обработчик для кнопки 'spreadsheet' (изменить exelId)
@bot.callback_query_handler(func=lambda call: call.data == 'spreadsheet')
def handle_spreadsheet(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Пожалуйста, отправьте адрес Excel. Но не забудьте нажать на крести, чтобы отправилась только ссылка")
    bot.register_next_step_handler(call.message, update_spreadsheet)


@bot.callback_query_handler(func=lambda call: call.data == 'sheetMain_name')
def handle_sheet_name(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Пожалуйста, отправьте название основного листа.")
    bot.register_next_step_handler(call.message, update_sheet_name)


@bot.message_handler(commands=['random'])
def handle_random(message):
    random_fic(message)


@bot.message_handler(commands=['search'])
def handle_search(message):
    try:
        search(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при получении листов: {e}")


@bot.message_handler(commands=['add'])
def send_add(message):
    bot.send_message(message.chat.id,
                     "Выберите лист куда хотите добавить произведение")
    try:
        need = get_user_settings(message)

        # Подключаемся к Google Sheets
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])

        sheets_metadata = service.spreadsheets().get(spreadsheetId=need[0]).execute()
        sheet_names = [sheet['properties']['title'] for sheet in sheets_metadata['sheets']]

        sheet_names.remove(need[1])

        inline_markup = types.InlineKeyboardMarkup()
        for sheet_name in sheet_names:
            inline_markup.add(types.InlineKeyboardButton(text=sheet_name, callback_data=f"sheet_add_{sheet_name}"))

        bot.send_message(message.chat.id, "Выберите лист для просмотра:", reply_markup=inline_markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при получении листов: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("sheet_add_"))
def handle_sheet_addition(call):
    sheet_name = call.data[len("sheet_add_"):]
    try:
        bot.send_message(call.message.chat.id,
                         f"Вы выбрали лист {sheet_name}. Введите данные для добавления в таблицу:")

        bot.register_next_step_handler(call.message, lambda message: add_to_sheet(message, sheet_name))

    except Exception as e:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Произошла ошибка: {e}", parse_mode='Markdown')


def add_to_sheet(message, sheet_name):
    try:
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])
        need = get_user_settings(message)
        # Сначала получим существующие данные столбца B
        result = service.spreadsheets().values().get(
            spreadsheetId=need[0],
            range=f'{sheet_name}!B:B'
        ).execute()

        # Определяем следующую пустую строку
        values = result.get('values', [])
        next_row = len(values) + 1

        # Указываем конкретную ячейку для вставки
        range_to_append = f'{sheet_name}!B{next_row}'

        user_message = message.text
        body = {
            'values': [[user_message]]
        }

        service.spreadsheets().values().update(
            spreadsheetId=need[0],
            range=range_to_append,
            valueInputOption='RAW',
            body=body
        ).execute()

        bot.send_message(message.chat.id, "Ваше сообщение успешно добавлено в таблицу!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("sheet_"))
def handle_sheet_selection(call):
    sheet_name = call.data[len("sheet_"):]
    need = get_user_settings(call.message)
    try:
        # Подключаемся к Google Sheets
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])

        # Получаем данные из указанного диапазона на выбранном листе
        response = service.spreadsheets().values().get(
            spreadsheetId=need[0],
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
    document(message)


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
    need = get_user_settings(message)
    # Подключаемся к Google Sheets
    service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                  'https://www.googleapis.com/auth/drive'])

    # Получаем названия листов
    sheet_titles, sheet_ids = get_sheets_titles(service, need[0])
    print(need)
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
    need = get_user_settings(call.message)

    # Получаем названия листов
    sheet_titles, sheet_ids = get_sheets_titles(service, need[0])
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
    need = get_user_settings(call.message)

    # Читаем данные из выбранного листа
    response = service.spreadsheets().values().get(
        spreadsheetId=need[0],
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
    need = get_user_settings2(chat_id)

    # Открываем таблицу по ее ID и выбираем нужный лист
    spreadsheet = gc.open_by_key(need[0])
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
    name = user_data[chat_id]['all_fanfics'][int(selected_fanfic) - 4]
    for i in range(1, 6):
        stars = '⭐' * i
        rating_markup.add(types.InlineKeyboardButton(text=stars, callback_data=f"rate_{selected_fanfic}_{i}"))
    bot.send_message(chat_id, "Оцените произведение:", reply_markup=rating_markup)


# Обработка оценки фанфика
@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_'))
def handle_fanfic_rating(call):
    chat_id = call.message.chat.id
    need = get_user_settings(call.message)
    data = call.data.split('_')
    selected_fanfic = data[1]
    sheet = user_data[chat_id]['selected_sheet']
    rating_stars = '⭐' * int(data[2])
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    # Открываем таблицу по ее ID и выбираем нужный лист
    spreadsheet = gc.open_by_key(need[0])
    worksheet = spreadsheet.worksheet(sheet)
    row = int(selected_fanfic)
    worksheet.update_cell(row, 1, "TRUE")
    worksheet.update_cell(row, 3, rating_stars)
    name = user_data[chat_id]['all_fanfics'][int(selected_fanfic) - 4]

    bot.send_message(chat_id, f"Вы оценили фанфик '{name[0]}'\n на {rating_stars} звезд.")


@bot.callback_query_handler(func=lambda call: call.data == "back")
def handle_back(call):
    chat_id = call.message.chat.id
    need = get_user_settings(call.message)
    user_query = user_data.get(chat_id, {}).get('search_query', '')
    if user_query:
        service = get_google_service('sheets', 'v4', ['https://www.googleapis.com/auth/spreadsheets',
                                                      'https://www.googleapis.com/auth/drive'])
        response = service.spreadsheets().values().get(
            spreadsheetId=need[0],
            range=f'{need[1]}!B4:B'
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


# Подключение к Google Sheets через gspread
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client


# Удаление существующих заголовков
def normalize_title(title):
    normalized = title.strip().lower()
    normalized = re.sub(r'\[.*?\]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'\s+', '', normalized)
    return normalized


def delete_existing_titles():
    try:
        chat_id = user_data[0]
        need = get_user_settings2(chat_id)
        client = get_gspread_client()
        spreadsheet = client.open_by_key(need[0])

        # Получаем данные из листа "Library"
        library_sheet = spreadsheet.worksheet("Library")
        library_titles = [normalize_title(row[0]) for row in library_sheet.col_values(2)[3:]]

        def remove_titles_from_sheet(sheet_name):
            sheet = spreadsheet.worksheet(sheet_name)
            sheet_titles = sheet.col_values(2)[3:]

            # Удаляем заголовки, которые уже есть в "Library"
            updated_titles = [title for title in sheet_titles if normalize_title(title) not in library_titles]

            # Обновляем данные в листе
            sheet.update('B4', [[title] for title in updated_titles])

        # Удаляем из листов "ФФ ВРИ" и "Минсоны"
        remove_titles_from_sheet('ФФ ВРИ')
        remove_titles_from_sheet('Минсоны')

    except Exception as e:
        print(f"Произошла ошибка: {e}")


# Поиск
def search(message):
    client = get_gspread_client()
    need = get_user_settings(message)
    spreadsheet = client.open_by_key(need[0])

    need = get_user_settings(message)

    # Получаем названия всех листов
    sheet_names = [sheet.title for sheet in spreadsheet.worksheets()]

    # Создаем инлайн-кнопки для каждого листа
    inline_markup = types.InlineKeyboardMarkup()
    for sheet_name in sheet_names:
        inline_markup.add(types.InlineKeyboardButton(text=sheet_name, callback_data=f"sheet_{sheet_name}"))

    # Отправляем инлайн-кнопки пользователю
    bot.send_message(message.chat.id, "Выберите лист для просмотра:", reply_markup=inline_markup)


# Обработчик обновлений
def update(message):
    bot.send_message(message.chat.id, "Выберите лист, в котором хотите искать:")
    need = get_user_settings(message)

    client = get_gspread_client()
    spreadsheet = client.open_by_key(need[0])

    # Получаем названия листов
    sheet_titles = [sheet.title for sheet in spreadsheet.worksheets()]

    inline_markup = types.InlineKeyboardMarkup()
    for sheet_title in sheet_titles:
        inline_markup.add(types.InlineKeyboardButton(text=sheet_title, callback_data=f"sheetUp_{sheet_title}"))

    # Отправляем инлайн-кнопки пользователю
    bot.send_message(message.chat.id, "Выберите лист:", reply_markup=inline_markup)


def random_fic(message):
    bot.send_message(message.chat.id, "Выберите лист, который хотите. Я передумал.\nСделаю всё сам!")
    need = get_user_settings(message)
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(need[0])

        # Получаем названия всех листов
        sheet_names = [sheet.title for sheet in spreadsheet.worksheets()]

        # Выбираем случайный лист
        random_sheet_name = random.choice(sheet_names)
        bot.send_message(message.chat.id, f"Я выбрал лист {random_sheet_name}")

        # Получаем данные с выбранного листа
        sheet = spreadsheet.worksheet(random_sheet_name)
        values = sheet.get_all_values()[3:]  # Получаем все строки, начиная с 4-й

        # Фильтруем данные, если в первом столбце не стоит "true" и второй столбец не пустой
        filtered_values = [
            row[1] for row in values if len(row) > 1 and row[1].strip() != '' and (row[0].strip().lower() != 'true')
        ]

        if filtered_values:
            # Формируем список фанфиков
            fanfics = [f"`{value}`" for value in filtered_values]
            random_fanfic = random.choice(fanfics)
            message_text = f"Это для вас:\n{random_fanfic}"
        else:
            message_text = "Нет доступных произведений на этом листе."

        # Проверка на длину сообщения и отправка нескольких сообщений, если нужно
        if len(message_text) > 4096:
            # Если сообщение слишком длинное, разделим его на несколько частей
            while len(message_text) > 4096:
                bot.send_message(message.chat.id, message_text[:4096])
                message_text = message_text[4096:]
            # Отправляем оставшуюся часть
            if message_text:
                bot.send_message(message.chat.id, message_text)
        else:
            bot.send_message(message.chat.id, message_text, parse_mode='Markdown')

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


# Основной цикл для polling бота
if __name__ == "__main__":
    set_bot_commands()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
