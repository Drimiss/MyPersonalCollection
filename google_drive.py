import os
from googleapiclient.http import MediaFileUpload
import logging
import time
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_to_google_drive(service, file_path, email, folder_id=None):
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id] if folder_id else []}
    media = MediaFileUpload(file_path, resumable=True)

    retries = 3
    for attempt in range(retries):
        try:
            logging.info(f"Попытка загрузки файла: {file_path}, попытка {attempt + 1}")
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_id = file.get('id')
            create_permission(service, file_id, email)
            logging.info(f"Файл успешно загружен. ID: {file_id}")
            return file_id
        except HttpError as e:
            logging.error(f"Ошибка при загрузке файла: {e}")
        except Exception as e:
            logging.error(f"Ошибка при загрузке файла: {e}")
        time.sleep(5)
    return None

def create_permission(service, file_id, email):
    permission = {'type': 'user', 'role': 'writer', 'emailAddress': email}
    try:
        service.permissions().create(fileId=file_id, body=permission, fields='id').execute()
    except Exception as e:
        print(f"Ошибка при добавлении разрешения: {e}")
