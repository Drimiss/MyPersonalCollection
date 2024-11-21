import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

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
                if fandom_text == "Сакавич Нора «Все ради игры»":
                    fandom_text = "All for the game"
                data.append(fandom_text)

            status = soup.find('b', string='Статус:')
            if status:
                status_text = status.find_next_sibling(string=True).strip()
                data.append(status_text)

            link = soup.find('a')
            if link and link.get('href'):
                data.append(link.get('href'))

            return data
