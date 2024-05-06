import logging
import threading
import aiohttp
import os
import requests
import random
import re
import pandas as pd
import concurrent.futures
from bs4 import BeautifulSoup
import io
import aiofiles
import time
import atexit
import subprocess
try:
    from PIL import Image
except ImportError:
    Image = None

# Реєструємо функцію, яка буде викликана при виході інтерпретатора
atexit.register(subprocess.run, ["python3", "sendmail.py"])

# Функция для получения случайного User-Agent из списка
def get_random_user_agent():
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/88.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/88.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/94.0.992.38",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/94.0.992.38",
        # Добавьте другие строки User-Agent здесь
    ]
    return random.choice(USER_AGENTS)

# Функция для выполнения запроса с использованием случайного User-Agent и обработки возможных ошибок
def make_request(url):
    headers = {'User-Agent': get_random_user_agent()}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        # Записываем ошибку в лог или обрабатываем её по необходимости
        with open('log.txt', 'a', encoding='utf-8') as log_file:
            log_file.write(f"Помилка при здійснені запиту {url}: {str(e)}\n")
        return None

# Функция для сжатия изображения до заданного уровня качества
def compress_image(img, quality=30):
    image_stream = io.BytesIO()
    img.save(image_stream, format='WEBP', quality=quality)
    image_stream.seek(0)  # Скидываем позицию потока
    return Image.open(image_stream)

# Функция для обработки одного изображения с использованием мультиасинхронности
async def process_image_async_with_semaphore(semaphore, session, img_url, image_folder, idx):
    async with semaphore:
        try:
            async with session.get(img_url) as response:
                if response.status == 200:
                    image_name = f"{idx + 1}.jpg"
                    image_path = os.path.join(image_folder, image_name)

                    async with aiofiles.open(image_path, 'wb') as f:
                        await f.write(await response.read())

                    img = Image.open(image_path)
                    
                    if img.width > 1000:
                        img = img.crop((300, 300, img.width - 300, img.height - 300))
                        img.thumbnail((1000, 1000))
                        processed_image_path = image_path.replace(".jpg", ".webp")
                        
                        # Сжатие - от 1 до 95 - чем меньше значение, тем больше сжатие.
                        # Рекомендованное значение для webp - от 75 до 90
                        compressed_img = compress_image(img, quality=30)
                        compressed_img.save(processed_image_path)

                        os.remove(image_path)
                        del img  # Освобождаем память, удалив объект img

                        return processed_image_path
                    else:
                        os.remove(image_path)
                        del img  # Освобождаем память, удалив объект img
                        return None
                    
                else:
                    return None
        except Exception as exc:
            logging.exception(f"Exception occurred while processing {img_url}: {exc}")
            return None

# Функция для обработки изображений параллельно и асинхронно
def process_images_parallel(img_urls, image_folder):
    image_paths = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor: # Тут можно менять количество потоков для картинок <-----------

        future_to_url = {executor.submit(process_image_async_with_semaphore, img_url, image_folder): img_url for img_url in img_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            img_url = future_to_url[future]
            try:
                image_path = future.result()
                if image_path:
                    image_paths.append(image_path)
            except Exception as exc:
                logging.exception(f"Exception occurred while processing {img_url}: {exc}")
    return image_paths

# Функция для парсинга страницы товара
async def parse_product_page_async(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return BeautifulSoup(await response.text(), 'html.parser')
        else:
            raise Exception(f"Failed to fetch the page: {url}")

# Функция для записи лога о сохранении товара
def log_saved_product(product_info, product_count):
    with open('log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"Товар {product_count} збережено: {product_info['Посилання на товар']}\n")
    del product_info  # Освобождаем память, удалив объект product_info

# Создаем объект блокировки
lock = threading.Lock()

# Создаем логгер и устанавливаем уровень логирования
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Функция для записи сообщения в лог с использованием созданного обработчика
def write_to_log(message):
    logger.debug(message)

# Функция для создания папки для категории товаров
def create_category_folder(category_name):
    cleaned_category_name = re.sub(r'\W+', '_', category_name)  # Заменяем пробелы и лишние символы на нижнее подчёркивание
    folder_name = os.path.join('Image', cleaned_category_name)  # Полный путь к папке категории
    
    os.makedirs(folder_name, exist_ok=True)
    
    if os.path.exists(folder_name):
        return folder_name
    else:
        raise Exception(f"Не вдалося створити каталог: {folder_name}")

# Функция для парсинга информации про товар асинхронно
async def parse_product_info_async(session, semaphore, product_url, product_image_folder, product_count):
    try:
        product_info = {}
        product_info['Порядковий номер'] = product_count

        soup = await parse_product_page_async(session, product_url)

        product_info['Посилання на товар'] = product_url
        
        product_info['Назва товару'] = soup.select_one \
            ('.part__title--desktop').text.strip()
        
        product_info['Категорія'] = soup.select_one \
            ('.desktop-breadcrumb>.breadcrumb__items:nth-last-child(2)').text.strip()
        
        product_info['Стан товару'] = soup.select_one \
            ('#product-desc-2 .product_details .product_details__term:nth-child(2)').text.strip()
        
        product_info['Артикул'] = ', '.join([a.text for a in soup.select \
            ('#product-desc-2 .product_details .product_details__term:nth-child(4) a')])

        if not product_info['Артикул']:
            product_info['Артикул'] = ', '.join([a.text for a in soup.select \
                ('#product-desc-2 .product_details .product_details__term:nth-child(6) a')])

        if not product_info['Артикул']:
            product_info['Артикул'] = ', '.join \
                ([a.text for a in soup.select('#product-desc-2 .product_details .product_details__term:nth-child(8) a')])

        attribute_names = [attr.text.strip() for attr in soup.select('#product-desc-1>.product_details .product_details__desc')]
        attribute_values = [attr.text.strip() for attr in soup.select('#product-desc-1>.product_details .product_details__term')]
        attribute_data = {name: value for name, value in zip(attribute_names, attribute_values)}

        images = soup.select('.product_gallery_for__panel')
        image_paths = []
        cleaned_articul = re.sub(r'\W+', '', product_info['Артикул'])
        random_number = str(random.randint(10000, 99999))

        category_folder_name = create_category_folder(product_info['Категорія'])
        product_image_folder = os.path.join(category_folder_name, f"{cleaned_articul}_{random_number}")
        os.makedirs(product_image_folder, exist_ok=True)

        tasks = []
        for idx, img in enumerate(images[:3]):
            img_url = img.get('data-src')
            if img_url:
                task = process_image_async_with_semaphore(semaphore, session, img_url, product_image_folder, idx)
                tasks.append(task)

        image_paths = await asyncio.gather(*tasks)
        product_info['Изображение'] = ', '.join(image_paths)  # Зберігаємо повний шлях до зображень
        product_info['Ціна'] = soup.select_one('.product_price_block_amount').text.strip()
        product_info['Ціна доставки'] = soup.select_one('.product_price_block__delivery__price').text.strip()

        product_data = {**product_info, **attribute_data}

        # Додаємо виклик функції для запису логу про збереження товару
        log_saved_product(product_info, product_count)

        return product_data
    
    except Exception as e:
        logging.exception(f"Error parsing {product_url}: {str(e)}")
        return None

# Функция для записи данных в Excel файл
def write_to_excel(data):
    df = pd.DataFrame(data)
    df.to_excel('products_honda.xlsx', index=False)

# Функция для парсинга страницы категории асинхронно
'''async def scrape_category_pages_async(category_url, semaphore):
    product_data = []  # Создаем список для хранения данных о товарах
    product_count = 0

    # Создаем папку для изображений
    if not os.path.exists('Image'):
        os.mkdir('Image')

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        page = 1
        while page <= 5:    # <--- Количество страниц для парсинга <-----------------------!!!
            page_url = f"{category_url}&page={page}"
            soup = await parse_product_page_async(session, page_url)
            products = soup.select('.products__items')

            if not products:
                break

            for product in products:
                product_url = product.get('href')
                if product_url:
                    async with semaphore:
                        await asyncio.sleep(1)  # Задержка перед каждым запросом
                        product_count += 1
                        product_info = await parse_product_info_async(session, semaphore, product_url, 'Image', product_count)
                        if product_info:
                            product_data.append(product_info)  # Доюавляем данные про товар в список
                    
                            # Записываем данные в Excel после обработки каждого товара
                            write_to_excel(product_data)

            await asyncio.sleep(1)

            page += 1'''

async def scrape_category_pages_async(category_url, semaphore, max_pages):
    scraped_products = set()
    product_data = []  # Створюємо список для зберігання даних про товари
    product_count = 0

    # Створюємо папку для зберігання зображень
    if not os.path.exists('Image'):
        os.mkdir('Image')

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        page = 1
        while page <= max_pages:
            page_url = f"{category_url}&page={page}"
            soup = await parse_product_page_async(session, page_url)
            products = soup.select('.products__items .product-item')

            if not products:
                break

            for product in products:
                product_url = product.get('href')
                if product_url and product_url not in scraped_products:
                    scraped_products.add(product_url)
                    async with semaphore:
                        await asyncio.sleep(1)  # Додаємо затримку перед кожним запитом
                        product_count += 1
                        product_info = await parse_product_info_async(session, semaphore, product_url, 'Image', product_count)
                        if product_info:
                            product_data.append(product_info)  # Додаємо дані про товар до списку

            await asyncio.sleep(1)
            page += 1

    with open('log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"--- Скановано {product_count} товарів з категорії {category_url} ---\n")

    return product_data

# Функция для проверки доступности сети
def is_internet_available():
    try:
        response = requests.get("https://www.google.com", timeout=5)
        # Проверяем, был ли успешным запрос
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.RequestException:
        return False

# Функция для запуска парсинга с периодичной проверкой доступности сети
async def run_parser_async(category_url, max_pages):
    semaphore = asyncio.Semaphore(6)  # Максимальное количество асинхронных запросов <-------------------!

    while True:
        if is_internet_available():
            await scrape_category_pages_async(category_url, semaphore, max_pages)
            logging.info("Парсинг виконано успішно.")
            break
        else:
            logging.info("Нет доступа к интернету. Повторная проверка через 60 секунд.")
            await asyncio.sleep(60) # Подождать 60 секунд и повторно проверить доступность интернета

if __name__ == '__main__':
    import asyncio
    
    max_pages = 100
    category_url = "https://ovoko.pl/szukaj?man_id=66&cpc=1120&mfi=66;&prs=1"
    start_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Отримання ID поточного процесу
    pid = os.getpid()
    print(f"ID процесу: {pid}")
    
    with open('log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"--- Початок парсингу {start_time} ---\n")
    
    # Запис ID процесу у лог-файл
    with open('log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"ID наявного процесу: {pid}\n")    
        
    asyncio.run(run_parser_async(category_url, max_pages))

    with open('log.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"--- Завершення парсингу {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    #subprocess.run(["python3", "sendmail.py"])
    #subprocess.run(["python3", "process_archives.py"])
