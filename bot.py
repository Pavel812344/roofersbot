import logging
import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import asyncio
from aiohttp import web
import random

async def healthcheck(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("✅ Веб-сервер запущен на порту 10000")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv('BOT_TOKEN') # убедись, что токен в переменных окружениях установлен!

# Словарь с информацией о ЖК
buildings = {
    'neva_towers': {
        'name': 'Neva Towers',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/neva_towers.jpg'  # Укажите путь к фото
    },
    'federation': {
        'name': 'Башня Федерация',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/federation.jpg'
    },
    'okyo': {
        'name': 'ЖК Око',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/okyo.jpg'
    },
    'mercury': {
        'name': 'Меркурий Сити Тауэр',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/mercury.jpg'
    },
    'capital_city': {
        'name': 'Город Столиц',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/capital_city.jpg'
    },
    'evolution': {
        'name': 'Башня Эволюция',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/evolution.jpg'
    },
    'imperia': {
        'name': 'Башня Империя',
        'complex': 'Москва-Сити',
        'points': 20,
        'photo_path': 'photos/imperia.jpg'
    },
    'vysotsky': {
        'name': 'ЖК Высоцкий',
        'complex': 'Екатеринбург',
        'points': 10,
        'photo_path': 'photos/vysotsky.jpg'
    },
    'lighthouse': {
        'name': 'ЖК Маяк',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/lighthouse.jpg'
    },
    'headliner': {
        'name': 'ЖК Хедлайнер',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/headliner.jpg'
    },
    'zilart': {
        'name': 'ЖК Зиларт',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/zilart.jpg'
    },
    'serdtse_stolicy': {
        'name': 'ЖК Сердце Столицы',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/serdtse_stolicy.jpg'
    },
    'alye_parusa': {
        'name': 'ЖК Алые Паруса',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/alye_parusa.jpg'
    },
    'vorobyovy_gory': {
        'name': 'ЖК Воробьёвы горы',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/vorobyovy_gory.jpg'
    },
    'triumph_palace': {
        'name': 'Триумф-Палас',
        'complex': 'Москва',
        'points': 10,
        'photo_path': 'photos/triumph_palace.jpg'
    }
}

# Функции для работы с базой данных
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  points INTEGER DEFAULT 0,
                  registered_date TEXT)''')
    
    # Таблица взятых ЖК
    c.execute('''CREATE TABLE IF NOT EXISTS conquered_buildings
                 (user_id INTEGER,
                  building_id TEXT,
                  conquered_date TEXT,
                  points_earned INTEGER,
                  PRIMARY KEY (user_id, building_id))''')
    
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name):
    """Регистрация нового пользователя"""
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, first_name, points, registered_date) VALUES (?, ?, ?, ?, ?)",
                  (user_id, username, first_name, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    
    conn.close()

def get_user_profile(user_id):
    """Получение профиля пользователя"""
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    # Получаем информацию о пользователе
    c.execute("SELECT points, first_name FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        conn.close()
        return None
    
    points, first_name = user_data
    
    # Получаем взятые ЖК
    c.execute('''SELECT b.building_id, b.name, b.complex, cb.conquered_date 
                 FROM conquered_buildings cb
                 JOIN buildings_info b ON cb.building_id = b.building_id
                 WHERE cb.user_id = ?
                 ORDER BY cb.conquered_date DESC''', (user_id,))
    conquered = c.fetchall()
    
    conn.close()
    
    return {
        'points': points,
        'first_name': first_name,
        'conquered': conquered
    }

def can_take_building(user_id, building_id):
    """Проверка, может ли пользователь взять ЖК"""
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM conquered_buildings WHERE user_id = ? AND building_id = ?",
              (user_id, building_id))
    result = c.fetchone() is None
    
    conn.close()
    return result

def take_building(user_id, building_id):
    """Взятие ЖК пользователем"""
    if not can_take_building(user_id, building_id):
        return False
    
    points = buildings[building_id]['points']
    
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    # Добавляем запись о взятом ЖК
    c.execute("INSERT INTO conquered_buildings (user_id, building_id, conquered_date, points_earned) VALUES (?, ?, ?, ?)",
              (user_id, building_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), points))
    
    # Обновляем очки пользователя
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
    
    conn.commit()
    conn.close()
    
    return True

# Создаем таблицу с информацией о ЖК для SQLite
def create_buildings_table():
    """Создание таблицы с информацией о ЖК"""
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS buildings_info
                 (building_id TEXT PRIMARY KEY,
                  name TEXT,
                  complex TEXT,
                  points INTEGER)''')
    
    # Заполняем таблицу данными
    for bid, info in buildings.items():
        c.execute("INSERT OR IGNORE INTO buildings_info (building_id, name, complex, points) VALUES (?, ?, ?, ?)",
                  (bid, info['name'], info['complex'], info['points']))
    
    conn.commit()
    conn.close()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
        [InlineKeyboardButton("📊 Портфолио руфера", callback_data='profile')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! Добро пожаловать в игру Руфер!\n\n"
        "Здесь ты можешь собирать очки, 'беря' разные жилые комплексы. "
        "Башни Москва-Сити оцениваются в 20 очков, остальные ЖК - по 10 очков.\n\n"
        "Нажимай кнопку 'Руфить!' чтобы начать!",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query 
    await query.answer()
    user = query.from_user
    register_user(user.id, user.username, user.first_name)
    
    if query.data == 'roof_action':
        # Выбираем случайный ЖК из доступных
        available_buildings = []
        for bid, info in buildings.items():
            if can_take_building(user.id, bid):
                available_buildings.append(bid)
        
        if not available_buildings:
            await query.edit_message_text(
                "Ты уже взял все доступные ЖК! Отличная работа! 👏\n\n"
                "Следи за обновлениями - скоро добавятся новые!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📊 В портфолио", callback_data='profile')
                ]])
            )
            return
        
        # Сохраняем список доступных ЖК в контексте
        context.user_data['available_buildings'] = available_buildings
        context.user_data['current_index'] = 0
        
        # Показываем первый ЖК
        await show_building(query, context, user.id)
    
    elif query.data == 'profile':
        profile = get_user_profile(user.id)
        if not profile:
            await query.edit_message_text("Профиль не найден. Начни игру с /start")
            return
        
        # Формируем сообщение с профилем
        message = f"📊 Портфолио руфера {profile['first_name']}\n\n"
        message += f"💰 Всего очков: {profile['points']}\n"
        message += f"🏆 Взято ЖК: {len(profile['conquered'])}\n\n"
        message += "📋 Взятые ЖК:\n"
        
        if profile['conquered']:
            for building in profile['conquered'][:10]:  # Показываем последние 10
                message += f"• {building[1]} ({building[2]}) - {building[3]}\n"
            if len(profile['conquered']) > 10:
                message += f"... и ещё {len(profile['conquered']) - 10}\n"
        else:
            message += "Пока нет взятых ЖК. Нажми 'Руфить!' чтобы начать!\n"
        
        keyboard = [[InlineKeyboardButton("🏢 Продолжить руфить", callback_data='roof_action')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    elif query.data == 'take_building':
        # Пользователь берет ЖК
        if 'current_building' not in context.user_data:
            await query.edit_message_text("Произошла ошибка. Попробуй снова нажать 'Руфить!'")
            return
        
        building_id = context.user_data['current_building']
        
        if take_building(user.id, building_id):
            building = buildings[building_id]
            
            # Показываем следующее здание или сообщение о завершении
            available_buildings = context.user_data.get('available_buildings', [])
            current_index = context.user_data.get('current_index', 0)
            
            if current_index + 1 < len(available_buildings):
                # Показываем следующее здание
                context.user_data['current_index'] = current_index + 1
                await show_building(query, context, user.id, edit=False)
            else:
                # Все здания показаны
                profile = get_user_profile(user.id)
                await query.edit_message_text()
                f"✅ Ты взял {building['name']} и получил {building['points']} очков!\n\n"
                f"Ты просмотрел все доступные ЖК! Всего у тебя {profile['points']} очков.",
                reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📊 В портфолио", callback_data='profile')
                    ]])
                
        else:
            await query.edit_message_text(
                "❌ Ты уже брал этот ЖК! Попробуй другой.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Показать другой", callback_data='roof_action')
                ]])
            )
    
    elif query.data == 'next_building':
        # Пропускаем текущее здание
        available_buildings = context.user_data.get('available_buildings', [])
        current_index = context.user_data.get('current_index', 0)
        
        if current_index + 1 < len(available_buildings):
            context.user_data['current_index'] = current_index + 1
            await show_building(query, context, user.id, edit=False)
        else:
            # Больше нет зданий для показа
            await query.edit_message_text(
                "Больше нет доступных ЖК для показа!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📊 В портфолио", callback_data='profile')
                ]])
            )

async def show_building(query, context, user_id, edit=True):
    """Показывает информацию о текущем ЖК"""
    available_buildings = context.user_data['available_buildings']
    current_index = context.user_data['current_index']
    
    building_id = available_buildings[current_index]
    building = buildings[building_id]
    context.user_data['current_building'] = building_id
    
    keyboard = [
        [InlineKeyboardButton("✅ Взять ЖК", callback_data='take_building')],
        [InlineKeyboardButton("⏭ Пропустить", callback_data='next_building')],
        [InlineKeyboardButton("📊 В портфолио", callback_data='profile')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"🏢 {building['name']}\n"
        f"📍 Комплекс: {building['complex']}\n"
        f"💰 Очки: {building['points']}\n\n"
        f"Прогресс: {current_index + 1}/{len(available_buildings)}"
    )
    
    try:
        # Отправляем фото
        with open(building['photo_path'], 'rb') as photo:
            if edit:
                await query.edit_message_media(
                    media=InputMediaPhoto(photo, caption=message_text),
                    reply_markup=reply_markup
                )
            else:
                await query.message.reply_photo(
                    photo=photo,
                    caption=message_text,
                    reply_markup=reply_markup
                )
                await query.message.delete()
    except FileNotFoundError:
        # Если фото не найдено, отправляем только текст
        if edit:
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await query.message.reply_text(message_text, reply_markup=reply_markup)
            await query.message.delete()

def main():
    """Основная функция запуска бота"""
    # Инициализация базы данных
    init_db()
    create_buildings_table()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    
    # Запуск бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
