import os
import shutil
from datetime import datetime

# Отримання поточної дати
today_date = datetime.now().strftime("%d_%m_%y")

# Шляхи до файлів та папок
root_folder = ""
archives_folder = os.path.join(root_folder, "Archives")
image_folder = os.path.join(root_folder, "Image")
archive_subfolder = os.path.join(archives_folder, today_date)
archive_zip_path = os.path.join(archive_subfolder, "Image.zip")
log_file_path = os.path.join(root_folder, "log.txt")
honda_file_path = os.path.join(root_folder, "products_honda.xlsx")

# Створення папки Archives, якщо вона не існує
if not os.path.exists(archives_folder):
    os.makedirs(archives_folder)

# Створення папки з поточною датою
if not os.path.exists(archive_subfolder):
    os.makedirs(archive_subfolder)

# Архівування папки Image в архів Image.zip
shutil.make_archive(archive_zip_path.replace('.zip', ''), 'zip', image_folder)

# Переміщення файлів log.txt та products_honda.xlsx в папку з поточною датою
shutil.move(log_file_path, archive_subfolder)
shutil.move(honda_file_path, archive_subfolder)

# Видалення папки Image, якщо архів створено успішно
if os.path.exists(archive_zip_path):
    shutil.rmtree(image_folder)
    print("Папку /root/parser/Image видалено.")
