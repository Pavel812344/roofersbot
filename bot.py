import logging
import sqlite3
import asyncio
import random
import os
import time
import requests
import signal
import threading
from datetime import datetime, timedelta
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

def add_menu_button(keyboard):
    if isinstance(keyboard, list):
        keyboard.append([InlineKeyboardButton("🏠 В меню", callback_data='menu')])
    return keyboard

# ==================== САМОПИНГ И ПЕРЕЗАПУСК ====================
def restart_bot():
    print("⚠️ Бот завис, принудительное завершение...")
    os._exit(1)

def self_ping_thread():
    failed_pings = 0
    while True:
        time.sleep(300)
        try:
            requests.get("https://roofchikbot.onrender.com", timeout=10)
            print("Self-ping выполнен")
            failed_pings = 0
        except Exception as e:
            failed_pings += 1
            print(f"Пинг не удался ({failed_pings}/3): {e}")
            if failed_pings >= 3:
                restart_bot()

# ==================== НАСТРОЙКА ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
TOKEN = os.getenv('BOT_TOKEN')

# ==================== ВЕБ-СЕРВЕР ДЛЯ ПИНГОВ ====================
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

# ==================== 100+ ЖК ====================
buildings = {
    # ========== МОСКВА-СИТИ (20 очков) ==========
    'neva_towers': {'name': 'Neva Towers', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/neva_towers.jpg'},
    'federation': {'name': 'Башня Федерация', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/federation.jpg'},
    'okyo': {'name': 'ЖК Око', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/okyo.jpg'},
    'mercury': {'name': 'Меркурий Сити Тауэр', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/mercury.jpg'},
    'capital_city': {'name': 'Город Столиц', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/capital_city.jpg'},
    'evolution': {'name': 'Башня Эволюция', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/evolution.jpg'},
    'imperia': {'name': 'Башня Империя', 'complex': 'Москва-Сити', 'points': 20, 'photo_path': 'photos/imperia.jpg'},

    # ========== МОСКВА (10 очков) ==========
    'filigrad': {'name': 'Фили Град', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/filigrad.jpg'},
    'setun_city': {'name': 'Сетунь Сити', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/setun_city.jpg'},
    'luchi': {'name': 'Лучи', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/luchi.jpg'},
    'simvol': {'name': 'Символ', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/simvol.jpg'},
    'sportkvartal': {'name': 'Спортивный квартал', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/sportkvartal.jpg'},
    'parkrublevo': {'name': 'Парк Рублёво', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/parkrublevo.jpg'},
    'myakinino': {'name': 'Резиденция Мякинино', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/myakinino.jpg'},
    'parkcity': {'name': 'Парк Сити', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/parkcity.jpg'},
    'mosfilm': {'name': 'Мосфильмовский', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/mosfilm.jpg'},
    'begovoy': {'name': 'Дом на Беговой', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/begovoy.jpg'},
    'frunzenskaya': {'name': 'Дом на Фрунзенской', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/frunzenskaya.jpg'},
    'beregovoy': {'name': 'Береговой', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/beregovoy.jpg'},
    'naberezhny': {'name': 'Набережный квартал', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/naberezhny.jpg'},
    'parkpobedy': {'name': 'Парк Победы', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/parkpobedy.jpg'},
    'smolensky': {'name': 'Смоленский пассаж', 'complex': 'Москва', 'points': 10, 'photo_path': 'photos/smolensky.jpg'},

    # ========== САНКТ-ПЕТЕРБУРГ (10 очков) ==========
    'evropacity': {'name': 'Европа Сити', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/evropacity.jpg'},
    'okhtamoll': {'name': 'Охта Молл', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/okhtamoll.jpg'},
    'nevskaya': {'name': 'Невская ратуша', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/nevskaya.jpg'},
    'primorsky': {'name': 'Приморский', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/primorsky.jpg'},
    'graf_orlov': {'name': 'Граф Орлов', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/graf_orlov.jpg'},
    'imperial': {'name': 'Империал', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/imperial.jpg'},
    'senator': {'name': 'Сенатор', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/senator.jpg'},
    'monblan': {'name': 'Резиденция Монблан', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/monblan.jpg'},
    'sever_dolina': {'name': 'Северная долина', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/sever_dolina.jpg'},
    'tsarskaya': {'name': 'Царская столица', 'complex': 'Санкт-Петербург', 'points': 10, 'photo_path': 'photos/tsarskaya.jpg'},

    # ========== ЕКАТЕРИНБУРГ (10 очков) ==========
    'vysotsky_ekb': {'name': 'Высоцкий', 'complex': 'Екатеринбург', 'points': 10, 'photo_path': 'photos/vysotsky_ekb.jpg'},
    'iset_tower': {'name': 'Isеt Tower', 'complex': 'Екатеринбург', 'points': 10, 'photo_path': 'photos/iset_tower.jpg'},
    'belinskogo': {'name': 'Квартал на Белинского', 'complex': 'Екатеринбург', 'points': 10, 'photo_path': 'photos/belinskogo.jpg'},
    'malysheva': {'name': 'Квартал на Малышева', 'complex': 'Екатеринбург', 'points': 10, 'photo_path': 'photos/malysheva.jpg'},

    # ========== КАЗАНЬ (10 очков) ==========
    'lazurnye_neba': {'name': 'Лазурные небеса', 'complex': 'Казань', 'points': 10, 'photo_path': 'photos/lazurnye_neba.jpg'},
    'kazan_river': {'name': 'Казань Ривер', 'complex': 'Казань', 'points': 10, 'photo_path': 'photos/kazan_river.jpg'},
    'izumrud': {'name': 'Изумрудный город', 'complex': 'Казань', 'points': 10, 'photo_path': 'photos/izumrud.jpg'},
    'serebryany': {'name': 'Серебряный бор', 'complex': 'Казань', 'points': 10, 'photo_path': 'photos/serebryany.jpg'},
    'kremlin_quart': {'name': 'Кремлёвский квартал', 'complex': 'Казань', 'points': 10, 'photo_path': 'photos/kremlin_quart.jpg'},

    # ========== НОВОСИБИРСК (10 очков) ==========
    'atlantic_city': {'name': 'Атлантик Сити', 'complex': 'Новосибирск', 'points': 10, 'photo_path': 'photos/atlantic_city.jpg'},
    'krasnaya_gorka': {'name': 'Красная горка', 'complex': 'Новосибирск', 'points': 10, 'photo_path': 'photos/krasnaya_gorka.jpg'},
    'zolotaya_niva': {'name': 'Золотая Нива', 'complex': 'Новосибирск', 'points': 10, 'photo_path': 'photos/zolotaya_niva.jpg'},
    'akadem': {'name': 'Академгородок', 'complex': 'Новосибирск', 'points': 10, 'photo_path': 'photos/akadem.jpg'},
    'rechnoy': {'name': 'Речной вокзал', 'complex': 'Новосибирск', 'points': 10, 'photo_path': 'photos/rechnoy.jpg'},

    # ========== КРАСНОДАР (10 очков) ==========
    'krasnodar_city': {'name': 'Краснодар Сити', 'complex': 'Краснодар', 'points': 10, 'photo_path': 'photos/krasnodar_city.jpg'},

    # ========== СОЧИ (10 очков) ==========
    'sochi_park': {'name': 'Сочи Парк', 'complex': 'Сочи', 'points': 10, 'photo_path': 'photos/sochi_park.jpg'},

    # ========== РОСТОВ-НА-ДОНУ (10 очков) ==========
    'rostov_arena': {'name': 'Ростов Арена', 'complex': 'Ростов-на-Дону', 'points': 10, 'photo_path': 'photos/rostov_arena.jpg'},
    'rostov_city': {'name': 'Ростов Сити', 'complex': 'Ростов-на-Дону', 'points': 10, 'photo_path': 'photos/rostov_city.jpg'},
}
# ==================== КУЛДАУН И ПРИМ ====================
def get_cooldown_hours(conquered_count):
    if conquered_count < 5: return 1.5
    elif conquered_count < 10: return 3
    elif conquered_count < 15: return 4
    elif conquered_count < 20: return 5
    else: return 6

def is_moscow_city(complex_name):
    return complex_name == 'Москва-Сити'

def check_prim(building):
    if is_moscow_city(building['complex']):
        return random.random() < 0.7
    else:
        return random.random() < 0.3

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  points INTEGER DEFAULT 0,
                  registered_date TEXT,
                  last_take_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conquered_buildings
                 (user_id INTEGER,
                  building_id TEXT,
                  conquered_date TEXT,
                  points_earned INTEGER,
                  PRIMARY KEY (user_id, building_id))''')
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name):
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, first_name, points, registered_date, last_take_time) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, username, first_name, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), None))
        conn.commit()
    conn.close()

def get_user_profile(user_id):
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    c.execute("SELECT points, first_name, last_take_time FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        conn.close()
        return None
    points, first_name, last_take_time = user_data
    c.execute('''SELECT b.building_id, b.name, b.complex, cb.conquered_date 
                 FROM conquered_buildings cb
                 JOIN buildings_info b ON cb.building_id = b.building_id
                 WHERE cb.user_id = ?
                 ORDER BY cb.conquered_date DESC''', (user_id,))
    conquered = c.fetchall()
    conquered_count = len(conquered)
    conn.close()
    return {
        'points': points,
        'first_name': first_name,
        'conquered': conquered,
        'conquered_count': conquered_count,
        'last_take_time': last_take_time
    }

def can_take_building(user_id, building_id):
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    c.execute("SELECT * FROM conquered_buildings WHERE user_id = ? AND building_id = ?", (user_id, building_id))
    if c.fetchone() is not None:
        conn.close()
        return False, "Ты уже брал этот ЖК!"
    c.execute("SELECT last_take_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result and result[0]:
        last_take = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        profile = get_user_profile(user_id)
        cooldown_hours = get_cooldown_hours(profile['conquered_count'])
        time_since_last = datetime.now() - last_take
        if time_since_last < timedelta(hours=cooldown_hours):
            remaining = timedelta(hours=cooldown_hours) - time_since_last
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            return False, f"Нужно подождать ещё {hours} ч {minutes} мин до следующего взятия!"
    return True, "Можно брать"

def take_building(user_id, building_id):
    building = buildings[building_id]
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    
    c.execute("SELECT last_take_time FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0]:
        last_take = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        profile = get_user_profile(user_id)
        cooldown_hours = get_cooldown_hours(profile['conquered_count'])
        time_since_last = datetime.now() - last_take
        if time_since_last < timedelta(hours=cooldown_hours):
            remaining = timedelta(hours=cooldown_hours) - time_since_last
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            conn.close()
            return False, f"Нужно подождать ещё {hours} ч {minutes} мин до следующего взятия!", False
            
    prim_active = check_prim(building)
    if prim_active:
    # Ставим КД даже после прима
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE users SET last_take_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
    
    # Определяем следующий кд
        profile = get_user_profile(user_id)
        next_cooldown = get_cooldown_hours(profile['conquered_count'])
    
        return False, f"⚠️ Ты не смог заруфать жк {building['name']} и тебя приняли! Следующая попытка через {next_cooldown} ч.", True
    points = building['points']
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO conquered_buildings (user_id, building_id, conquered_date, points_earned) VALUES (?, ?, ?, ?)",
              (user_id, building_id, current_time, points))
    c.execute("UPDATE users SET points = points + ?, last_take_time = ? WHERE user_id = ?", 
              (points, current_time, user_id))
    conn.commit()
    conn.close()
    profile = get_user_profile(user_id)
    next_cooldown = get_cooldown_hours(profile['conquered_count'])
    return True, f"✅ Ты взял {building['name']} и получил {points} очков!\n\nСледующее взятие будет доступно через {next_cooldown} ч.", False

def create_buildings_table():
    conn = sqlite3.connect('roofer_game.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS buildings_info
                 (building_id TEXT PRIMARY KEY,
                  name TEXT,
                  complex TEXT,
                  points INTEGER)''')
    for bid, info in buildings.items():
        c.execute("INSERT OR IGNORE INTO buildings_info (building_id, name, complex, points) VALUES (?, ?, ?, ?)",
                  (bid, info['name'], info['complex'], info['points']))
    conn.commit()
    conn.close()

# ==================== ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, from_menu: bool = False):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    keyboard = [
        [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
        [InlineKeyboardButton("📊 Портфолио", callback_data='profile')],
        [InlineKeyboardButton("⏰ Проверить таймер", callback_data='check_timer')]
    ]
    text = (
        f"Привет, {user.first_name}! Добро пожаловать в игру Руфер!\n\n"
        "⚠️ Важно: при попытке взять ЖК есть шанс, что тебя 'примут':\n"
        "• Обычные ЖК - 30%\n"
        "• Москва-Сити - 70%\n\n"
        "⏰ Кулдаун: 1.5–6 часов"
    )
    if from_menu:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_building(query, context, user_id, edit=True):
    available_buildings = context.user_data['available_buildings']
    current_index = context.user_data['current_index']
    building_id = available_buildings[current_index]
    building = buildings[building_id]
    context.user_data['current_building'] = building_id
    keyboard = [
        [InlineKeyboardButton("✅ Взять ЖК", callback_data='take_building')],
        [InlineKeyboardButton("⏭ Пропустить", callback_data='next_building')],
        [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    prim_chance = "70%" if is_moscow_city(building['complex']) else "30%"
    message_text = (
        f"🏢 {building['name']}\n"
        f"📍 Комплекс: {building['complex']}\n"
        f"💰 Очки: {building['points']}\n"
        f"⚠️ Шанс быть принятым: {prim_chance}\n"
    )
    try:
        with open(building['photo_path'], 'rb') as photo:
            if edit:
                await query.edit_message_media(media=InputMediaPhoto(photo, caption=message_text), reply_markup=reply_markup)
            else:
                await query.message.reply_photo(photo=photo, caption=message_text, reply_markup=reply_markup)
    except:
        await query.message.reply_text(message_text, reply_markup=reply_markup)
        
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    register_user(user.id, user.username, user.first_name)

    if query.data == 'roof_action':
        available_buildings = []
        for bid in buildings:
            can_take, _ = can_take_building(user.id, bid)
            if can_take:
                available_buildings.append(bid)
        if not available_buildings:
            keyboard = [
                [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
            ]
            await query.edit_message_text(
                "⏰ Нет доступных ЖК. Проверь таймер.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        random.shuffle(available_buildings)
        context.user_data['available_buildings'] = available_buildings
        context.user_data['current_index'] = 0
        await show_building(query, context, user.id)

    elif query.data == 'profile':
        profile = get_user_profile(user.id)
        if not profile:
            return
        text = f"📊 {profile['first_name']}\n💰 Очков: {profile['points']}\n🏆 Взято: {profile['conquered_count']}"
        keyboard = [
            [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
            [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'check_timer':
        profile = get_user_profile(user.id)
        if profile['last_take_time']:
            last_take = datetime.strptime(profile['last_take_time'], "%Y-%m-%d %H:%M:%S")
            cooldown = get_cooldown_hours(profile['conquered_count'])
            time_since = datetime.now() - last_take
            if time_since < timedelta(hours=cooldown):
                remaining = timedelta(hours=cooldown) - time_since
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                keyboard = [
                    [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
                ]
                await query.edit_message_text(
                    f"⏰ Осталось {hours} ч {minutes} мин",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard = [
                    [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
                    [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
                ]
                await query.edit_message_text(
                    "✅ Можно брать!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
    elif query.data == 'take_building':
        try:
            if 'current_building' not in context.user_data:
                await query.answer("Ошибка: ЖК не выбран", show_alert=True)
                return
            building_id = context.user_data['current_building']
            success, msg, prim = take_building(user.id, building_id)

            keyboard = [
                [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
                [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(msg, reply_markup=reply_markup)
        except:
            await query.message.reply_text(msg, reply_markup=reply_markup)
            await query.message.delete()
    
    elif query.data == 'menu':
        await start(update, context, from_menu=True)

    elif query.data == 'next_building':
        available = context.user_data.get('available_buildings', [])
        idx = context.user_data.get('current_index', 0)
        if idx + 1 < len(available):
            context.user_data['current_index'] = idx + 1
            await show_building(query, context, user.id, edit=False)
        else:
            keyboard = [
                [InlineKeyboardButton("🏢 Руфить!", callback_data='roof_action')],
                [InlineKeyboardButton("🏠 В меню", callback_data='menu')]
            ]
            await query.edit_message_text(
                "Больше нет ЖК",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

# ==================== ЗАПУСК ====================
def main():
    if not os.path.exists('photos'):
        os.makedirs('photos')
    init_db()
    create_buildings_table()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    ping_thread = threading.Thread(target=self_ping_thread, daemon=True)
    ping_thread.start()
    print("Бот запущен...")
    print(f"Всего ЖК: {len(buildings)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
