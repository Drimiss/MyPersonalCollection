def is_record_exists(service, sheet_name, spreadsheet_id, search_value):
    range_to_check = f'{sheet_name}!B:B'
    response = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_to_check).execute()
    values = response.get('values', [])
    return any(row and row[0] == search_value for row in values)

def updateSpreadsheet(service, data, spreadsheet_id, sheet_name, file_id):
    data1, size, data2, data3, data4 = data[0], data[1], data[2], data[3], data[4]
    file_view_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    range_to_insert = f'{sheet_name}!A{len(service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!B:B").execute().get("values", [])) + 1}:H'
    hyperlink_formula = f'=ГИПЕРССЫЛКА("{data4}"; "тык")'
    hyperlink_file = f'=ГИПЕРССЫЛКА("{file_view_link}"; "и тут тык")'
    data_to_insert = [['', data1, '', data2, data3, hyperlink_formula, hyperlink_file, size]]

    request = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_to_insert,
        valueInputOption='USER_ENTERED',
        body={'values': data_to_insert}
    )
    request.execute()



def updateSpreadsheetUP(service, data, spreadsheet_id):


    # Определение диапазона для вставки данных
    existing_rows = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{data[1]}!B:B").execute().get("values", [])
    range_to_insert = f'{data[1]}!A{data[0]}:C'

    # Данные для вставки
    data_to_insert = [[data[2],data[3], data[4]]]

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