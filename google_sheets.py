def is_record_exists(service, sheet_name, spreadsheet_id, search_value):
    range_to_check = f'{sheet_name}!B:B'
    response = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_to_check).execute()
    values = response.get('values', [])
    return any(row and row[0] == search_value for row in values)


def addSpreadsheet(service, data, spreadsheet_id, sheet_name, file_id):
    print(data)
    data1, size, data2, data3, data4 = data[0], data[1], data[2], data[3], data[4]
    print(data1, size, data2, data3, data4)
    file_view_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    if spreadsheet_id == "1UXDZ_UEGvAP0cyLNVDbC3aBXB77tCuKULmtZPAReRj4":
        range_to_insert = f'{sheet_name}!A{len(service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!B:B").execute().get("values", [])) + 1}:H'
        hyperlink_formula = f'=ГИПЕРССЫЛКА("{data4}"; "тык")'
        hyperlink_file = f'=ГИПЕРССЫЛКА("{file_view_link}"; "и тут тык")'
        data_to_insert = [['', data1, '', data2, data3, hyperlink_formula, hyperlink_file, size]]
    else:
        range_to_insert = f'{sheet_name}!A{len(service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!B:B").execute().get("values", [])) + 1}:H'
        hyperlink_formula = f'=ГИПЕРССЫЛКА("{data4}"; "тык")'
        data_to_insert = [['', data1, '', data2, data3, hyperlink_formula, size]]

    request = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_to_insert,
        valueInputOption='USER_ENTERED',
        body={'values': data_to_insert}
    )
    request.execute()


# def updateSpreadsheet(service, data, spreadsheet_id, sheet_name):
#     data1, size, _, data3, _ = data  # Извлекаем только нужные данные (data3)
#
#     # Получаем все значения из столбца B
#     response = service.spreadsheets().values().get(
#         spreadsheetId=spreadsheet_id,
#         range=f"{sheet_name}!B2:B"
#     ).execute()
#
#     values = response.get("values", [])
#     row_number = None
#     range_to_insert = f'{sheet_name}!A{len(service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!B:B").execute().get("values", [])) + 1}:H'
#
#     # Ищем строку с названием data1 в столбце B
#     for i, row in enumerate(values):
#         if row and row[0] == data1:
#             row_number = i + 2  # Строки начинаются с 2-й, потому что 1-я — это заголовки
#             break
#
#     # Если строка с названием не найдена, добавляем новую строку
#     if row_number is None:
#         row_number = len(values) + 2  # Если строка не найдена, вставляем в конец
#
#     # Обновляем данные в столбце E (столбец E — это 5-й столбец)
#     range_to_update = f'{sheet_name}!E{row_number}'
#
#     data_to_insert = [['', data1, '', '', data3, '', size]]
#
#     # Обновляем только данные в столбце E
#     request = service.spreadsheets().values().update(
#         spreadsheetId=spreadsheet_id,
#         range=range_to_insert,
#         valueInputOption='USER_ENTERED',
#         body={'values': data_to_insert}  # Вставляем только значение data3
#     )
#     request.execute()
#
#     print(f"Updated cell {range_to_update} with value {data3}")
#

def updateSpreadsheetUP(service, data, spreadsheet_id):
    # Определение диапазона для вставки данных
    existing_rows = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{data[1]}!B:B").execute().get("values", [])
    range_to_insert = f'{data[1]}!A{data[0]}:C'

    # Данные для вставки
    data_to_insert = [[data[2], data[3], data[4]]]

    # Обновление таблицы
    try:
        request = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_to_insert,
            valueInputOption='USER_ENTERED',
            body={'values': data_to_insert}
        )
        request.execute()
        print("Данные успешно обновлены!")
    except Exception as e:
        print(f"Ошибка при обновлении таблицы: {e}")


def get_sheets_titles(service, spreadsheet_id):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', [])
    sheet_titles = [sheet['properties']['title'] for sheet in sheets]
    sheet_id = [sheet['properties']['sheetId'] for sheet in sheets]
    return sheet_titles, sheet_id
