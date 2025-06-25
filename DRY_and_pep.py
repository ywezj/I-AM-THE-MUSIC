import telebot
import sqlite3
from telebot import types
import os
from pathlib import Path

# Инициализация бота
bot = telebot.TeleBot(token='7497684081:AAG1kaEeLCCUa4ftLPAg266XYQQiaNAhcHE')

# Конфигурация путей
BASE_DIR = Path(file).parent
DB_PATH = BASE_DIR / 'music.sql'
MUSIC_DIR = BASE_DIR / 'MUSIC'
MUSIC_DIR.mkdir(exist_ok=True)  # Создаем папку для музыки, если её нет

# Глобальные переменные
name = None
artist = None
old_name = None

def main():
    """Основная функция запуска бота"""

    @bot.message_handler(commands=['start'])
    def start(message):
        """Обработчик команды /start"""
        send_message_with_markup(
            message.chat.id,
            f'Привет, {message.from_user.first_name}, напиши /help',
            create_main_markup()
        )

    @bot.message_handler(commands=['help'])
    def help_message(message):
        """Обработчик команды /help"""
        send_text_file(message, 'help.txt')

    @bot.message_handler(commands=['listen'])
    def listen(message):
        """Обработчик команды /listen"""
        try:
            send_playlist(message)
            bot.register_next_step_handler(message, music_player)
        except sqlite3.OperationalError:
            send_message(message.chat.id, 'Ты пока не загрузил песни')

    @bot.message_handler(commands=['view_all'])
    def view_all(message):
        """Обработчик команды /view_all"""
        send_message(message.chat.id, get_playlist_info())

    @bot.message_handler(commands=['add'])
    def song_name(message):
        """Обработчик команды /add"""
        init_database()
        send_message(message.chat.id, 'Введи название песни')
        bot.register_next_step_handler(message, naming)

    @bot.message_handler(commands=['options'])
    def options_message(message):
        """Обработчик команды /options"""
        markup = create_simple_markup(['/delete', '/edit'])
        send_message(message.chat.id, 'Что вы хотите сделать?', reply_markup=markup)

    @bot.message_handler(commands=['delete'])
    def preparation_for_delete(message):
        """Обработчик команды /delete"""
        send_message(message.chat.id, 'Введи название песни')
        send_message(message.chat.id, get_playlist_info())
        bot.register_next_step_handler(message, delete)

    @bot.message_handler(commands=['edit'])
    def find_old_name(message):
        """Обработчик команды /edit"""
        send_message(message.chat.id, 'Введи старое название песни')
        send_message(message.chat.id, get_playlist_info())
        bot.register_next_step_handler(message, new_name)

    @bot.message_handler(content_types=['audio'])
    def save_audio(message):
        """Обработчик аудиофайлов"""
        try:
            save_audio_file(message)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('Весь плейлист', callback_data='loadings'))
            bot.delete_message(message.chat.id, message.message_id)
            send_message(message.chat.id, 'Трек добавлен', reply_markup=markup)
        except AttributeError:
            send_message(message.chat.id, 'Друг, похоже ты отправил мне не аудиофайл. Отправь мне аудио, пожалуйста')

    @bot.callback_query_handler(func=lambda callback: True)
    def callback_message(callback):
        """Обработчик callback-запросов"""
        send_message(callback.message.chat.id, get_playlist_info())

    @bot.message_handler()
    def txt_random_validation(message):
        """Обработчик неизвестных команд"""
        if message.text not in ['/add', '/start', '/listen']:
            send_text_file(message, 'validation.txt')

    bot.polling()

# Вспомогательные функции
def init_database():
    """Инициализация базы данных"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS loadings (id INTEGER PRIMARY KEY, name TEXT, artist TEXT)')

def get_playlist_info():
    """Получение информации о плейлисте"""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM loadings')
        loadings = cur.fetchall()
        return '\n'.join(f'Название трека: {i[1]}, Исполнитель: {i[2]}' for i in loadings)

def create_main_markup():
    """Создание основной клавиатуры"""
    return create_simple_markup(['/listen', '/add', '/view_all', '/options'])

def create_simple_markup(buttons):
    """Создание простой клавиатуры"""
    markup = types.ReplyKeyboardMarkup()
    for btn in buttons:
        markup.row(types.KeyboardButton(btn))
    return markup

def send_playlist(message):
    """Отправка плейлиста пользователю"""
    send_message(message.chat.id, 'ВАШ ПЛЕЙЛИСТ:')
    send_message(message.chat.id, get_playlist_info())

def music_player(message):
    """Воспроизведение музыки"""
    track_name = message.text
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM loadings WHERE name=?', (track_name,))
        track = cur.fetchone()

    if track:
        file_path = MUSIC_DIR / f'{track_name}.mp3'
        if file_path.exists():
            with open(file_path, 'rb') as file:
                bot.send_audio(message.chat.id, file, title=track_name)
        else:
            send_message(message.chat.id, 'Файл не найден на сервере')

def naming(message):
    """Обработка названия трека"""
    global name
    name = message.text.strip()
    send_message(message.chat.id, 'отправь аудио')
    bot.register_next_step_handler(message, save_audio)

def save_audio_file(message):
    """Сохранение аудиофайла"""
    global name, artist
    artist = message.audio.performer or 'Неизвестный исполнитель'
    audio_path = MUSIC_DIR / f"{name}.mp3"
    
    # Скачиваем и сохраняем файл
    file_info = bot.get_file(message.audio.file_id)
    audio_data = bot.download_file(file_info.file_path)
    
    with open(audio_path, 'wb') as file:
        file.write(audio_data)

    # Сохраняем в БД
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO loadings (name, artist) VALUES (?, ?)', (name, artist))

def delete(message):
    """Удаление трека"""
    track_name = message.text.strip()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM loadings WHERE name = ?', (track_name,))

    file_path = MUSIC_DIR / f'{track_name}.mp3'
    if file_path.exists():
        os.remove(file_path)
        send_message(message.chat.id, 'Запись успешно удалена')
    else:
        send_message(message.chat.id, 'Такого трека нет в твоём плейлисте, друг')
    
    send_message_with_markup(
        message.chat.id,
        get_playlist_info(),
        create_main_markup()
    )

def new_name(message):
    """Получение старого названия для редактирования"""
    global old_name
    old_name = message.text.strip()
    send_message(message.chat.id, 'Введи новое название песни')
    bot.register_next_step_handler(message, edit)

def edit(message):
    """Редактирование трека"""
    global old_name
    new_name = message.text.strip()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE loadings SET name = ? WHERE name = ?", (new_name, old_name))

    old_path = MUSIC_DIR / f'{old_name}.mp3'
    new_path = MUSIC_DIR / f'{new_name}.mp3'
    
    if old_path.exists():
        os.rename(old_path, new_path)
        send_message(message.chat.id, 'Запись успешно обновлена')
    else:
        send_message(message.chat.id, 'Похоже такого трека нет в твоём плейлисте, друг')
    
    send_message_with_markup(
        message.chat.id,
        get_playlist_info(),
        create_main_markup()
    )

def send_message(chat_id, text, reply_markup=None):
    """Универсальная функция отправки сообщения"""
    bot.send_message(chat_id, text, reply_markup=reply_markup)

def send_message_with_markup(chat_id, text, markup):
    """Отправка сообщения с клавиатурой"""
    send_message(chat_id, text, reply_markup=markup)
  
def send_text_file(message, filename):
    """Отправка содержимого текстового файла"""
    file_path = BASE_DIR / filename
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as file:
            send_message(message.chat.id, file.read())
    else:
        send_message(message.chat.id, f'Файл {filename} не найден')

if name == 'main':
    main()