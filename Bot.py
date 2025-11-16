# ==============================
# MAGIC RPG BOT - ПОЛНЫЙ КОД НА AIOGRAM
# ==============================

import os
import asyncio
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==============================
# НАСТРОЙКА ТОКЕНА БОТА
# ==============================

# Получаем токен бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    # Если нет в переменных окружения, можно вписать прямо здесь
    BOT_TOKEN = "7417647142:AAFjTxYQEj3zAUKHjGuemIKmQ6OO9V-0yx0"  # ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ТОКЕН

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ==============================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ==============================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================
# КОНФИГУРАЦИЯ ИГРЫ
# ==============================

class GameConfig:
    MAX_LEVEL = 100
    START_GOLD = 1000
    START_SAPPHIRES = 5
    ENERGY_MAX = 100
    ENERGY_REGEN = 1  # в минуту

    # Классы персонажей
    CLASSES = {
        "mage": {
            "name": "🧙‍♂️ Маг",
            "health": 80,
            "mana": 150,
            "damage": 10,
            "defense": 5,
            "intellect": 20,
            "agility": 8
        },
        "warrior": {
            "name": "⚔️ Воин",
            "health": 150,
            "mana": 50,
            "damage": 18,
            "defense": 15,
            "intellect": 5,
            "agility": 6
        },
        "archer": {
            "name": "🏹 Лучник",
            "health": 100,
            "mana": 80,
            "damage": 15,
            "defense": 8,
            "intellect": 10,
            "agility": 18
        },
        "priest": {
            "name": "🙏 Жрец",
            "health": 120,
            "mana": 120,
            "damage": 12,
            "defense": 10,
            "intellect": 15,
            "agility": 10
        },
        "dark_mage": {
            "name": "🔮 Тёмный маг",
            "health": 70,
            "mana": 160,
            "damage": 14,
            "defense": 4,
            "intellect": 22,
            "agility": 9
        }
    }

    # Монстры для охоты
    MONSTERS = {
        "goblin": {"name": "🧌 Гоблин", "level": 1, "health": 50, "damage": 5, "gold": (10, 25)},
        "wolf": {"name": "🐺 Волк", "level": 3, "health": 70, "damage": 8, "gold": (15, 35)},
        "skeleton": {"name": "💀 Скелет", "level": 5, "health": 90, "damage": 12, "gold": (20, 50)},
        "orc": {"name": "👹 Орк", "level": 10, "health": 150, "damage": 18, "gold": (30, 80)}
    }

# ==============================
# СОСТОЯНИЯ ДЛЯ FSM
# ==============================

class PlayerStates(StatesGroup):
    choosing_name = State()
    choosing_class = State()
    in_battle = State()
    in_hunt = State()

# ==============================
# БАЗА ДАННЫХ
# ==============================

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('magic_rpg.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Игроки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                character_name TEXT,
                class TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                gold INTEGER DEFAULT 1000,
                sapphires INTEGER DEFAULT 5,
                health INTEGER DEFAULT 100,
                max_health INTEGER DEFAULT 100,
                mana INTEGER DEFAULT 100,
                max_mana INTEGER DEFAULT 100,
                damage INTEGER DEFAULT 10,
                defense INTEGER DEFAULT 5,
                intellect INTEGER DEFAULT 10,
                agility INTEGER DEFAULT 10,
                energy INTEGER DEFAULT 100,
                last_energy_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Предметы в инвентаре
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                item_type TEXT,
                rarity TEXT,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES players (user_id)
            )
        ''')

        self.conn.commit()

    def get_player(self, user_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None

    def create_player(self, user_id: int, username: str, character_name: str, character_class: str):
        cursor = self.conn.cursor()
        class_stats = GameConfig.CLASSES[character_class]

        cursor.execute('''
            INSERT INTO players
            (user_id, username, character_name, class, max_health, health, max_mana, mana, damage, defense, intellect, agility)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, username, character_name, character_class,
            class_stats['health'], class_stats['health'],
            class_stats['mana'], class_stats['mana'],
            class_stats['damage'], class_stats['defense'],
            class_stats['intellect'], class_stats['agility']
        ))
        self.conn.commit()

    def update_player_stats(self, user_id: int, updates: Dict):
        cursor = self.conn.cursor()
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]

        cursor.execute(f'UPDATE players SET {set_clause} WHERE user_id = ?', values)
        self.conn.commit()

# Инициализация базы данных
db = Database()

# ==============================
# СИСТЕМА ЕСТЕСТВЕННОГО ЯЗЫКА
# ==============================

class NaturalLanguageProcessor:
    @staticmethod
    def process_text(text: str) -> str:
        text = text.lower().strip()

        command_map = {
            # Профиль
            'профиль': 'profile', 'мой профиль': 'profile', 'статы': 'profile',
            'характеристики': 'profile', 'персонаж': 'profile',

            # Охота
            'охота': 'hunt', 'охотиться': 'hunt', 'монстры': 'hunt',
            'пойти на охоту': 'hunt', 'бить монстров': 'hunt',

            # Дуэли
            'дуэль': 'pvp', 'пвп': 'pvp', 'сразиться': 'pvp',
            'бой': 'pvp', 'поединок': 'pvp',

            # Помощь
            'помощь': 'help', 'команды': 'help', 'справка': 'help',
            'обучение': 'help', 'как играть': 'help'
        }

        return command_map.get(text, 'unknown')

# ==============================
# ОСНОВНЫЕ КОМАНДЫ БОТА
# ==============================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if player:
        # Игрок уже зарегистрирован
        await message.answer(
            f"🎮 С возвращением, {player['character_name']}!\n"
            f"Уровень: {player['level']} | Золото: {player['gold']} 💰\n\n"
            f"Напиши 'профиль' чтобы посмотреть свои характеристики или 'охота' чтобы начать приключение!"
        )
    else:
        # Новый игрок - начинаем регистрацию
        await state.set_state(PlayerStates.choosing_name)
        await message.answer(
            "🎮 Добро пожаловать в Magic RPG!\n\n"
            "Давай создадим твоего персонажа. Как тебя зовут, герой?"
        )
# ==============================
# ЧАСТЬ 2: РЕГИСТРАЦИЯ И ПРОФИЛЬ
# ==============================

# Обработчик выбора имени персонажа
@router.message(PlayerStates.choosing_name)
async def process_character_name(message: Message, state: FSMContext):
    character_name = message.text.strip()

    if len(character_name) < 2:
        await message.answer("❌ Имя должно содержать хотя бы 2 символа. Попробуй еще раз:")
        return

    if len(character_name) > 20:
        await message.answer("❌ Имя слишком длинное (макс. 20 символов). Попробуй еще раз:")
        return

    await state.update_data(character_name=character_name)
    await state.set_state(PlayerStates.choosing_class)

    # Создаем клавиатуру выбора класса
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧙‍♂️ Маг", callback_data="class_mage"),
            InlineKeyboardButton(text="⚔️ Воин", callback_data="class_warrior")
        ],
        [
            InlineKeyboardButton(text="🏹 Лучник", callback_data="class_archer"),
            InlineKeyboardButton(text="🙏 Жрец", callback_data="class_priest")
        ],
        [
            InlineKeyboardButton(text="🔮 Тёмный маг", callback_data="class_dark_mage")
        ]
    ])

    await message.answer(
        f"Отличное имя, {character_name}! 🎉\n\n"
        "Теперь выбери класс персонажа:",
        reply_markup=keyboard
    )

# Обработчик выбора класса
@router.callback_query(lambda c: c.data.startswith('class_'))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
    class_type = callback.data.replace('class_', '')
    user_data = await state.get_data()
    character_name = user_data['character_name']

    # Создаем игрока в базе данных
    db.create_player(
        user_id=callback.from_user.id,
        username=callback.from_user.username or callback.from_user.first_name,
        character_name=character_name,
        character_class=class_type
    )

    class_info = GameConfig.CLASSES[class_type]

    await callback.message.edit_text(
        f"🎊 Поздравляю, {character_name}!\n"
        f"Ты стал {class_info['name']}!\n\n"
        f"📊 Твои стартовые характеристики:\n"
        f"❤️ Здоровье: {class_info['health']}\n"
        f"🔮 Мана: {class_info['mana']}\n"
        f"⚔️ Урон: {class_info['damage']}\n"
        f"🛡️ Защита: {class_info['defense']}\n"
        f"🧠 Интеллект: {class_info['intellect']}\n"
        f"🎯 Ловкость: {class_info['agility']}\n\n"
        f"Напиши 'профиль' чтобы посмотреть свой профиль или 'охота' чтобы начать приключение!"
    )

    await state.clear()

# Команда /profile и ее текстовые аналоги
@router.message(Command('profile'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'profile')
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Рассчитываем опыт до следующего уровня
    exp_needed = player['level'] * 100
    exp_progress = min(player['experience'] / exp_needed * 100, 100) if exp_needed > 0 else 100

    class_info = GameConfig.CLASSES.get(player['class'], {})

    profile_text = (
        f"👤 **Профиль {player['character_name']}**\n"
        f"🎯 Уровень: {player['level']}\n"
        f"📊 Опыт: {player['experience']}/{exp_needed} ({exp_progress:.1f}%)\n"
        f"🎭 Класс: {class_info.get('name', 'Неизвестно')}\n\n"
        f"❤️ Здоровье: {player['health']}/{player['max_health']}\n"
        f"🔮 Мана: {player['mana']}/{player['max_mana']}\n"
        f"⚡ Энергия: {player['energy']}/{GameConfig.ENERGY_MAX}\n\n"
        f"📈 Характеристики:\n"
        f"⚔️ Урон: {player['damage']}\n"
        f"🛡️ Защита: {player['defense']}\n"
        f"🧠 Интеллект: {player['intellect']}\n"
        f"🎯 Ловкость: {player['agility']}\n\n"
        f"💰 Богатство:\n"
        f"Золото: {player['gold']} 💰\n"
        f"Сапфиры: {player['sapphires']} 💎"
    )

    # Кнопки для быстрых действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ На охоту", callback_data="hunt_start")],
        [InlineKeyboardButton(text="🔄 Восстановить энергию", callback_data="restore_energy")],
        [InlineKeyboardButton(text="📦 Инвентарь", callback_data="inventory")]
    ])

    await message.answer(profile_text, reply_markup=keyboard, parse_mode='Markdown')

# Обработчик восстановления энергии
@router.callback_query(lambda c: c.data == 'restore_energy')
async def restore_energy(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    if player['energy'] >= GameConfig.ENERGY_MAX:
        await callback.answer("⚡ У тебя уже полная энергия!", show_alert=True)
        return

    # Восстанавливаем энергию (1 сапфир = 50 энергии)
    if player['sapphires'] >= 1:
        db.update_player_stats(user_id, {
            'energy': GameConfig.ENERGY_MAX,
            'sapphires': player['sapphires'] - 1
        })
        await callback.answer("⚡ Энергия полностью восстановлена за 1 сапфир!", show_alert=True)

        # Обновляем сообщение профиля
        player = db.get_player(user_id)
        await update_profile_message(callback.message, player)
    else:
        await callback.answer("❌ Недостаточно сапфиров для восстановления энергии!", show_alert=True)

# Функция обновления сообщения профиля
async def update_profile_message(message: Message, player: Dict):
    exp_needed = player['level'] * 100
    exp_progress = min(player['experience'] / exp_needed * 100, 100) if exp_needed > 0 else 100
    class_info = GameConfig.CLASSES.get(player['class'], {})

    profile_text = (
        f"👤 **Профиль {player['character_name']}**\n"
        f"🎯 Уровень: {player['level']}\n"
        f"📊 Опыт: {player['experience']}/{exp_needed} ({exp_progress:.1f}%)\n"
        f"🎭 Класс: {class_info.get('name', 'Неизвестно')}\n\n"
        f"❤️ Здоровье: {player['health']}/{player['max_health']}\n"
        f"🔮 Мана: {player['mana']}/{player['max_mana']}\n"
        f"⚡ Энергия: {player['energy']}/{GameConfig.ENERGY_MAX}\n\n"
        f"💰 Богатство:\n"
        f"Золото: {player['gold']} 💰\n"
        f"Сапфиры: {player['sapphires']} 💎"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ На охоту", callback_data="hunt_start")],
        [InlineKeyboardButton(text="🔄 Восстановить энергию", callback_data="restore_energy")],
        [InlineKeyboardButton(text="📦 Инвентарь", callback_data="inventory")]
    ])

    await message.edit_text(profile_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# СИСТЕМА ИНВЕНТАРЯ
# ==============================

@router.callback_query(lambda c: c.data == 'inventory')
async def show_inventory(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получаем предметы из инвентаря
    cursor = db.conn.cursor()
    cursor.execute('SELECT item_name, item_type, rarity, quantity FROM inventory WHERE user_id = ?', (user_id,))
    items = cursor.fetchall()

    if not items:
        inventory_text = "📦 Твой инвентарь пуст.\n\nОтправляйся на охоту или открой кейсы чтобы получить предметы!"
    else:
        inventory_text = "📦 **Твой инвентарь:**\n\n"
        for item in items:
            item_name, item_type, rarity, quantity = item
            rarity_icon = get_rarity_icon(rarity)
            inventory_text += f"{rarity_icon} {item_name} ({item_type}) x{quantity}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="back_to_profile")],
        [InlineKeyboardButton(text="🎁 Открыть кейс", callback_data="open_case")]
    ])

    await callback.message.edit_text(inventory_text, reply_markup=keyboard, parse_mode='Markdown')

# Функция для получения иконки редкости
def get_rarity_icon(rarity: str) -> str:
    icons = {
        'common': '⚪',
        'uncommon': '🟢',
        'rare': '🔶',
        'epic': '🟣',
        'legendary': '🟡',
        'mythic': '❤️'
    }
    return icons.get(rarity, '⚪')

# Обработчик возврата к профилю
@router.callback_query(lambda c: c.data == 'back_to_profile')
async def back_to_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)
    await update_profile_message(callback.message, player)

# ==============================
# КОМАНДА ПОМОЩИ
# ==============================

@router.message(Command('help'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'help')
async def cmd_help(message: Message):
    help_text = (
        "🎮 **Magic RPG Bot - Помощь**\n\n"
        "📋 **Основные команды:**\n"
        "• /start - Начать игру\n"
        "• /profile - Профиль персонажа\n"
        "• /hunt - Охота на монстров\n"
        "• /pvp - PvP дуэли\n"
        "• /shop - Магазин\n"
        "• /help - Эта справка\n\n"

        "🗣️ **Можно писать текстом:**\n"
        "• 'профиль', 'статы', 'персонаж'\n"
        "• 'охота', 'монстры', 'охотиться'\n"
        "• 'дуэль', 'пвп', 'бой'\n"
        "• 'помощь', 'команды'\n\n"

        "🎯 **Советы для новичков:**\n"
        "1. Начни с охоты на монстров\n"
        "2. Участвуй в PvP для опыта\n"
        "3. Используй энергию wisely\n"
        "4. Присоединяйся к клану\n\n"

        "⚡ **Энергия:** Восстанавливается со временем (1/мин)\n"
        "💰 **Золото:** Основная валюта\n"
        "💎 **Сапфиры:** Редкая валюта\n\n"

        "Удачи в приключениях! 🎊"
    )

    await message.answer(help_text, parse_mode='Markdown')

# ==============================
# ЧАСТЬ 3: СИСТЕМА ОХОТЫ И БОЕВ
# ==============================

# Команда охоты и текстовые аналоги
@router.message(Command('hunt'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'hunt')
@router.callback_query(lambda c: c.data == 'hunt_start')
async def cmd_hunt(update: types.Update, state: FSMContext):
    if isinstance(update, CallbackQuery):
        message = update.message
        user_id = update.from_user.id
        await update.answer()
    else:
        message = update
        user_id = update.from_user.id

    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Проверяем энергию
    if player['energy'] < 10:
        await message.answer(
            "❌ Недостаточно энергии для охоты!\n"
            f"Нужно 10 энергии, у тебя: {player['energy']}\n\n"
            "Энергия восстанавливается со временем (1/мин) или можно восстановить за сапфиры."
        )
        return

    # Выбираем случайного монстра
    monster_name = random.choice(list(GameConfig.MONSTERS.keys()))
    monster = GameConfig.MONSTERS[monster_name]

    # Сохраняем состояние боя
    await state.set_state(PlayerStates.in_hunt)
    await state.update_data(
        monster=monster_name,
        monster_health=monster['health'],
        player_health=player['health'],
        player_mana=player['mana']
    )

    # Клавиатура для боя
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Атаковать", callback_data="hunt_attack"),
            InlineKeyboardButton(text="🔮 Магия", callback_data="hunt_magic")
        ],
        [
            InlineKeyboardButton(text="🛡️ Защита", callback_data="hunt_defend"),
            InlineKeyboardButton(text="🏃 Сбежать", callback_data="hunt_flee")
        ]
    ])

    battle_text = (
        f"🐺 **Встреча с {monster['name']}!**\n\n"
        f"📊 Характеристики монстра:\n"
        f"❤️ Здоровье: {monster['health']}\n"
        f"⚔️ Урон: {monster['damage']}\n"
        f"🎯 Уровень: {monster['level']}\n\n"
        f"Твои характеристики:\n"
        f"❤️ {player['health']}/{player['max_health']} | 🔮 {player['mana']}/{player['max_mana']}\n\n"
        f"Выбери действие:"
    )

    if isinstance(update, CallbackQuery):
        await message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(battle_text, reply_markup=keyboard, parse_mode='Markdown')

# Обработчик атаки в охоте
@router.callback_query(lambda c: c.data == 'hunt_attack', PlayerStates.in_hunt)
async def hunt_attack(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = db.get_player(user_id)
    battle_data = await state.get_data()

    monster_name = battle_data['monster']
    monster = GameConfig.MONSTERS[monster_name]
    monster_health = battle_data['monster_health']
    player_health = battle_data['player_health']

    # Игрок атакует
    player_damage = max(1, player['damage'] - random.randint(0, 5))
    monster_health -= player_damage

    battle_log = f"🎯 Ты атаковал {monster['name']} и нанес {player_damage} урона!\n"

    # Проверяем победу
    if monster_health <= 0:
        await handle_hunt_victory(callback, state, player, monster)
        return

    # Монстр атакует в ответ
    monster_damage = max(1, monster['damage'] - random.randint(0, player['defense'] // 3))
    player_health -= monster_damage
    battle_log += f"🐺 {monster['name']} атаковал тебя и нанес {monster_damage} урона!\n"

    # Проверяем поражение
    if player_health <= 0:
        await handle_hunt_defeat(callback, state, player)
        return

    # Обновляем состояние боя
    await state.update_data(
        monster_health=monster_health,
        player_health=player_health
    )

    # Продолжаем бой
    await continue_hunt_battle(callback, battle_log, monster, monster_health, player_health, player)

# Обработчик магической атаки
@router.callback_query(lambda c: c.data == 'hunt_magic', PlayerStates.in_hunt)
async def hunt_magic(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = db.get_player(user_id)
    battle_data = await state.get_data()

    monster_name = battle_data['monster']
    monster = GameConfig.MONSTERS[monster_name]
    monster_health = battle_data['monster_health']
    player_health = battle_data['player_health']
    player_mana = battle_data['player_mana']

    # Проверяем ману
    if player_mana < 20:
        await callback.answer("❌ Недостаточно маны для магической атаки!", show_alert=True)
        return

    # Магическая атака (сильнее, но тратит ману)
    magic_damage = max(1, player['intellect'] + random.randint(5, 15))
    monster_health -= magic_damage
    player_mana -= 20

    battle_log = f"🔮 Ты использовал магическую атаку и нанес {magic_damage} урона!\n"

    # Проверяем победу
    if monster_health <= 0:
        await state.update_data(player_mana=player_mana)
        await handle_hunt_victory(callback, state, player, monster)
        return

    # Монстр атакует
    monster_damage = max(1, monster['damage'] - random.randint(0, player['defense'] // 4))
    player_health -= monster_damage
    battle_log += f"🐺 {monster['name']} атаковал тебя и нанес {monster_damage} урона!\n"

    # Проверяем поражение
    if player_health <= 0:
        await state.update_data(player_mana=player_mana)
        await handle_hunt_defeat(callback, state, player)
        return

    # Обновляем состояние боя
    await state.update_data(
        monster_health=monster_health,
        player_health=player_health,
        player_mana=player_mana
    )

    # Продолжаем бой
    await continue_hunt_battle(callback, battle_log, monster, monster_health, player_health, player)

# Обработчик защиты
@router.callback_query(lambda c: c.data == 'hunt_defend', PlayerStates.in_hunt)
async def hunt_defend(callback: CallbackQuery, state: FSMContext):
    battle_data = await state.get_data()

    monster_name = battle_data['monster']
    monster = GameConfig.MONSTERS[monster_name]
    player_health = battle_data['player_health']

    # Защита уменьшает урон
    monster_damage = max(1, monster['damage'] // 2 - random.randint(0, 3))
    player_health -= monster_damage

    battle_log = f"🛡️ Ты защищаешься! Урон уменьшен.\n"
    battle_log += f"🐺 {monster['name']} атаковал и нанес {monster_damage} урона!\n"

    # Проверяем поражение
    if player_health <= 0:
        await handle_hunt_defeat(callback, state, db.get_player(callback.from_user.id))
        return

    # Обновляем состояние боя
    await state.update_data(player_health=player_health)

    # Продолжаем бой
    await continue_hunt_battle(callback, battle_log, monster, battle_data['monster_health'], player_health, db.get_player(callback.from_user.id))

# Обработчик побега
@router.callback_query(lambda c: c.data == 'hunt_flee', PlayerStates.in_hunt)
async def hunt_flee(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    # Шанс побега 70%
    if random.random() < 0.7:
        # Тратим энергию даже при побеге
        db.update_player_stats(user_id, {'energy': player['energy'] - 5})

        await callback.message.edit_text(
            "🏃 Ты успешно сбежал с поля боя!\n"
            f"Потрачено 5 энергии. Осталось: {player['energy'] - 5}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Снова на охоту", callback_data="hunt_start")],
                [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
            ])
        )
    else:
        # Не удалось сбежать
        battle_data = await state.get_data()
        monster = GameConfig.MONSTERS[battle_data['monster']]
        player_health = battle_data['player_health']

        # Монстр атакует при неудачном побеге
        monster_damage = max(1, monster['damage'] + random.randint(0, 5))
        player_health -= monster_damage

        battle_log = f"❌ Тебе не удалось сбежать!\n"
        battle_log += f"🐺 {monster['name']} атаковал и нанес {monster_damage} урона!\n"

        if player_health <= 0:
            await handle_hunt_defeat(callback, state, player)
        else:
            await state.update_data(player_health=player_health)
            await continue_hunt_battle(callback, battle_log, monster, battle_data['monster_health'], player_health, player)

    await state.clear()

# Продолжение боя после хода
async def continue_hunt_battle(callback: CallbackQuery, battle_log: str, monster: Dict, monster_health: int, player_health: int, player: Dict):
    battle_text = (
        f"{battle_log}\n"
        f"❤️ Твое здоровье: {player_health}/{player['max_health']}\n"
        f"❤️ Здоровье {monster['name']}: {monster_health}/{monster['health']}\n\n"
        f"Выбери следующее действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Атаковать", callback_data="hunt_attack"),
            InlineKeyboardButton(text="🔮 Магия", callback_data="hunt_magic")
        ],
        [
            InlineKeyboardButton(text="🛡️ Защита", callback_data="hunt_defend"),
            InlineKeyboardButton(text="🏃 Сбежать", callback_data="hunt_flee")
        ]
    ])

    await callback.message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')

# Обработчик победы в охоте
async def handle_hunt_victory(callback: CallbackQuery, state: FSMContext, player: Dict, monster: Dict):
    user_id = callback.from_user.id

    # Награды за победу
    gold_reward = random.randint(monster['gold'][0], monster['gold'][1])
    exp_reward = monster['level'] * 10

    # Шанс выпадения предмета (20%)
    item_drop = None
    if random.random() < 0.2:
        item_drop = get_random_item_drop(monster['level'])
        add_item_to_inventory(user_id, item_drop)

    # Обновляем статистику игрока
    new_exp = player['experience'] + exp_reward
    new_level = player['level']

    # Проверяем повышение уровня
    exp_needed = new_level * 100
    if new_exp >= exp_needed and new_level < GameConfig.MAX_LEVEL:
        new_level += 1
        new_exp = 0
        level_up_bonus = "🎊 **Повышение уровня!** Ты достиг уровня {new_level}!\n"
    else:
        level_up_bonus = ""

    db.update_player_stats(user_id, {
        'gold': player['gold'] + gold_reward,
        'experience': new_exp,
        'level': new_level,
        'energy': player['energy'] - 10,
        'health': player['max_health'],  # Восстанавливаем здоровье после боя
        'mana': player['max_mana']       # Восстанавливаем ману
    })

    victory_text = (
        f"🎉 **Победа!** Ты победил {monster['name']}!\n\n"
        f"🏆 Награды:\n"
        f"💰 Золото: +{gold_reward}\n"
        f"⭐ Опыт: +{exp_reward}\n"
        f"⚡ Энергия: -10\n\n"
        f"{level_up_bonus}"
    )

    if item_drop:
        victory_text += f"🎁 Выпал предмет: {item_drop['name']}!\n"

    victory_text += f"\nТвой баланс: {player['gold'] + gold_reward} золота"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Снова на охоту", callback_data="hunt_start")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(victory_text, reply_markup=keyboard, parse_mode='Markdown')
    await state.clear()

# Обработчик поражения в охоте
async def handle_hunt_defeat(callback: CallbackQuery, state: FSMContext, player: Dict):
    user_id = callback.from_user.id

    # Штраф за поражение
    gold_loss = min(player['gold'] // 10, 100)  # 10% но не более 100

    db.update_player_stats(user_id, {
        'gold': player['gold'] - gold_loss,
        'energy': max(0, player['energy'] - 5),
        'health': player['max_health'] // 2,  # Восстанавливаем половину здоровья
        'mana': player['max_mana'] // 2       # Восстанавливаем половину маны
    })

    defeat_text = (
        f"💀 **Поражение!** Ты был побежден в бою.\n\n"
        f"📉 Штрафы:\n"
        f"💰 Потеряно золота: {gold_loss}\n"
        f"⚡ Энергия: -5\n"
        f"❤️ Здоровье восстановлено до 50%\n"
        f"🔮 Мана восстановлена до 50%\n\n"
        f"Не отчаивайся! Подготовься лучше и возвращайся к бою!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Снова на охоту", callback_data="hunt_start")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(defeat_text, reply_markup=keyboard, parse_mode='Markdown')
    await state.clear()

# ==============================
# СИСТЕМА ПРЕДМЕТОВ
# ==============================

def get_random_item_drop(monster_level: int) -> Dict:
    # Базовые предметы которые могут выпасть
    items = [
        {"name": "⚔️ Ржавый меч", "type": "weapon", "rarity": "common", "damage": 5},
        {"name": "🛡️ Кожаный доспех", "type": "armor", "rarity": "common", "defense": 3},
        {"name": "🧪 Зелье здоровья", "type": "potion", "rarity": "common", "effect": "heal_50"},
        {"name": "🔮 Слабый посох", "type": "weapon", "rarity": "uncommon", "damage": 8, "intellect": 2},
        {"name": "🏹 Охотничий лук", "type": "weapon", "rarity": "uncommon", "damage": 7, "agility": 3}
    ]

    # Улучшаем предметы в зависимости от уровня монстра
    item = random.choice(items).copy()
    if monster_level > 5:
        if item['type'] == 'weapon':
            item['damage'] += monster_level // 3
        elif item['type'] == 'armor':
            item['defense'] += monster_level // 4

    return item

def add_item_to_inventory(user_id: int, item: Dict):
    cursor = db.conn.cursor()

    # Проверяем есть ли уже такой предмет
    cursor.execute(
        'SELECT id, quantity FROM inventory WHERE user_id = ? AND item_name = ?',
        (user_id, item['name'])
    )
    existing = cursor.fetchone()

    if existing:
        # Увеличиваем количество
        cursor.execute(
            'UPDATE inventory SET quantity = quantity + 1 WHERE id = ?',
            (existing[0],)
        )
    else:
        # Добавляем новый предмет
        cursor.execute(
            'INSERT INTO inventory (user_id, item_name, item_type, rarity) VALUES (?, ?, ?, ?)',
            (user_id, item['name'], item['type'], item['rarity'])
        )

    db.conn.commit()
# ==============================
# ЧАСТЬ 4: PvP СИСТЕМА И ДУЭЛИ
# ==============================

# Добавляем таблицу PvP рейтингов в базу данных
def create_pvp_tables():
    cursor = db.conn.cursor()

    # Таблица PvP рейтингов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pvp_ratings (
            user_id INTEGER PRIMARY KEY,
            rating INTEGER DEFAULT 1000,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            last_pvp_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица активных PvP боев
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pvp_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER,
            player2_id INTEGER,
            player1_health INTEGER,
            player2_health INTEGER,
            player1_mana INTEGER,
            player2_mana INTEGER,
            current_turn INTEGER DEFAULT 1,
            battle_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES players (user_id),
            FOREIGN KEY (player2_id) REFERENCES players (user_id)
        )
    ''')

    db.conn.commit()

# Вызываем создание таблиц при инициализации
create_pvp_tables()

# Команда PvP и текстовые аналоги
@router.message(Command('pvp'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'pvp')
async def cmd_pvp(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Проверяем здоровье
    if player['health'] < player['max_health'] * 0.5:
        await message.answer(
            "❌ Слишком мало здоровья для PvP!\n"
            f"Твое здоровье: {player['health']}/{player['max_health']}\n"
            "Восстанови здоровье перед боем."
        )
        return

    # Получаем или создаем PvP рейтинг
    cursor = db.conn.cursor()
    cursor.execute('SELECT rating, wins, losses FROM pvp_ratings WHERE user_id = ?', (user_id,))
    pvp_stats = cursor.fetchone()

    if not pvp_stats:
        cursor.execute('INSERT INTO pvp_ratings (user_id) VALUES (?)', (user_id,))
        db.conn.commit()
        rating, wins, losses = 1000, 0, 0
    else:
        rating, wins, losses = pvp_stats

    pvp_text = (
        f"⚔️ **PvP Арена**\n\n"
        f"📊 Твоя статистика:\n"
        f"🏆 Рейтинг: {rating}\n"
        f"✅ Побед: {wins}\n"
        f"❌ Поражений: {losses}\n\n"
        f"Выбери тип дуэли:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти противника", callback_data="pvp_find")],
        [InlineKeyboardButton(text="📊 Топ игроков", callback_data="pvp_top")],
        [InlineKeyboardButton(text="👤 Тренировка с ботом", callback_data="pvp_bot")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
    ])

    await message.answer(pvp_text, reply_markup=keyboard, parse_mode='Markdown')

# Поиск противника для PvP
@router.callback_query(lambda c: c.data == 'pvp_find')
async def pvp_find_opponent(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    # Получаем рейтинг игрока
    cursor = db.conn.cursor()
    cursor.execute('SELECT rating FROM pvp_ratings WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    player_rating = result[0] if result else 1000

    # Ищем противника с близким рейтингом (±100)
    cursor.execute('''
        SELECT user_id, username, rating FROM pvp_ratings
        JOIN players ON pvp_ratings.user_id = players.user_id
        WHERE user_id != ? AND rating BETWEEN ? AND ?
        ORDER BY ABS(rating - ?)
        LIMIT 1
    ''', (user_id, player_rating - 100, player_rating + 100, player_rating))

    opponent = cursor.fetchone()

    if opponent:
        # Нашли противника - начинаем бой
        opponent_id, opponent_username, opponent_rating = opponent
        await start_pvp_battle(callback, user_id, opponent_id, opponent_username, opponent_rating)
    else:
        # Не нашли противника - предлагаем бота
        await callback.message.edit_text(
            "🔍 Поиск противника...\n\n"
            "❌ Не удалось найти живого противника с близким рейтингом.\n\n"
            "Хочешь сразиться с ботом для тренировки?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Сразиться с ботом", callback_data="pvp_bot")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_back")]
            ])
        )

# Тренировка с ботом
@router.callback_query(lambda c: c.data == 'pvp_bot')
async def pvp_bot_battle(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    # Создаем бота-противника на основе уровня игрока
    bot_level = player['level']
    bot_stats = {
        'health': 80 + bot_level * 5,
        'damage': 10 + bot_level * 2,
        'defense': 5 + bot_level,
        'intellect': 8 + bot_level,
        'agility': 8 + bot_level,
        'mana': 60 + bot_level * 3
    }

    # Сохраняем бой в базу
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO pvp_battles (player1_id, player2_id, player1_health, player2_health, player1_mana, player2_mana)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, 0, player['health'], bot_stats['health'], player['mana'], bot_stats['mana']))

    battle_id = cursor.lastrowid
    db.conn.commit()

    await start_pvp_battle_display(callback, battle_id, player, bot_stats, is_bot=True)

# Топ игроков PvP
@router.callback_query(lambda c: c.data == 'pvp_top')
async def pvp_top_players(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.character_name, pr.rating, pr.wins, pr.losses
        FROM pvp_ratings pr
        JOIN players p ON pr.user_id = p.user_id
        ORDER BY pr.rating DESC
        LIMIT 10
    ''')

    top_players = cursor.fetchall()

    top_text = "🏆 **Топ 10 игроков PvP**\n\n"

    for i, (name, rating, wins, losses) in enumerate(top_players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        top_text += f"{medal} {name} - {rating} 📊 ({wins}/{losses}, {win_rate:.1f}%)\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Найти бой", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_back")]
    ])

    await callback.message.edit_text(top_text, reply_markup=keyboard, parse_mode='Markdown')

# Начало PvP боя
async def start_pvp_battle(callback: CallbackQuery, player1_id: int, player2_id: int, opponent_username: str, opponent_rating: int):
    player1 = db.get_player(player1_id)
    player2 = db.get_player(player2_id)

    # Сохраняем бой в базу
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO pvp_battles (player1_id, player2_id, player1_health, player2_health, player1_mana, player2_mana)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (player1_id, player2_id, player1['health'], player2['health'], player1['mana'], player2['mana']))

    battle_id = cursor.lastrowid
    db.conn.commit()

    # Уведомляем обоих игроков
    battle_text = (
        f"⚔️ **Дуэль началась!**\n\n"
        f"🎯 {player1['character_name']} vs {player2['character_name']}\n"
        f"🏆 Рейтинг: {get_pvp_rating(player1_id)} vs {opponent_rating}\n\n"
        f"Бой начинается!"
    )

    await callback.message.edit_text(battle_text, parse_mode='Markdown')

    # Отправляем сообщение второму игроку
    try:
        await bot.send_message(
            player2_id,
            f"⚔️ Тебя вызвали на дуэль! {player1['character_name']} бросает тебе вызов!\n\n"
            f"Напиши 'дуэль' чтобы принять бой!",
            parse_mode='Markdown'
        )
    except:
        pass  # Игрок может заблокировать бота

    # Запускаем бой
    await start_pvp_battle_display(callback, battle_id, player1, player2)

# Отображение PvP боя
async def start_pvp_battle_display(callback: CallbackQuery, battle_id: int, player1: Dict, player2: Dict, is_bot: bool = False):
    battle_text = (
        f"⚔️ **PvP Дуэль**\n\n"
        f"👤 {player1['character_name']}\n"
        f"❤️ {player1['health']}/{player1['max_health']} | 🔮 {player1['mana']}/{player1['max_mana']}\n\n"
        f"⚡ VS ⚡\n\n"
    )

    if is_bot:
        battle_text += f"🤖 Бот-противник\n❤️ {player2['health']} | 🔮 {player2['mana']}\n\n"
    else:
        battle_text += f"👤 {player2['character_name']}\n❤️ {player2['health']}/{player2['max_health']} | 🔮 {player2['mana']}/{player2['max_mana']}\n\n"

    battle_text += "Выбери действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Атака", callback_data=f"pvp_attack_{battle_id}"),
            InlineKeyboardButton(text="🔮 Магия", callback_data=f"pvp_magic_{battle_id}")
        ],
        [
            InlineKeyboardButton(text="🛡️ Защита", callback_data=f"pvp_defend_{battle_id}"),
            InlineKeyboardButton(text="💥 Ультимейт", callback_data=f"pvp_ultimate_{battle_id}")
        ]
    ])

    await callback.message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')

# Обработчик PvP атаки
@router.callback_query(lambda c: c.data.startswith('pvp_attack_'))
async def pvp_attack(callback: CallbackQuery):
    battle_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM pvp_battles WHERE id = ?', (battle_id,))
    battle = cursor.fetchone()

    if not battle:
        await callback.answer("❌ Бой не найден!", show_alert=True)
        return

    # Определяем кто атакует
    if battle[1] == user_id:  # player1
        attacker_id, defender_id = battle[1], battle[2]
        attacker_health, defender_health = battle[3], battle[4]
        attacker_mana, defender_mana = battle[5], battle[6]
    else:  # player2
        attacker_id, defender_id = battle[2], battle[1]
        attacker_health, defender_health = battle[4], battle[3]
        attacker_mana, defender_mana = battle[6], battle[5]

    attacker = db.get_player(attacker_id)
    defender = db.get_player(defender_id)

    # Атака
    damage = max(1, attacker['damage'] - random.randint(0, defender['defense'] // 2))
    defender_health -= damage

    battle_log = f"⚔️ {attacker['character_name']} атаковал и нанес {damage} урона!\n"

    # Проверяем победу
    if defender_health <= 0:
        await finish_pvp_battle(callback, battle_id, attacker_id, defender_id, battle_log)
        return

    # Обновляем бой в базе
    if battle[1] == user_id:
        cursor.execute('UPDATE pvp_battles SET player2_health = ?, battle_log = ? WHERE id = ?',
                     (defender_health, battle_log, battle_id))
    else:
        cursor.execute('UPDATE pvp_battles SET player1_health = ?, battle_log = ? WHERE id = ?',
                     (defender_health, battle_log, battle_id))

    db.conn.commit()

    # Передаем ход
    await continue_pvp_battle(callback, battle_id, is_bot=(defender_id == 0))

# Завершение PvP боя
async def finish_pvp_battle(callback: CallbackQuery, battle_id: int, winner_id: int, loser_id: int, battle_log: str):
    cursor = db.conn.cursor()

    # Обновляем рейтинги
    winner_rating = get_pvp_rating(winner_id)
    loser_rating = get_pvp_rating(loser_id)

    # Рассчитываем изменение рейтинга
    rating_change = calculate_rating_change(winner_rating, loser_rating)

    # Обновляем статистику
    cursor.execute('UPDATE pvp_ratings SET rating = rating + ?, wins = wins + 1 WHERE user_id = ?',
                  (rating_change, winner_id))
    cursor.execute('UPDATE pvp_ratings SET rating = rating - ?, losses = losses + 1 WHERE user_id = ?',
                  (rating_change, loser_id))

    # Награды за победу
    winner = db.get_player(winner_id)
    gold_reward = rating_change * 2
    exp_reward = 50

    db.update_player_stats(winner_id, {
        'gold': winner['gold'] + gold_reward,
        'experience': winner['experience'] + exp_reward,
        'health': winner['max_health'],  # Полное восстановление
        'mana': winner['max_mana']
    })

    # Удаляем бой из базы
    cursor.execute('DELETE FROM pvp_battles WHERE id = ?', (battle_id,))
    db.conn.commit()

    victory_text = (
        f"🎉 **Победа в PvP!**\n\n"
        f"{battle_log}\n"
        f"🏆 Награды:\n"
        f"💰 Золото: +{gold_reward}\n"
        f"⭐ Опыт: +{exp_reward}\n"
        f"📈 Рейтинг: +{rating_change}\n\n"
        f"Поздравляем с победой!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data="pvp_find")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(victory_text, reply_markup=keyboard, parse_mode='Markdown')

# Продолжение PvP боя
async def continue_pvp_battle(callback: CallbackQuery, battle_id: int, is_bot: bool = False):
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM pvp_battles WHERE id = ?', (battle_id,))
    battle = cursor.fetchone()

    if not battle:
        return

    player1 = db.get_player(battle[1])
    player2_data = db.get_player(battle[2]) if not is_bot else {'character_name': 'Бот-противник'}

    battle_text = (
        f"⚔️ **PvP Дуэль**\n\n"
        f"👤 {player1['character_name']}\n"
        f"❤️ {battle[3]}/{player1['max_health']} | 🔮 {battle[5]}/{player1['max_mana']}\n\n"
        f"⚡ VS ⚡\n\n"
        f"👤 {player2_data['character_name']}\n"
        f"❤️ {battle[4]}/{player2_data.get('max_health', 100)} | 🔮 {battle[6]}/{player2_data.get('max_mana', 100)}\n\n"
    )

    if battle[7]:  # battle_log
        battle_text += f"📜 {battle[7]}\n\n"

    battle_text += "Выбери действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Атака", callback_data=f"pvp_attack_{battle_id}"),
            InlineKeyboardButton(text="🔮 Магия", callback_data=f"pvp_magic_{battle_id}")
        ],
        [
            InlineKeyboardButton(text="🛡️ Защита", callback_data=f"pvp_defend_{battle_id}"),
            InlineKeyboardButton(text="💥 Ультимейт", callback_data=f"pvp_ultimate_{battle_id}")
        ]
    ])

    await callback.message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')

# Вспомогательные функции PvP
def get_pvp_rating(user_id: int) -> int:
    cursor = db.conn.cursor()
    cursor.execute('SELECT rating FROM pvp_ratings WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 1000

def calculate_rating_change(winner_rating: int, loser_rating: int) -> int:
    expected = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    return int(32 * (1 - expected))

# Назад в PvP меню
@router.callback_query(lambda c: c.data == 'pvp_back')
async def pvp_back(callback: CallbackQuery):
    await cmd_pvp(callback.message)

# ==============================
# ЧАСТЬ 5: КЛАНЫ И ШАХТЫ
# ==============================

# Добавляем таблицы для кланов и шахт
def create_clan_and_mine_tables():
    cursor = db.conn.cursor()

    # Таблица улучшений замка
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS castle_upgrades (
            clan_id INTEGER PRIMARY KEY,
            main_hall INTEGER DEFAULT 1,
            walls INTEGER DEFAULT 1,
            barracks INTEGER DEFAULT 1,
            magic_tower INTEGER DEFAULT 1,
            treasury INTEGER DEFAULT 1,
            warehouse INTEGER DEFAULT 1,
            last_attack DATETIME,
            FOREIGN KEY (clan_id) REFERENCES clans (id)
        )
    ''')

    # Таблица шахт игроков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_mines (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 1,
            income_per_hour INTEGER DEFAULT 100,
            last_collected DATETIME DEFAULT CURRENT_TIMESTAMP,
            storage INTEGER DEFAULT 0,
            max_storage INTEGER DEFAULT 1000,
            guard_level INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица атак на шахты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mine_attacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id INTEGER,
            target_id INTEGER,
            success BOOLEAN,
            resources_stolen INTEGER,
            guard_damage INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (attacker_id) REFERENCES players (user_id),
            FOREIGN KEY (target_id) REFERENCES players (user_id)
        )
    ''')

    db.conn.commit()

# Вызываем создание таблиц
create_clan_and_mine_tables()

# ==============================
# СИСТЕМА КЛАНОВ
# ==============================

@router.message(Command('clan'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'клан')
async def cmd_clan(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Проверяем состоит ли игрок в клане
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT c.id, c.name, c.level, cm.role
        FROM clans c
        JOIN clan_members cm ON c.id = cm.clan_id
        WHERE cm.user_id = ?
    ''', (user_id,))

    clan_data = cursor.fetchone()

    if clan_data:
        # Игрок в клане - показываем информацию
        clan_id, clan_name, clan_level, role = clan_data
        await show_clan_info(message, clan_id, clan_name, clan_level, role, user_id)
    else:
        # Игрок не в клане - предлагаем создать или вступить
        await show_clan_creation(message)

async def show_clan_info(message: Message, clan_id: int, clan_name: str, clan_level: int, role: str, user_id: int):
    cursor = db.conn.cursor()

    # Получаем количество участников
    cursor.execute('SELECT COUNT(*) FROM clan_members WHERE clan_id = ?', (clan_id,))
    member_count = cursor.fetchone()[0]

    # Получаем информацию об улучшениях замка
    cursor.execute('SELECT * FROM castle_upgrades WHERE clan_id = ?', (clan_id,))
    upgrades = cursor.fetchone()

    clan_text = (
        f"🏰 **Клан {clan_name}**\n\n"
        f"🎯 Уровень: {clan_level}\n"
        f"👥 Участников: {member_count}/20\n"
        f"👑 Твоя роль: {get_role_icon(role)} {role}\n\n"
        f"🏯 Улучшения замка:\n"
    )

    if upgrades:
        clan_text += (
            f"🏛️ Главный зал: Ур. {upgrades[1]}\n"
            f"🛡️ Стены: Ур. {upgrades[2]}\n"
            f"⚔️ Казармы: Ур. {upgrades[3]}\n"
            f"🔮 Магическая башня: Ур. {upgrades[4]}\n"
            f"💰 Казна: Ур. {upgrades[5]}\n"
            f"📦 Склад: Ур. {upgrades[6]}\n"
        )

    keyboard_buttons = []

    if role in ['owner', 'officer']:
        keyboard_buttons.append([InlineKeyboardButton(text="🛠️ Управление кланом", callback_data=f"clan_manage_{clan_id}")])

    keyboard_buttons.extend([
        [InlineKeyboardButton(text="👥 Список участников", callback_data=f"clan_members_{clan_id}")],
        [InlineKeyboardButton(text="🏯 Улучшить замок", callback_data=f"clan_upgrade_{clan_id}")],
        [InlineKeyboardButton(text="⚔️ Клановые войны", callback_data=f"clan_wars_{clan_id}")],
        [InlineKeyboardButton(text="❌ Покинуть клан", callback_data=f"clan_leave_{clan_id}")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(clan_text, reply_markup=keyboard, parse_mode='Markdown')

async def show_clan_creation(message: Message):
    clan_text = (
        "🏰 **Клановая система**\n\n"
        "Присоединяйся к клану чтобы:\n"
        "• 🏯 Строить и улучшать замок\n"
        "• ⚔️ Участвовать в клановых войнах\n"
        "• 👥 Получать бонусы от участников\n"
        "• 💰 Совместно зарабатывать ресурсы\n\n"
        "Выбери действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Создать клан", callback_data="clan_create")],
        [InlineKeyboardButton(text="🔍 Найти клан", callback_data="clan_search")],
        [InlineKeyboardButton(text="📊 Топ кланов", callback_data="clan_top")]
    ])

    await message.answer(clan_text, reply_markup=keyboard, parse_mode='Markdown')

# Создание клана
@router.callback_query(lambda c: c.data == 'clan_create')
async def clan_create_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    # Проверяем уровень игрока
    if player['level'] < 10:
        await callback.answer("❌ Для создания клана нужен 10+ уровень!", show_alert=True)
        return

    # Проверяем стоимость создания
    if player['gold'] < 5000:
        await callback.answer("❌ Для создания клана нужно 5000 золота!", show_alert=True)
        return

    await callback.message.edit_text(
        "🏰 **Создание клана**\n\n"
        "Придумай название для своего клана (3-20 символов):"
    )

    await state.set_state("waiting_clan_name")

@router.message(lambda message: len(message.text) >= 3 and len(message.text) <= 20)
async def process_clan_name(message: Message, state: FSMContext):
    clan_name = message.text.strip()
    user_id = message.from_user.id

    # Проверяем уникальность имени
    cursor = db.conn.cursor()
    cursor.execute('SELECT id FROM clans WHERE name = ?', (clan_name,))
    if cursor.fetchone():
        await message.answer("❌ Клан с таким названием уже существует! Выбери другое:")
        return

    # Создаем клан
    cursor.execute('INSERT INTO clans (name, owner_id) VALUES (?, ?)', (clan_name, user_id))
    clan_id = cursor.lastrowid

    # Добавляем создателя в клан как владельца
    cursor.execute('INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, ?)',
                  (clan_id, user_id, 'owner'))

    # Создаем начальные улучшения замка
    cursor.execute('INSERT INTO castle_upgrades (clan_id) VALUES (?)', (clan_id,))

    # Списываем золото
    player = db.get_player(user_id)
    db.update_player_stats(user_id, {'gold': player['gold'] - 5000})

    db.conn.commit()

    await message.answer(
        f"🎉 Поздравляю! Ты создал клан **{clan_name}**!\n\n"
        f"Теперь ты можешь:\n"
        f"• Приглашать других игроков\n"
        f"• Улучшать замок\n"
        f"• Участвовать в клановых войнах\n\n"
        f"Напиши 'клан' чтобы управлять своим кланом."
    )

    await state.clear()

# ==============================
# СИСТЕМА ШАХТ
# ==============================

@router.message(Command('mine'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'шахта')
async def cmd_mine(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Получаем или создаем шахту игрока
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM player_mines WHERE user_id = ?', (user_id,))
    mine_data = cursor.fetchone()

    if not mine_data:
        # Создаем начальную шахту
        cursor.execute('''
            INSERT INTO player_mines (user_id, level, income_per_hour, max_storage)
            VALUES (?, 1, 100, 1000)
        ''', (user_id,))
        db.conn.commit()
        mine_data = (user_id, 1, 100, None, 0, 1000, 0)

    user_id, level, income_per_hour, last_collected, storage, max_storage, guard_level = mine_data

    # Рассчитываем накопленные ресурсы
    if last_collected:
        last_collected_dt = datetime.fromisoformat(last_collected)
        hours_passed = (datetime.now() - last_collected_dt).total_seconds() / 3600
        resources_accumulated = min(int(hours_passed * income_per_hour), max_storage - storage)
    else:
        resources_accumulated = 0

    total_resources = storage + resources_accumulated

    mine_text = (
        f"⛏️ **Твоя шахта**\n\n"
        f"📊 Уровень: {level}\n"
        f"💰 Доход в час: {income_per_hour} золота\n"
        f"📦 Накоплено: {total_resources}/{max_storage} золота\n"
        f"🛡️ Уровень защиты: {guard_level}\n\n"
    )

    if resources_accumulated > 0:
        mine_text += f"💎 Можно собрать: {resources_accumulated} золота\n\n"

    mine_text += "Выбери действие:"

    keyboard_buttons = []

    if resources_accumulated > 0:
        keyboard_buttons.append([InlineKeyboardButton(text="💎 Собрать ресурсы", callback_data="mine_collect")])

    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🆙 Улучшить шахту", callback_data="mine_upgrade")],
        [InlineKeyboardButton(text="🛡️ Улучшить защиту", callback_data="mine_guard")],
        [InlineKeyboardButton(text="⚔️ Атаковать шахту", callback_data="mine_attack")],
        [InlineKeyboardButton(text="📊 Статистика атак", callback_data="mine_stats")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(mine_text, reply_markup=keyboard, parse_mode='Markdown')

# Сбор ресурсов с шахты
@router.callback_query(lambda c: c.data == 'mine_collect')
async def mine_collect(callback: CallbackQuery):
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM player_mines WHERE user_id = ?', (user_id,))
    mine_data = cursor.fetchone()

    if not mine_data:
        await callback.answer("❌ Шахта не найдена!", show_alert=True)
        return

    user_id, level, income_per_hour, last_collected, storage, max_storage, guard_level = mine_data

    # Рассчитываем накопленные ресурсы
    if last_collected:
        last_collected_dt = datetime.fromisoformat(last_collected)
        hours_passed = (datetime.now() - last_collected_dt).total_seconds() / 3600
        resources_accumulated = min(int(hours_passed * income_per_hour), max_storage - storage)
    else:
        resources_accumulated = 0

    if resources_accumulated <= 0:
        await callback.answer("❌ Нечего собирать! Подожди пока накопится больше ресурсов.", show_alert=True)
        return

    # Добавляем золото игроку
    player = db.get_player(user_id)
    db.update_player_stats(user_id, {'gold': player['gold'] + resources_accumulated})

    # Обновляем шахту
    cursor.execute('''
        UPDATE player_mines
        SET storage = 0, last_collected = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (user_id,))
    db.conn.commit()

    await callback.message.edit_text(
        f"💎 Ты собрал {resources_accumulated} золота с шахты!\n\n"
        f"💰 Твой баланс: {player['gold'] + resources_accumulated} золота\n\n"
        f"Шахта продолжает работать...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ К шахте", callback_data="mine_back")],
            [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
        ])
    )

# Улучшение шахты
@router.callback_query(lambda c: c.data == 'mine_upgrade')
async def mine_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM player_mines WHERE user_id = ?', (user_id,))
    mine_data = cursor.fetchone()

    if not mine_data:
        await callback.answer("❌ Шахта не найдена!", show_alert=True)
        return

    user_id, level, income_per_hour, last_collected, storage, max_storage, guard_level = mine_data

    # Стоимость улучшения
    upgrade_cost = level * 2000
    next_income = income_per_hour + 50
    next_storage = max_storage + 500

    if player['gold'] < upgrade_cost:
        await callback.answer(f"❌ Недостаточно золота! Нужно {upgrade_cost} золота.", show_alert=True)
        return

    if level >= 5:
        await callback.answer("❌ Достигнут максимальный уровень шахты!", show_alert=True)
        return

    # Улучшаем шахту
    cursor.execute('''
        UPDATE player_mines
        SET level = level + 1, income_per_hour = ?, max_storage = ?
        WHERE user_id = ?
    ''', (next_income, next_storage, user_id))

    # Списываем золото
    db.update_player_stats(user_id, {'gold': player['gold'] - upgrade_cost})
    db.conn.commit()

    await callback.message.edit_text(
        f"🆙 Шахта улучшена до уровня {level + 1}!\n\n"
        f"📈 Новый доход: {next_income} золота/час\n"
        f"📦 Вместимость: {next_storage} золота\n"
        f"💰 Потрачено: {upgrade_cost} золота\n\n"
        f"Следующее улучшение будет стоить {upgrade_cost + 2000} золота",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ К шахте", callback_data="mine_back")],
            [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
        ])
    )

# Атака на шахту другого игрока
@router.callback_query(lambda c: c.data == 'mine_attack')
async def mine_attack(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    # Проверяем уровень игрока
    if player['level'] < 5:
        await callback.answer("❌ Для атак на шахты нужен 5+ уровень!", show_alert=True)
        return

    # Ищем цели для атаки (игроки с ресурсами и не в нашем клане)
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT pm.user_id, p.character_name, pm.level, pm.storage, pm.guard_level
        FROM player_mines pm
        JOIN players p ON pm.user_id = p.user_id
        WHERE pm.user_id != ? AND pm.storage > 100
        ORDER BY pm.storage DESC
        LIMIT 5
    ''', (user_id,))

    targets = cursor.fetchall()

    if not targets:
        await callback.answer("❌ Нет подходящих целей для атаки!", show_alert=True)
        return

    attack_text = "⚔️ **Выбери цель для атаки:**\n\n"

    keyboard_buttons = []
    for target in targets:
        target_id, target_name, target_level, target_storage, target_guard = target
        attack_text += f"👤 {target_name} | ⛏️ Ур.{target_level} | 💰 {target_storage} | 🛡️ {target_guard}\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"⚔️ Атаковать {target_name}",
                callback_data=f"mine_attack_{target_id}"
            )
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="mine_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(attack_text, reply_markup=keyboard)

# Обработка атаки на конкретную шахту
@router.callback_query(lambda c: c.data.startswith('mine_attack_'))
async def mine_attack_target(callback: CallbackQuery):
    attacker_id = callback.from_user.id
    target_id = int(callback.data.split('_')[2])

    attacker = db.get_player(attacker_id)
    target_mine = get_player_mine(target_id)

    if not target_mine:
        await callback.answer("❌ Цель не найдена!", show_alert=True)
        return

    # Расчет шанса успеха
    guard_protection = target_mine[6] * 10  # Каждый уровень защиты дает +10% защиты
    success_chance = max(10, 70 - guard_protection)

    if random.randint(1, 100) <= success_chance:
        # Успешная атака
        stolen_resources = min(target_mine[4] // 3, 500)  # Крадем до 33% но не более 500
        damage_to_guard = random.randint(1, 3)

        # Обновляем шахту цели
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE player_mines
            SET storage = storage - ?, guard_level = GREATEST(0, guard_level - ?)
            WHERE user_id = ?
        ''', (stolen_resources, damage_to_guard, target_id))

        # Даем ресурсы атакующему
        db.update_player_stats(attacker_id, {'gold': attacker['gold'] + stolen_resources})

        # Записываем атаку
        cursor.execute('''
            INSERT INTO mine_attacks (attacker_id, target_id, success, resources_stolen, guard_damage)
            VALUES (?, ?, ?, ?, ?)
        ''', (attacker_id, target_id, True, stolen_resources, damage_to_guard))

        result_text = (
            f"🎉 **Успешная атака!**\n\n"
            f"💰 Украдено: {stolen_resources} золота\n"
            f"🛡️ Нанесен урон защите: -{damage_to_guard} уровня\n"
            f"💎 Твой баланс: {attacker['gold'] + stolen_resources} золота"
        )
    else:
        # Неудачная атака
        cursor = db.conn.cursor()
        cursor.execute('''
            INSERT INTO mine_attacks (attacker_id, target_id, success, resources_stolen, guard_damage)
            VALUES (?, ?, ?, ?, ?)
        ''', (attacker_id, target_id, False, 0, 0))

        result_text = "❌ **Атака отражена!** Защита шахты оказалась слишком сильной."

    db.conn.commit()

    await callback.message.edit_text(
        result_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⛏️ К шахте", callback_data="mine_back")],
            [InlineKeyboardButton(text="⚔️ Новая атака", callback_data="mine_attack")]
        ])
    )

# Вспомогательные функции
def get_role_icon(role: str) -> str:
    icons = {
        'owner': '👑',
        'officer': '⭐',
        'member': '👤',
        'recruit': '🆕'
    }
    return icons.get(role, '👤')

def get_player_mine(user_id: int):
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM player_mines WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

# Назад к шахте
@router.callback_query(lambda c: c.data == 'mine_back')
async def mine_back(callback: CallbackQuery):
    await cmd_mine(callback.message)

## ==============================
# ЧАСТЬ 6: МАГАЗИН, КЕЙСЫ И ЭКОНОМИКА
# ==============================

# Добавляем таблицы для магазина и кейсов
def create_shop_and_case_tables():
    cursor = db.conn.cursor()

    # Таблица товаров в магазине
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,
            item_type TEXT,
            rarity TEXT,
            cost_gold INTEGER,
            cost_sapphires INTEGER,
            required_level INTEGER DEFAULT 1,
            quantity_available INTEGER DEFAULT -1, -- -1 = неограничено
            is_available BOOLEAN DEFAULT TRUE
        )
    ''')

    # Таблица кейсов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cost_gold INTEGER,
            cost_sapphires INTEGER,
            rarity_distribution TEXT, -- JSON с распределением редкостей
            is_available BOOLEAN DEFAULT TRUE
        )
    ''')

    # Таблица открытых кейсов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opened_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            case_id INTEGER,
            item_name TEXT,
            rarity TEXT,
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Заполняем начальные данные
    initialize_shop_data(cursor)
    initialize_cases_data(cursor)

    db.conn.commit()

def initialize_shop_data(cursor):
    # Очищаем старые данные
    cursor.execute('DELETE FROM shop_items')

    # Добавляем товары в магазин
    shop_items = [
        # Зелья за золото
        ("🧪 Зелье здоровья", "potion", "common", 50, 0, 1, -1),
        ("🔮 Зелье маны", "potion", "common", 75, 0, 1, -1),
        ("⚡ Зелье энергии", "potion", "common", 100, 0, 5, -1),
        ("💪 Зелье силы", "potion", "uncommon", 200, 0, 10, -1),

        # Предметы за золото
        ("⚔️ Стальной меч", "weapon", "uncommon", 1000, 0, 5, -1),
        ("🛡️ Железный доспех", "armor", "uncommon", 800, 0, 5, -1),
        ("🏹 Охотничий лук", "weapon", "uncommon", 1200, 0, 8, -1),

        # Премиум товары за сапфиры
        ("🔥 Огненный меч", "weapon", "epic", 0, 15, 20, -1),
        ("❄️ Ледяной посох", "weapon", "epic", 0, 20, 25, -1),
        ("⚡ Молниевый клинок", "weapon", "epic", 0, 25, 30, -1),
        ("💎 Алмазная броня", "armor", "epic", 0, 30, 35, -1),
        ("** Kopоля мага", "armor", "legendary", 0, 50, 40, 1),  # Ограниченное количество
    ]

    for item in shop_items:
        cursor.execute('''
            INSERT INTO shop_items (item_name, item_type, rarity, cost_gold, cost_sapphires, required_level, quantity_available)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', item)

def initialize_cases_data(cursor):
    # Очищаем старые данные
    cursor.execute('DELETE FROM cases')

    # Добавляем кейсы
    cases = [
        ("⚪ Обычный кейс", 500, 0, '{"common": 70, "uncommon": 25, "rare": 5}'),
        ("🟢 Необычный кейс", 1500, 1, '{"common": 40, "uncommon": 40, "rare": 15, "epic": 5}'),
        ("🔶 Редкий кейс", 0, 5, '{"uncommon": 30, "rare": 50, "epic": 15, "legendary": 5}'),
        ("🟣 Эпический кейс", 0, 15, '{"rare": 40, "epic": 45, "legendary": 15}'),
    ]

    for case in cases:
        cursor.execute('''
            INSERT INTO cases (name, cost_gold, cost_sapphires, rarity_distribution)
            VALUES (?, ?, ?, ?)
        ''', case)

# Вызываем создание таблиц
create_shop_and_case_tables()

# ==============================
# СИСТЕМА МАГАЗИНА
# ==============================

@router.message(Command('shop'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'магазин')
async def cmd_shop(message: Message):
    shop_text = (
        "🛍️ **Магический магазин**\n\n"
        "Здесь ты можешь купить:\n"
        "• 🧪 Зелья и расходники\n"
        "• ⚔️ Оружие и броню\n"
        "• 🎁 Кейсы с случайными предметами\n"
        "• 💎 Эксклюзивные предметы за сапфиры\n\n"
        "Выбери категорию:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧪 Зелья", callback_data="shop_potions"),
            InlineKeyboardButton(text="⚔️ Оружие", callback_data="shop_weapons")
        ],
        [
            InlineKeyboardButton(text="🛡️ Броня", callback_data="shop_armor"),
            InlineKeyboardButton(text="🎁 Кейсы", callback_data="shop_cases")
        ],
        [
            InlineKeyboardButton(text="💎 Премиум", callback_data="shop_premium"),
            InlineKeyboardButton(text="📦 Мои покупки", callback_data="shop_my_items")
        ]
    ])

    await message.answer(shop_text, reply_markup=keyboard, parse_mode='Markdown')

# Показ зелий в магазине
@router.callback_query(lambda c: c.data == 'shop_potions')
async def shop_show_potions(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT id, item_name, cost_gold, cost_sapphires, required_level, quantity_available
        FROM shop_items
        WHERE item_type = 'potion' AND is_available = TRUE
        ORDER BY cost_gold, cost_sapphires
    ''')

    potions = cursor.fetchall()

    if not potions:
        await callback.answer("❌ В этой категории пока нет товаров!", show_alert=True)
        return

    shop_text = "🧪 **Зелья и расходники**\n\n"

    keyboard_buttons = []
    for potion in potions:
        item_id, name, cost_gold, cost_sapphires, level, quantity = potion

        if cost_gold > 0:
            cost_text = f"{cost_gold}💰"
        else:
            cost_text = f"{cost_sapphires}💎"

        shop_text += f"{name} - {cost_text} | Ур. {level}\n"

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"Купить {name}",
                callback_data=f"shop_buy_{item_id}"
            )
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(shop_text, reply_markup=keyboard)

# Покупка товара
@router.callback_query(lambda c: c.data.startswith('shop_buy_'))
async def shop_buy_item(callback: CallbackQuery):
    item_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT item_name, item_type, rarity, cost_gold, cost_sapphires, required_level, quantity_available
        FROM shop_items
        WHERE id = ? AND is_available = TRUE
    ''', (item_id,))

    item = cursor.fetchone()

    if not item:
        await callback.answer("❌ Товар не найден!", show_alert=True)
        return

    name, item_type, rarity, cost_gold, cost_sapphires, level, quantity = item
    player = db.get_player(user_id)

    # Проверяем уровень
    if player['level'] < level:
        await callback.answer(f"❌ Нужен {level}+ уровень для покупки!", show_alert=True)
        return

    # Проверяем валюту
    if cost_gold > 0 and player['gold'] < cost_gold:
        await callback.answer(f"❌ Недостаточно золота! Нужно {cost_gold}💰", show_alert=True)
        return

    if cost_sapphires > 0 and player['sapphires'] < cost_sapphires:
        await callback.answer(f"❌ Недостаточно сапфиров! Нужно {cost_sapphires}💎", show_alert=True)
        return

    # Проверяем количество
    if quantity == 0:
        await callback.answer("❌ Товар закончился!", show_alert=True)
        return

    # Списываем валюту
    updates = {}
    if cost_gold > 0:
        updates['gold'] = player['gold'] - cost_gold
    if cost_sapphires > 0:
        updates['sapphires'] = player['sapphires'] - cost_sapphires

    db.update_player_stats(user_id, updates)

    # Уменьшаем количество товара если нужно
    if quantity > 0:
        cursor.execute('UPDATE shop_items SET quantity_available = quantity_available - 1 WHERE id = ?', (item_id,))

    # Добавляем предмет в инвентарь
    add_item_to_inventory(user_id, {
        'name': name,
        'type': item_type,
        'rarity': rarity
    })

    db.conn.commit()

    # Показываем подтверждение
    if cost_gold > 0:
        cost_text = f"{cost_gold} золота"
    else:
        cost_text = f"{cost_sapphires} сапфиров"

    await callback.message.edit_text(
        f"🎉 **Покупка успешна!**\n\n"
        f"📦 Ты купил: {name}\n"
        f"💳 Потрачено: {cost_text}\n"
        f"📦 Предмет добавлен в инвентарь!\n\n"
        f"💰 Твой баланс:\n"
        f"Золото: {updates.get('gold', player['gold'])} | Сапфиры: {updates.get('sapphires', player['sapphires'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Продолжить покупки", callback_data="shop_back")],
            [InlineKeyboardButton(text="📦 Инвентарь", callback_data="inventory")]
        ])
    )

# ==============================
# СИСТЕМА КЕЙСОВ
# ==============================

@router.callback_query(lambda c: c.data == 'shop_cases')
async def shop_show_cases(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('SELECT id, name, cost_gold, cost_sapphires FROM cases WHERE is_available = TRUE')
    cases = cursor.fetchall()

    if not cases:
        await callback.answer("❌ В этой категории пока нет кейсов!", show_alert=True)
        return

    cases_text = "🎁 **Кейсы с сюрпризом**\n\n"

    keyboard_buttons = []
    for case in cases:
        case_id, name, cost_gold, cost_sapphires = case

        if cost_gold > 0:
            cost_text = f"{cost_gold}💰"
        else:
            cost_text = f"{cost_sapphires}💎"

        cases_text += f"{name} - {cost_text}\n"

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"Открыть {name}",
                callback_data=f"case_open_{case_id}"
            )
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(cases_text, reply_markup=keyboard)

# Открытие кейса
@router.callback_query(lambda c: c.data.startswith('case_open_'))
async def case_open(callback: CallbackQuery):
    case_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('SELECT name, cost_gold, cost_sapphires, rarity_distribution FROM cases WHERE id = ?', (case_id,))
    case = cursor.fetchone()

    if not case:
        await callback.answer("❌ Кейс не найден!", show_alert=True)
        return

    case_name, cost_gold, cost_sapphires, distribution_json = case
    player = db.get_player(user_id)

    # Проверяем валюту
    if cost_gold > 0 and player['gold'] < cost_gold:
        await callback.answer(f"❌ Недостаточно золота! Нужно {cost_gold}💰", show_alert=True)
        return

    if cost_sapphires > 0 and player['sapphires'] < cost_sapphires:
        await callback.answer(f"❌ Недостаточно сапфиров! Нужно {cost_sapphires}💎", show_alert=True)
        return

    # Списываем валюту
    updates = {}
    if cost_gold > 0:
        updates['gold'] = player['gold'] - cost_gold
    if cost_sapphires > 0:
        updates['sapphires'] = player['sapphires'] - cost_sapphires

    db.update_player_stats(user_id, updates)

    # Генерируем предмет из кейса
    distribution = json.loads(distribution_json)
    item = generate_item_from_case(distribution)

    # Добавляем предмет в инвентарь
    add_item_to_inventory(user_id, item)

    # Записываем открытие кейса
    cursor.execute('''
        INSERT INTO opened_cases (user_id, case_id, item_name, rarity)
        VALUES (?, ?, ?, ?)
    ''', (user_id, case_id, item['name'], item['rarity']))

    db.conn.commit()

    # Анимация открытия кейса
    await callback.message.edit_text("🎁 Открываем кейс...")
    await asyncio.sleep(1)

    await callback.message.edit_text("🎁 Открываем кейс... ✨")
    await asyncio.sleep(1)

    # Показываем результат
    rarity_icon = get_rarity_icon(item['rarity'])

    await callback.message.edit_text(
        f"🎉 **Кейс открыт!**\n\n"
        f"{rarity_icon} **{item['name']}**\n"
        f"📊 Редкость: {item['rarity']}\n"
        f"🎯 Тип: {item['type']}\n\n"
        f"📦 Предмет добавлен в инвентарь!\n\n"
        f"💰 Твой баланс:\n"
        f"Золото: {updates.get('gold', player['gold'])} | Сапфиры: {updates.get('sapphires', player['sapphires'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Открыть еще", callback_data="shop_cases")],
            [InlineKeyboardButton(text="📦 Инвентарь", callback_data="inventory")],
            [InlineKeyboardButton(text="🛍️ В магазин", callback_data="shop_back")]
        ])
    )

# Генерация предмета из кейса
def generate_item_from_case(distribution: Dict) -> Dict:
    # Создаем список редкостей согласно распределению
    rarities = []
    for rarity, chance in distribution.items():
        rarities.extend([rarity] * chance)

    # Выбираем случайную редкость
    selected_rarity = random.choice(rarities)

    # Генерируем предмет в зависимости от редкости
    items_by_rarity = {
        'common': [
            {"name": "⚔️ Ржавый меч", "type": "weapon", "rarity": "common", "damage": 5},
            {"name": "🛡️ Кожаный щит", "type": "armor", "rarity": "common", "defense": 3},
            {"name": "🧪 Слабое зелье", "type": "potion", "rarity": "common", "effect": "heal_30"}
        ],
        'uncommon': [
            {"name": "⚔️ Стальной меч", "type": "weapon", "rarity": "uncommon", "damage": 8},
            {"name": "🛡️ Кольчужный доспех", "type": "armor", "rarity": "uncommon", "defense": 6},
            {"name": "🏹 Охотничий лук", "type": "weapon", "rarity": "uncommon", "damage": 7, "agility": 2}
        ],
        'rare': [
            {"name": "⚔️ Зачарованный меч", "type": "weapon", "rarity": "rare", "damage": 12, "intellect": 3},
            {"name": "🛡️ Мифриловая броня", "type": "armor", "rarity": "rare", "defense": 10, "health": 20},
            {"name": "🔮 Посох мага", "type": "weapon", "rarity": "rare", "damage": 8, "intellect": 5}
        ],
        'epic': [
            {"name": "🔥 Огненный клинок", "type": "weapon", "rarity": "epic", "damage": 18, "intellect": 5},
            {"name": "❄️ Ледяной доспех", "type": "armor", "rarity": "epic", "defense": 15, "health": 30},
            {"name": "⚡ Молниевый посох", "type": "weapon", "rarity": "epic", "damage": 15, "intellect": 8}
        ],
        'legendary': [
            {"name": "🐉 Драконий меч", "type": "weapon", "rarity": "legendary", "damage": 25, "strength": 10},
            {"name": "👑 Доспех короля", "type": "armor", "rarity": "legendary", "defense": 20, "health": 50},
            {"name": "🌟 Посох вечности", "type": "weapon", "rarity": "legendary", "damage": 20, "intellect": 15}
        ]
    }

    return random.choice(items_by_rarity.get(selected_rarity, items_by_rarity['common']))

# ==============================
# ПРЕМИУМ МАГАЗИН
# ==============================

@router.callback_query(lambda c: c.data == 'shop_premium')
async def shop_show_premium(callback: CallbackQuery):
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT id, item_name, cost_sapphires, required_level
        FROM shop_items
        WHERE cost_sapphires > 0 AND is_available = TRUE
        ORDER BY cost_sapphires
    ''')

    premium_items = cursor.fetchall()

    if not premium_items:
        await callback.answer("❌ В этой категории пока нет товаров!", show_alert=True)
        return

    premium_text = "💎 **Премиум товары**\n\n"
    premium_text += "Эксклюзивные предметы только за сапфиры!\n\n"

    keyboard_buttons = []
    for item in premium_items:
        item_id, name, cost_sapphires, level = item
        premium_text += f"{name} - {cost_sapphires}💎 | Ур. {level}\n"

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"Купить {name}",
                callback_data=f"shop_buy_{item_id}"
            )
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(premium_text, reply_markup=keyboard)

# ==============================
# МОИ ПОКУПКИ
# ==============================

@router.callback_query(lambda c: c.data == 'shop_my_items')
async def shop_my_items(callback: CallbackQuery):
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT oc.item_name, oc.rarity, oc.opened_at, c.name
        FROM opened_cases oc
        LEFT JOIN cases c ON oc.case_id = c.id
        WHERE oc.user_id = ?
        ORDER BY oc.opened_at DESC
        LIMIT 10
    ''', (user_id,))

    opened_cases = cursor.fetchall()

    items_text = "📦 **Моя история покупок**\n\n"

    if not opened_cases:
        items_text += "Ты еще не открывал кейсы.\n"
    else:
        items_text += "🎁 **Последние открытые кейсы:**\n"
        for item_name, rarity, opened_at, case_name in opened_cases:
            rarity_icon = get_rarity_icon(rarity)
            date = datetime.fromisoformat(opened_at).strftime("%d.%m %H:%M")
            items_text += f"{rarity_icon} {item_name} ({case_name}) - {date}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ В магазин", callback_data="shop_back")],
        [InlineKeyboardButton(text="🎁 Открыть кейс", callback_data="shop_cases")]
    ])

    await callback.message.edit_text(items_text, reply_markup=keyboard)

# Назад в магазин
@router.callback_query(lambda c: c.data == 'shop_back')
async def shop_back(callback: CallbackQuery):
    await cmd_shop(callback.message)

# ==============================
# ЧАСТЬ 7: БОССЫ, СОБЫТИЯ И АДМИН-ПАНЕЛЬ
# ==============================

# Добавляем таблицы для боссов и событий
def create_boss_and_events_tables():
    cursor = db.conn.cursor()

    # Таблица ежедневных боссов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_bosses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_name TEXT,
            boss_type TEXT,
            health INTEGER,
            damage INTEGER,
            gold_reward INTEGER,
            sapphire_chance INTEGER,
            spawn_day INTEGER, -- 1-7 (понедельник-воскресенье)
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')

    # Таблица боев с боссами
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boss_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            boss_id INTEGER,
            damage_dealt INTEGER,
            reward_received BOOLEAN DEFAULT FALSE,
            battled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES players (user_id),
            FOREIGN KEY (boss_id) REFERENCES daily_bosses (id)
        )
    ''')

    # Таблица текущего состояния босса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boss_current_status (
            boss_id INTEGER PRIMARY KEY,
            current_health INTEGER,
            last_reset DATE DEFAULT CURRENT_DATE,
            total_damage INTEGER DEFAULT 0,
            is_alive BOOLEAN DEFAULT TRUE
        )
    ''')

    # Таблица событий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT,
            event_type TEXT,
            start_time DATETIME,
            end_time DATETIME,
            is_active BOOLEAN DEFAULT FALSE,
            multiplier_gold FLOAT DEFAULT 1.0,
            multiplier_exp FLOAT DEFAULT 1.0,
            description TEXT
        )
    ''')

    # Заполняем боссов
    initialize_bosses_data(cursor)

    db.conn.commit()

def initialize_bosses_data(cursor):
    # Очищаем старые данные
    cursor.execute('DELETE FROM daily_bosses')

    # Добавляем ежедневных боссов
    bosses = [
        ("🧙‍♂️ Архимаг Вейлон", "mage", 5000, 50, 1000, 10, 1),  # Понедельник
        ("⚔️ Варлорд Краг", "warrior", 6000, 60, 1200, 15, 2),  # Вторник
        ("🏹 Теневой лучник", "archer", 4500, 65, 900, 12, 3),   # Среда
        ("🙏 Верховный жрец", "priest", 4000, 45, 800, 8, 4),   # Четверг
        ("🔮 Некромант Заракс", "dark_mage", 5500, 70, 1100, 20, 5),  # Пятница
        ("🐲 Древний дракон", "dragon", 8000, 80, 2000, 25, 6), # Суббота
        ("🌟 Случайный босс", "random", 3000, 40, 700, 5, 7)    # Воскресенье
    ]

    for boss in bosses:
        cursor.execute('''
            INSERT INTO daily_bosses (boss_name, boss_type, health, damage, gold_reward, sapphire_chance, spawn_day)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', boss)

# Вызываем создание таблиц
create_boss_and_events_tables()

# ==============================
# СИСТЕМА ЕЖЕДНЕВНЫХ БОССОВ
# ==============================

@router.message(Command('boss'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'босс')
async def cmd_boss(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Ты еще не создал персонажа! Напиши /start чтобы начать игру.")
        return

    # Получаем текущего босса
    current_boss = get_current_daily_boss()

    if not current_boss:
        await message.answer("❌ На этой неделе все боссы побеждены! Заходи завтра.")
        return

    boss_id, boss_name, boss_type, health, damage, gold_reward, sapphire_chance, spawn_day = current_boss

    # Получаем текущее состояние босса
    cursor = db.conn.cursor()
    cursor.execute('SELECT current_health, is_alive FROM boss_current_status WHERE boss_id = ?', (boss_id,))
    boss_status = cursor.fetchone()

    if not boss_status:
        # Инициализируем босса
        cursor.execute('INSERT INTO boss_current_status (boss_id, current_health) VALUES (?, ?)', (boss_id, health))
        db.conn.commit()
        current_health, is_alive = health, True
    else:
        current_health, is_alive = boss_status

    if not is_alive:
        await message.answer(
            f"🎉 **{boss_name} уже побежден!**\n\n"
            f"Приходи завтра для нового босса!\n"
            f"Следующий босс: {get_tomorrow_boss_name()}"
        )
        return

    boss_text = (
        f"🐉 **Ежедневный босс: {boss_name}**\n\n"
        f"❤️ Здоровье: {current_health}/{health}\n"
        f"⚔️ Урон: {damage}\n"
        f"💰 Награда: {gold_reward} золота\n"
        f"💎 Шанс сапфира: {sapphire_chance}%\n\n"
        f"🏆 Общий нанесенный урон: {get_boss_total_damage(boss_id)}\n\n"
    )

    # Проверяем участвовал ли игрок сегодня
    cursor.execute('''
        SELECT COUNT(*) FROM boss_battles
        WHERE user_id = ? AND boss_id = ? AND DATE(battled_at) = DATE('now')
    ''', (user_id, boss_id))

    already_battled = cursor.fetchone()[0] > 0

    if already_battled:
        boss_text += "⚠️ Ты уже сражался с этим боссом сегодня.\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика боя", callback_data=f"boss_stats_{boss_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
        ])
    else:
        boss_text += "⚔️ Ты можешь атаковать босса один раз в день!"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Атаковать босса", callback_data=f"boss_attack_{boss_id}")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data=f"boss_stats_{boss_id}")]
        ])

    await message.answer(boss_text, reply_markup=keyboard, parse_mode='Markdown')

# Атака на босса
@router.callback_query(lambda c: c.data.startswith('boss_attack_'))
async def boss_attack(callback: CallbackQuery):
    boss_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    player = db.get_player(user_id)
    boss_data = get_boss_data(boss_id)

    if not boss_data or not player:
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return

    # Проверяем участвовал ли игрок сегодня
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM boss_battles
        WHERE user_id = ? AND boss_id = ? AND DATE(battled_at) = DATE('now')
    ''', (user_id, boss_id))

    if cursor.fetchone()[0] > 0:
        await callback.answer("❌ Ты уже сражался с этим боссом сегодня!", show_alert=True)
        return

    boss_id, boss_name, boss_type, health, damage, gold_reward, sapphire_chance, spawn_day = boss_data

    # Получаем текущее здоровье босса
    cursor.execute('SELECT current_health FROM boss_current_status WHERE boss_id = ?', (boss_id,))
    result = cursor.fetchone()

    if not result:
        await callback.answer("❌ Босс не найден!", show_alert=True)
        return

    current_health = result[0]

    # Игрок атакует босса
    player_damage = calculate_boss_damage(player, boss_type)
    new_health = current_health - player_damage

    # Босс атакует игрока (игрок теряет 10% здоровья)
    player_health_loss = max(1, player['health'] // 10)
    new_player_health = player['health'] - player_health_loss

    # Обновляем здоровье игрока
    db.update_player_stats(user_id, {'health': new_player_health})

    # Обновляем здоровье босса и общий урон
    cursor.execute('''
        UPDATE boss_current_status
        SET current_health = ?, total_damage = total_damage + ?
        WHERE boss_id = ?
    ''', (new_health, player_damage, boss_id))

    # Записываем бой
    cursor.execute('''
        INSERT INTO boss_battles (user_id, boss_id, damage_dealt)
        VALUES (?, ?, ?)
    ''', (user_id, boss_id, player_damage))

    # Проверяем победу над боссом
    if new_health <= 0:
        cursor.execute('UPDATE boss_current_status SET is_alive = FALSE WHERE boss_id = ?', (boss_id,))
        boss_defeated = True
    else:
        boss_defeated = False

    db.conn.commit()

    # Награждаем игрока
    reward_text = await give_boss_rewards(user_id, boss_data, player_damage, boss_defeated)

    # Формируем сообщение о результате
    result_text = (
        f"⚔️ **Результат боя с {boss_name}**\n\n"
        f"🎯 Ты нанес {player_damage} урона!\n"
        f"❤️ Потерял {player_health_loss} здоровья\n"
        f"🐉 Здоровье босса: {new_health}/{health}\n\n"
        f"{reward_text}"
    )

    if boss_defeated:
        result_text += f"\n🎉 **{boss_name} ПОБЕЖДЕН!** Все участники получат бонусные награды!"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика босса", callback_data=f"boss_stats_{boss_id}")],
        [InlineKeyboardButton(text="🐉 К боссам", callback_data="boss_back")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode='Markdown')

# Награды за босса
async def give_boss_rewards(user_id: int, boss_data: tuple, damage: int, boss_defeated: bool) -> str:
    boss_id, boss_name, boss_type, health, gold_reward, sapphire_chance, spawn_day = boss_data
    player = db.get_player(user_id)

    # Базовые награды
    base_gold = max(100, (damage * gold_reward) // health)
    exp_reward = damage * 2

    # Бонус за убийство босса
    if boss_defeated:
        base_gold *= 2
        exp_reward *= 3

    # Шанс сапфира
    sapphire_reward = 0
    if random.randint(1, 100) <= sapphire_chance:
        sapphire_reward = 1
        if boss_defeated:
            sapphire_reward += 1

    # Обновляем статистику игрока
    updates = {
        'gold': player['gold'] + base_gold,
        'experience': player['experience'] + exp_reward
    }

    if sapphire_reward > 0:
        updates['sapphires'] = player['sapphires'] + sapphire_reward

    db.update_player_stats(user_id, updates)

    # Формируем текст наград
    reward_text = f"🏆 Награды:\n💰 +{base_gold} золота\n⭐ +{exp_reward} опыта"

    if sapphire_reward > 0:
        reward_text += f"\n💎 +{sapphire_reward} сапфир(ов)"

    return reward_text

# Статистика босса
@router.callback_query(lambda c: c.data.startswith('boss_stats_'))
async def boss_stats(callback: CallbackQuery):
    boss_id = int(callback.data.split('_')[2])

    boss_data = get_boss_data(boss_id)
    if not boss_data:
        await callback.answer("❌ Босс не найден!", show_alert=True)
        return

    cursor = db.conn.cursor()

    # Топ 5 игроков по урону к этому боссу
    cursor.execute('''
        SELECT p.character_name, bb.damage_dealt
        FROM boss_battles bb
        JOIN players p ON bb.user_id = p.user_id
        WHERE bb.boss_id = ? AND DATE(bb.battled_at) = DATE('now')
        ORDER BY bb.damage_dealt DESC
        LIMIT 5
    ''', (boss_id,))

    top_damagers = cursor.fetchall()

    # Общая статистика
    cursor.execute('SELECT total_damage, current_health FROM boss_current_status WHERE boss_id = ?', (boss_id,))
    total_damage, current_health = cursor.fetchone()

    stats_text = f"📊 **Статистика {boss_data[1]}**\n\n"
    stats_text += f"🎯 Общий урон: {total_damage}\n"
    stats_text += f"❤️ Осталось здоровья: {current_health}\n\n"
    stats_text += "🏆 Топ бойцов:\n"

    for i, (name, damage) in enumerate(top_damagers, 1):
        stats_text += f"{i}. {name} - {damage} урона\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐉 К боссам", callback_data="boss_back")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await callback.message.edit_text(stats_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# СИСТЕМА СОБЫТИЙ
# ==============================

@router.message(Command('events'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'события')
async def cmd_events(message: Message):
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT event_name, event_type, start_time, end_time, multiplier_gold, multiplier_exp, description
        FROM game_events
        WHERE is_active = TRUE AND end_time > CURRENT_TIMESTAMP
    ''')

    active_events = cursor.fetchall()

    events_text = "🎪 **Активные события**\n\n"

    if not active_events:
        events_text += "Сейчас нет активных событий.\nЗаходи позже!"
    else:
        for event in active_events:
            name, etype, start, end, mult_gold, mult_exp, desc = event
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)

            events_text += f"🎯 **{name}**\n"
            events_text += f"📅 До: {end_dt.strftime('%d.%m %H:%M')}\n"
            events_text += f"💰 Множитель золота: x{mult_gold}\n"
            events_text += f"⭐ Множитель опыта: x{mult_exp}\n"
            events_text += f"📝 {desc}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐉 Ежедневные боссы", callback_data="boss_back")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await message.answer(events_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# АДМИН-ПАНЕЛЬ
# ==============================

# Список админов (в реальном боте лучше хранить в базе)
ADMIN_IDS = [123456789]  # Замени на реальные ID админов

@router.message(Command('admin'))
async def cmd_admin(message: Message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет доступа к админ-панели!")
        return

    admin_text = (
        "👑 **Админ-панель**\n\n"
        "Выбери действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give_currency")],
        [InlineKeyboardButton(text="🎁 Выдать предмет", callback_data="admin_give_item")],
        [InlineKeyboardButton(text="🐉 Управление боссами", callback_data="admin_manage_bosses")],
        [InlineKeyboardButton(text="🎪 Управление событиями", callback_data="admin_manage_events")],
        [InlineKeyboardButton(text="📊 Статистика сервера", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔄 Сброс боссов", callback_data="admin_reset_bosses")]
    ])

    await message.answer(admin_text, reply_markup=keyboard, parse_mode='Markdown')

# Выдача валюты
@router.callback_query(lambda c: c.data == 'admin_give_currency')
async def admin_give_currency(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 **Выдача валюты**\n\n"
        "Введи данные в формате:\n"
        "`ID_игрока золото сапфиры`\n\n"
        "Пример: `123456789 1000 5`"
    )

    await state.set_state("admin_give_currency")

@router.message(lambda message: message.text and message.from_user.id in ADMIN_IDS)
async def process_admin_currency(message: Message, state: FSMContext):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Неверный формат! Используй: ID_игрока золото сапфиры")
            return

        target_id = int(parts[0])
        gold = int(parts[1])
        sapphires = int(parts[2])

        player = db.get_player(target_id)
        if not player:
            await message.answer("❌ Игрок не найден!")
            return

        db.update_player_stats(target_id, {
            'gold': player['gold'] + gold,
            'sapphires': player['sapphires'] + sapphires
        })

        await message.answer(
            f"✅ Валюта выдана игроку {player['character_name']}!\n"
            f"💰 Золото: +{gold}\n"
            f"💎 Сапфиры: +{sapphires}"
        )

    except ValueError:
        await message.answer("❌ Ошибка в данных! Убедись что используешь числа.")
    finally:
        await state.clear()

# Статистика сервера
@router.callback_query(lambda c: c.data == 'admin_stats')
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    cursor = db.conn.cursor()

    # Общая статистика
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM players WHERE DATE(created_at) = DATE("now")')
    new_today = cursor.fetchone()[0]

    cursor.execute('SELECT SUM(gold) FROM players')
    total_gold = cursor.fetchone()[0] or 0

    cursor.execute('SELECT SUM(sapphires) FROM players')
    total_sapphires = cursor.fetchone()[0] or 0

    stats_text = (
        f"📊 **Статистика сервера**\n\n"
        f"👥 Всего игроков: {total_players}\n"
        f"🆕 Новых сегодня: {new_today}\n"
        f"💰 Всего золота: {total_gold}\n"
        f"💎 Всего сапфиров: {total_sapphires}\n"
        f"🐉 Активных боссов: {get_active_bosses_count()}\n"
        f"🏰 Создано кланов: {get_clans_count()}"
    )

    await callback.message.edit_text(stats_text, parse_mode='Markdown')

# ==============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================

def get_current_daily_boss():
    """Получает текущего босса по дню недели"""
    current_day = datetime.now().isoweekday()  # 1-7 (понедельник-воскресенье)

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT * FROM daily_bosses
        WHERE spawn_day = ? AND is_active = TRUE
    ''', (current_day,))

    return cursor.fetchone()

def get_boss_data(boss_id: int):
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM daily_bosses WHERE id = ?', (boss_id,))
    return cursor.fetchone()

def calculate_boss_damage(player: Dict, boss_type: str) -> int:
    """Рассчитывает урон игрока по боссу"""
    base_damage = player['damage']

    # Бонусы в зависимости от типа босса
    type_bonus = {
        'mage': player['intellect'] * 0.5,
        'warrior': player['damage'] * 0.3,
        'archer': player['agility'] * 0.4,
        'priest': (player['intellect'] + player['damage']) * 0.2,
        'dark_mage': player['intellect'] * 0.6,
        'dragon': (player['damage'] + player['agility']) * 0.25,
        'random': random.randint(10, 30)
    }

    bonus = type_bonus.get(boss_type, 0)
    return int(base_damage + bonus + random.randint(5, 15))

def get_boss_total_damage(boss_id: int) -> int:
    cursor = db.conn.cursor()
    cursor.execute('SELECT total_damage FROM boss_current_status WHERE boss_id = ?', (boss_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def get_tomorrow_boss_name() -> str:
    tomorrow_day = (datetime.now().isoweekday() % 7) + 1
    cursor = db.conn.cursor()
    cursor.execute('SELECT boss_name FROM daily_bosses WHERE spawn_day = ?', (tomorrow_day,))
    result = cursor.fetchone()
    return result[0] if result else "Неизвестный босс"

def get_active_bosses_count() -> int:
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM boss_current_status WHERE is_alive = TRUE')
    return cursor.fetchone()[0]

def get_clans_count() -> int:
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM clans')
    return cursor.fetchone()[0]

# Назад к боссам
@router.callback_query(lambda c: c.data == 'boss_back')
async def boss_back(callback: CallbackQuery):
    await cmd_boss(callback.message)

    # ==============================
# ЧАСТЬ 8: РЕЖИМЫ И УЛУЧШЕНИЯ
# ==============================

# Добавляем таблицы для новых режимов
def create_game_modes_tables():
    cursor = db.conn.cursor()

    # Таблица королевских битв
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS royal_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_code TEXT UNIQUE,
            max_players INTEGER DEFAULT 10,
            current_players INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT FALSE,
            is_started BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица участников королевской битвы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS royal_battle_players (
            battle_id INTEGER,
            user_id INTEGER,
            health INTEGER,
            position_x INTEGER DEFAULT 0,
            position_y INTEGER DEFAULT 0,
            kills INTEGER DEFAULT 0,
            is_alive BOOLEAN DEFAULT TRUE,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (battle_id, user_id),
            FOREIGN KEY (battle_id) REFERENCES royal_battles (id),
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица тёмной охоты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dark_hunt_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            difficulty TEXT,
            hunter_count INTEGER,
            time_remaining INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица улучшений персонажа
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS character_upgrades (
            user_id INTEGER PRIMARY KEY,
            strength INTEGER DEFAULT 0,
            intellect INTEGER DEFAULT 0,
            agility INTEGER DEFAULT 0,
            stamina INTEGER DEFAULT 0,
            available_points INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    db.conn.commit()

# Вызываем создание таблиц
create_game_modes_tables()

# ==============================
# КОРОЛЕВСКАЯ БИТВА
# ==============================

@router.message(Command('royal'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'королевская битва')
async def cmd_royal_battle(message: Message):
    royal_text = (
        "👑 **Королевская битва**\n\n"
        "⚔️ 10 игроков сражаются до последнего выжившего!\n"
        "🎯 Особенности режима:\n"
        "• 🔥 Случайные события на карте\n"
        "• 💎 Усиления и предметы\n"
        "• 🏃‍♂️ Уменьшающаяся зона\n"
        "• 🏆 Уникальные награды\n\n"
        "Выбери действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Быстрый поиск", callback_data="royal_quick_join")],
        [InlineKeyboardButton(text="👥 Создать комнату", callback_data="royal_create")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="royal_stats")],
        [InlineKeyboardButton(text="🏆 Лучшие игроки", callback_data="royal_top")]
    ])

    await message.answer(royal_text, reply_markup=keyboard, parse_mode='Markdown')

# Быстрый поиск королевской битвы
@router.callback_query(lambda c: c.data == 'royal_quick_join')
async def royal_quick_join(callback: CallbackQuery):
    user_id = callback.from_user.id
    player = db.get_player(user_id)

    if not player:
        await callback.answer("❌ Сначала создай персонажа!", show_alert=True)
        return

    # Ищем активную битву с свободными местами
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT id, battle_code, current_players, max_players
        FROM royal_battles
        WHERE is_active = TRUE AND is_started = FALSE AND current_players < max_players
        LIMIT 1
    ''')

    battle = cursor.fetchone()

    if battle:
        # Присоединяемся к существующей битве
        battle_id, battle_code, current_players, max_players = battle
        await join_royal_battle(callback, battle_id, user_id, player)
    else:
        # Создаем новую битву
        battle_code = generate_battle_code()
        cursor.execute('''
            INSERT INTO royal_battles (battle_code, max_players, is_active)
            VALUES (?, 10, TRUE)
        ''', (battle_code,))
        battle_id = cursor.lastrowid
        db.conn.commit()

        await join_royal_battle(callback, battle_id, user_id, player)

async def join_royal_battle(callback: CallbackQuery, battle_id: int, user_id: int, player: Dict):
    cursor = db.conn.cursor()

    # Проверяем не присоединился ли уже
    cursor.execute('SELECT 1 FROM royal_battle_players WHERE battle_id = ? AND user_id = ?', (battle_id, user_id))
    if cursor.fetchone():
        await callback.answer("❌ Ты уже в этой битве!", show_alert=True)
        return

    # Добавляем игрока в битву
    cursor.execute('''
        INSERT INTO royal_battle_players (battle_id, user_id, health)
        VALUES (?, ?, ?)
    ''', (battle_id, user_id, player['health']))

    # Обновляем счетчик игроков
    cursor.execute('UPDATE royal_battles SET current_players = current_players + 1 WHERE id = ?', (battle_id,))

    # Получаем обновленную информацию о битве
    cursor.execute('SELECT battle_code, current_players, max_players FROM royal_battles WHERE id = ?', (battle_id,))
    battle_code, current_players, max_players = cursor.fetchone()

    db.conn.commit()

    battle_text = (
        f"🎮 **Королевская битва #{battle_code}**\n\n"
        f"👥 Игроков: {current_players}/{max_players}\n"
        f"⏳ Ожидание игроков...\n\n"
        f"Присоединились:\n"
    )

    # Получаем список игроков
    cursor.execute('''
        SELECT p.character_name
        FROM royal_battle_players rbp
        JOIN players p ON rbp.user_id = p.user_id
        WHERE rbp.battle_id = ?
    ''', (battle_id,))

    players = cursor.fetchall()
    for i, (name,) in enumerate(players, 1):
        battle_text += f"{i}. {name}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"royal_refresh_{battle_id}")],
        [InlineKeyboardButton(text="🚪 Покинуть", callback_data=f"royal_leave_{battle_id}")]
    ])

    # Проверяем можно ли начинать
    if current_players >= 3:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🎬 Начать битву", callback_data=f"royal_start_{battle_id}")])

    await callback.message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')

    # Автоматически начинаем при заполнении
    if current_players >= max_players:
        await asyncio.sleep(2)
        await start_royal_battle(battle_id)

# Начало королевской битвы
async def start_royal_battle(battle_id: int):
    cursor = db.conn.cursor()
    cursor.execute('UPDATE royal_battles SET is_started = TRUE WHERE id = ?', (battle_id,))
    db.conn.commit()

    # Получаем всех игроков
    cursor.execute('''
        SELECT rbp.user_id, p.character_name
        FROM royal_battle_players rbp
        JOIN players p ON rbp.user_id = p.user_id
        WHERE rbp.battle_id = ?
    ''', (battle_id,))

    players = cursor.fetchall()

    # Отправляем сообщение о начале всем игрокам
    for user_id, character_name in players:
        try:
            await bot.send_message(
                user_id,
                "🎬 **Королевская битва началась!**\n\n"
                "🏃‍♂️ Беги к центру карты!\n"
                "🔥 Зона начинает уменьшаться через 2 минуты!\n"
                "⚔️ Сражайся с другими игроками!\n\n"
                "Последний выживший получит легендарные награды!",
                parse_mode='Markdown'
            )

            # Отправляем карту боя
            await send_royal_battle_map(user_id, battle_id)

        except Exception as e:
            print(f"Не удалось отправить сообщение игроку {user_id}: {e}")

# Карта королевской битвы
async def send_royal_battle_map(user_id: int, battle_id: int):
    cursor = db.conn.cursor()

    # Получаем позицию игрока
    cursor.execute('SELECT position_x, position_y, health FROM royal_battle_players WHERE battle_id = ? AND user_id = ?', (battle_id, user_id))
    player_pos = cursor.fetchone()

    if not player_pos:
        return

    player_x, player_y, health = player_pos

    # Создаем простую текстовую карту
    map_size = 10
    map_text = "🗺️ **Карта битвы**\n\n"

    for y in range(map_size):
        for x in range(map_size):
            if x == player_x and y == player_y:
                map_text += "👤"  # Игрок
            elif abs(x - player_x) <= 1 and abs(y - player_y) <= 1:
                map_text += "🌳"  # Ближайшие клетки
            else:
                map_text += "⬜"  # Пустая клетка
        map_text += "\n"

    map_text += f"\n❤️ Здоровье: {health}\n🎯 Позиция: ({player_x}, {player_y})"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬆️", callback_data=f"royal_move_{battle_id}_up"),
            InlineKeyboardButton(text="⬇️", callback_data=f"royal_move_{battle_id}_down")
        ],
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"royal_move_{battle_id}_left"),
            InlineKeyboardButton(text="➡️", callback_data=f"royal_move_{battle_id}_right")
        ],
        [InlineKeyboardButton(text="⚔️ Атаковать рядом", callback_data=f"royal_attack_{battle_id}")],
        [InlineKeyboardButton(text="🔄 Обновить карту", callback_data=f"royal_refresh_{battle_id}")]
    ])

    try:
        await bot.send_message(user_id, map_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка отправки карты: {e}")

# ==============================
# ТЁМНАЯ ОХОТА
# ==============================

@router.message(Command('hunt_dark'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'тёмная охота')
async def cmd_dark_hunt(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Сначала создай персонажа!", show_alert=True)
        return

    hunt_text = (
        "🌑 **Тёмная охота**\n\n"
        "Ты - добыча! Выживай против ботов-охотников!\n\n"
        "🎯 Цель: Продержаться 5 минут или убить всех охотников\n"
        "🏃‍♂️ Особенности:\n"
        "• 🤖 3-5 умных ботов-охотников\n"
        "• 🎯 Тактическое поведение AI\n"
        "• 💎 Уникальные награды за выживание\n"
        "• ⚡ Прогрессирующая сложность\n\n"
        "Выбери сложность:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Легко (3 охотника)", callback_data="dark_hunt_easy"),
            InlineKeyboardButton(text="🟡 Средне (4 охотника)", callback_data="dark_hunt_medium")
        ],
        [
            InlineKeyboardButton(text="🔴 Сложно (5 охотников)", callback_data="dark_hunt_hard"),
            InlineKeyboardButton(text="💀 Эксперт (5 элитных)", callback_data="dark_hunt_expert")
        ],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="dark_hunt_stats")]
    ])

    await message.answer(hunt_text, reply_markup=keyboard, parse_mode='Markdown')

# Начало тёмной охоты
@router.callback_query(lambda c: c.data.startswith('dark_hunt_'))
async def start_dark_hunt(callback: CallbackQuery):
    difficulty = callback.data.replace('dark_hunt_', '')
    user_id = callback.from_user.id

    # Настройки сложности
    difficulty_settings = {
        'easy': {'hunters': 3, 'time': 300, 'hunter_level': -2},
        'medium': {'hunters': 4, 'time': 300, 'hunter_level': 0},
        'hard': {'hunters': 5, 'time': 300, 'hunter_level': 2},
        'expert': {'hunters': 5, 'time': 240, 'hunter_level': 5}
    }

    settings = difficulty_settings.get(difficulty, difficulty_settings['medium'])

    # Создаем сессию охоты
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO dark_hunt_sessions (user_id, difficulty, hunter_count, time_remaining)
        VALUES (?, ?, ?, ?)
    ''', (user_id, difficulty, settings['hunters'], settings['time']))

    session_id = cursor.lastrowid
    db.conn.commit()

    hunt_text = (
        f"🌑 **Тёмная охота началась!**\n\n"
        f"🎯 Сложность: {difficulty.upper()}\n"
        f"🤖 Охотников: {settings['hunters']}\n"
        f"⏱️ Время: {settings['time']//60} минут\n\n"
        f"🏃‍♂️ **Цели:**\n"
        f"• Выжить {settings['time']//60} минут\n"
        f"• ИЛИ убить всех охотников\n\n"
        f"Удачи, добыча! 🎯"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Начать выживание", callback_data=f"dark_hunt_start_{session_id}")],
        [InlineKeyboardButton(text="🚪 Сбежать", callback_data="dark_hunt_cancel")]
    ])

    await callback.message.edit_text(hunt_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# СИСТЕМА УЛУЧШЕНИЙ ПЕРСОНАЖА
# ==============================

@router.message(Command('upgrade'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'улучшить')
async def cmd_upgrade(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Сначала создай персонажа!", show_alert=True)
        return

    # Получаем или создаем запись улучшений
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM character_upgrades WHERE user_id = ?', (user_id,))
    upgrades = cursor.fetchone()

    if not upgrades:
        # Даем начальные очки за уровень
        available_points = max(0, player['level'] - 1) * 2
        cursor.execute('''
            INSERT INTO character_upgrades (user_id, available_points)
            VALUES (?, ?)
        ''', (user_id, available_points))
        db.conn.commit()
        upgrades = (user_id, 0, 0, 0, 0, available_points)

    user_id, strength, intellect, agility, stamina, available_points = upgrades

    upgrade_text = (
        f"🔧 **Улучшение характеристик**\n\n"
        f"🎯 Доступно очков: {available_points}\n\n"
        f"📊 Текущие улучшения:\n"
        f"💪 Сила: +{strength} (увеличивает физический урон)\n"
        f"🧠 Интеллект: +{intellect} (увеличивает магический урон и ману)\n"
        f"🎯 Ловкость: +{agility} (увеличивает шанс крита и уклонения)\n"
        f"❤️ Выносливость: +{stamina} (увеличивает здоровье)\n\n"
        f"Выбери характеристику для улучшения:"
    )

    keyboard_buttons = []

    if available_points > 0:
        keyboard_buttons = [
            [InlineKeyboardButton(text="💪 +1 Сила", callback_data="upgrade_strength")],
            [InlineKeyboardButton(text="🧠 +1 Интеллект", callback_data="upgrade_intellect")],
            [InlineKeyboardButton(text="🎯 +1 Ловкость", callback_data="upgrade_agility")],
            [InlineKeyboardButton(text="❤️ +1 Выносливость", callback_data="upgrade_stamina")],
        ]

    keyboard_buttons.append([InlineKeyboardButton(text="📊 Обновить статистику", callback_data="upgrade_refresh")])
    keyboard_buttons.append([InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(upgrade_text, reply_markup=keyboard, parse_mode='Markdown')

# Улучшение характеристики
@router.callback_query(lambda c: c.data.startswith('upgrade_'))
async def process_upgrade(callback: CallbackQuery):
    upgrade_type = callback.data.replace('upgrade_', '')
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM character_upgrades WHERE user_id = ?', (user_id,))
    upgrades = cursor.fetchone()

    if not upgrades or upgrades[5] <= 0:  # available_points
        await callback.answer("❌ Нет доступных очков улучшения!", show_alert=True)
        return

    user_id, strength, intellect, agility, stamina, available_points = upgrades

    # Обновляем характеристику
    if upgrade_type == 'strength':
        cursor.execute('UPDATE character_upgrades SET strength = strength + 1, available_points = available_points - 1 WHERE user_id = ?', (user_id,))
        # Обновляем урон игрока
        player = db.get_player(user_id)
        db.update_player_stats(user_id, {'damage': player['damage'] + 2})

    elif upgrade_type == 'intellect':
        cursor.execute('UPDATE character_upgrades SET intellect = intellect + 1, available_points = available_points - 1 WHERE user_id = ?', (user_id,))
        # Обновляем ману игрока
        player = db.get_player(user_id)
        db.update_player_stats(user_id, {
            'max_mana': player['max_mana'] + 10,
            'mana': min(player['mana'] + 10, player['max_mana'] + 10)
        })

    elif upgrade_type == 'agility':
        cursor.execute('UPDATE character_upgrades SET agility = agility + 1, available_points = available_points - 1 WHERE user_id = ?', (user_id,))

    elif upgrade_type == 'stamina':
        cursor.execute('UPDATE character_upgrades SET stamina = stamina + 1, available_points = available_points - 1 WHERE user_id = ?', (user_id,))
        # Обновляем здоровье игрока
        player = db.get_player(user_id)
        db.update_player_stats(user_id, {
            'max_health': player['max_health'] + 15,
            'health': min(player['health'] + 15, player['max_health'] + 15)
        })

    db.conn.commit()

    await callback.answer(f"✅ {upgrade_type.capitalize()} улучшена!", show_alert=True)
    await cmd_upgrade(callback.message)

# ==============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================

def generate_battle_code() -> str:
    """Генерирует уникальный код для битвы"""
    import string
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(6))

# Обновление королевской битвы
@router.callback_query(lambda c: c.data.startswith('royal_refresh_'))
async def royal_refresh(callback: CallbackQuery):
    battle_id = int(callback.data.split('_')[2])

    cursor = db.conn.cursor()
    cursor.execute('SELECT battle_code, current_players, max_players, is_started FROM royal_battles WHERE id = ?', (battle_id,))
    battle_data = cursor.fetchone()

    if not battle_data:
        await callback.answer("❌ Битва не найдена!", show_alert=True)
        return

    battle_code, current_players, max_players, is_started = battle_data

    if is_started:
        await callback.answer("🎬 Битва уже началась!", show_alert=True)
        return

    battle_text = f"🎮 **Королевская битва #{battle_code}**\n\n👥 Игроков: {current_players}/{max_players}\n\n"

    cursor.execute('''
        SELECT p.character_name
        FROM royal_battle_players rbp
        JOIN players p ON rbp.user_id = p.user_id
        WHERE rbp.battle_id = ?
    ''', (battle_id,))

    players = cursor.fetchall()
    for i, (name,) in enumerate(players, 1):
        battle_text += f"{i}. {name}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"royal_refresh_{battle_id}")],
        [InlineKeyboardButton(text="🚪 Покинуть", callback_data=f"royal_leave_{battle_id}")]
    ])

    if current_players >= 3:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🎬 Начать битву", callback_data=f"royal_start_{battle_id}")])

    await callback.message.edit_text(battle_text, reply_markup=keyboard, parse_mode='Markdown')

# Выход из королевской битвы
@router.callback_query(lambda c: c.data.startswith('royal_leave_'))
async def royal_leave(callback: CallbackQuery):
    battle_id = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('DELETE FROM royal_battle_players WHERE battle_id = ? AND user_id = ?', (battle_id, user_id))
    cursor.execute('UPDATE royal_battles SET current_players = current_players - 1 WHERE id = ?', (battle_id,))
    db.conn.commit()

    await callback.message.edit_text(
        "🚪 Ты покинул королевскую битву.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Новая битва", callback_data="royal_quick_join")],
            [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
        ])
    )

# Обновление улучшений
@router.callback_query(lambda c: c.data == 'upgrade_refresh')
async def upgrade_refresh(callback: CallbackQuery):
    await cmd_upgrade(callback.message)

# Отмена тёмной охоты
@router.callback_query(lambda c: c.data == 'dark_hunt_cancel')
async def dark_hunt_cancel(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌑 Ты сбежал из тёмной охоты...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="dark_hunt_back")],
            [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
        ])
    )

# Назад к тёмной охоте
@router.callback_query(lambda c: c.data == 'dark_hunt_back')
async def dark_hunt_back(callback: CallbackQuery):
    await cmd_dark_hunt(callback.message)

    # ==============================
# ЧАСТЬ 9: ЗАВЕРШАЮЩИЕ СИСТЕМЫ И ОПТИМИЗАЦИЯ
# ==============================

# Добавляем завершающие таблицы
def create_final_tables():
    cursor = db.conn.cursor()

    # Таблица достижений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_id TEXT,
            achievement_name TEXT,
            achievement_description TEXT,
            achieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reward_claimed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица ежедневных наград
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_rewards (
            user_id INTEGER PRIMARY KEY,
            last_reward_date DATE,
            streak_count INTEGER DEFAULT 0,
            total_rewards INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица энергетической системы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS energy_system (
            user_id INTEGER PRIMARY KEY,
            last_energy_check DATETIME DEFAULT CURRENT_TIMESTAMP,
            energy_accumulated INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES players (user_id)
        )
    ''')

    # Таблица глобальных настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Инициализируем настройки
    initialize_global_settings(cursor)

    db.conn.commit()

def initialize_global_settings(cursor):
    settings = [
        ('game_version', '1.0.0', 'Версия игры'),
        ('maintenance_mode', 'false', 'Режим техобслуживания'),
        ('gold_drop_multiplier', '1.0', 'Множитель выпадения золота'),
        ('exp_multiplier', '1.0', 'Множитель опыта'),
        ('energy_regen_rate', '1', 'Скорость восстановления энергии в минуту')
    ]

    for key, value, description in settings:
        cursor.execute('''
            INSERT OR REPLACE INTO global_settings (key, value, description)
            VALUES (?, ?, ?)
        ''', (key, value, description))

# Вызываем создание таблиц
create_final_tables()

# ==============================
# СИСТЕМА ЭНЕРГИИ И ВОССТАНОВЛЕНИЯ
# ==============================

async def update_energy_system():
    """Обновляет энергию всех игроков (вызывается периодически)"""
    cursor = db.conn.cursor()
    cursor.execute('SELECT user_id, last_energy_check, energy_accumulated FROM energy_system')
    energy_data = cursor.fetchall()

    for user_id, last_check_str, accumulated in energy_data:
        if not last_check_str:
            continue

        last_check = datetime.fromisoformat(last_check_str)
        now = datetime.now()
        minutes_passed = int((now - last_check).total_seconds() / 60)

        if minutes_passed > 0:
            # Восстанавливаем энергию
            energy_gained = min(minutes_passed, GameConfig.ENERGY_MAX - accumulated)
            new_accumulated = accumulated + energy_gained

            # Обновляем энергию в системе
            cursor.execute('''
                UPDATE energy_system
                SET energy_accumulated = ?, last_energy_check = ?
                WHERE user_id = ?
            ''', (new_accumulated, now.isoformat(), user_id))

            # Обновляем энергию игрока если нужно
            if energy_gained > 0:
                player = db.get_player(user_id)
                if player:
                    new_energy = min(player['energy'] + energy_gained, GameConfig.ENERGY_MAX)
                    db.update_player_stats(user_id, {'energy': new_energy})

    db.conn.commit()

def initialize_player_energy(user_id: int):
    """Инициализирует систему энергии для нового игрока"""
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO energy_system (user_id, energy_accumulated)
        VALUES (?, ?)
    ''', (user_id, GameConfig.ENERGY_MAX))
    db.conn.commit()

# ==============================
# СИСТЕМА ДОСТИЖЕНИЙ
# ==============================

class AchievementSystem:
    ACHIEVEMENTS = {
        'first_blood': {
            'name': '🩸 Первая кровь',
            'description': 'Победить первого монстра',
            'reward_gold': 100,
            'reward_sapphires': 1
        },
        'pvp_master': {
            'name': '⚔️ Мастер PvP',
            'description': 'Выиграть 10 PvP боев',
            'reward_gold': 500,
            'reward_sapphires': 5
        },
        'boss_slayer': {
            'name': '🐉 Убийца боссов',
            'description': 'Победить 5 разных боссов',
            'reward_gold': 1000,
            'reward_sapphires': 10
        },
        'mine_tycoon': {
            'name': '⛏️ Магнат шахт',
            'description': 'Достичь 5 уровня шахты',
            'reward_gold': 800,
            'reward_sapphires': 8
        },
        'clan_leader': {
            'name': '🏰 Лидер клана',
            'description': 'Создать собственный клан',
            'reward_gold': 2000,
            'reward_sapphires': 15
        },
        'rich_player': {
            'name': '💰 Богач',
            'description': 'Накопить 100,000 золота',
            'reward_gold': 5000,
            'reward_sapphires': 20
        },
        'level_50': {
            'name': '🎯 Опытный воин',
            'description': 'Достичь 50 уровня',
            'reward_gold': 3000,
            'reward_sapphires': 25
        },
        'royal_champion': {
            'name': '👑 Чемпион королевской битвы',
            'description': 'Победить в королевской битве',
            'reward_gold': 2000,
            'reward_sapphires': 15
        }
    }

    @classmethod
    def check_achievements(cls, user_id: int, achievement_type: str, progress: int = 1):
        """Проверяет и выдает достижения"""
        cursor = db.conn.cursor()

        if achievement_type == 'first_kill' and progress >= 1:
            cls.grant_achievement(user_id, 'first_blood')

        elif achievement_type == 'pvp_wins' and progress >= 10:
            cls.grant_achievement(user_id, 'pvp_master')

        elif achievement_type == 'boss_kills' and progress >= 5:
            cls.grant_achievement(user_id, 'boss_slayer')

        elif achievement_type == 'mine_level' and progress >= 5:
            cls.grant_achievement(user_id, 'mine_tycoon')

        elif achievement_type == 'clan_created' and progress >= 1:
            cls.grant_achievement(user_id, 'clan_leader')

        elif achievement_type == 'gold_accumulated' and progress >= 100000:
            cls.grant_achievement(user_id, 'rich_player')

        elif achievement_type == 'player_level' and progress >= 50:
            cls.grant_achievement(user_id, 'level_50')

        elif achievement_type == 'royal_wins' and progress >= 1:
            cls.grant_achievement(user_id, 'royal_champion')

    @classmethod
    def grant_achievement(cls, user_id: int, achievement_id: str):
        """Выдает достижение игроку"""
        cursor = db.conn.cursor()

        # Проверяем не получено ли уже достижение
        cursor.execute('SELECT 1 FROM achievements WHERE user_id = ? AND achievement_id = ?', (user_id, achievement_id))
        if cursor.fetchone():
            return

        achievement = cls.ACHIEVEMENTS.get(achievement_id)
        if not achievement:
            return

        # Добавляем достижение
        cursor.execute('''
            INSERT INTO achievements (user_id, achievement_id, achievement_name, achievement_description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, achievement_id, achievement['name'], achievement['description']))

        db.conn.commit()

        # Уведомляем игрока
        asyncio.create_task(notify_achievement(user_id, achievement))

async def notify_achievement(user_id: int, achievement: Dict):
    """Уведомляет игрока о новом достижении"""
    try:
        await bot.send_message(
            user_id,
            f"🎉 **Новое достижение!**\n\n"
            f"🏆 {achievement['name']}\n"
            f"📝 {achievement['description']}\n\n"
            f"Награда: {achievement.get('reward_gold', 0)}💰 + {achievement.get('reward_sapphires', 0)}💎\n\n"
            f"Напиши 'достижения' чтобы посмотреть все свои достижения!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Не удалось уведомить о достижении: {e}")

@router.message(Command('achievements'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'достижения')
async def cmd_achievements(message: Message):
    user_id = message.from_user.id

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT achievement_name, achievement_description, achieved_at, reward_claimed
        FROM achievements
        WHERE user_id = ?
        ORDER BY achieved_at DESC
    ''', (user_id,))

    achievements = cursor.fetchall()

    if not achievements:
        await message.answer(
            "🏆 **Достижения**\n\n"
            "У тебя пока нет достижений!\n"
            "Играй в разные режимы и выполняй задания чтобы получать достижения.",
            parse_mode='Markdown'
        )
        return

    achievements_text = "🏆 **Твои достижения**\n\n"

    claimed_count = 0
    for name, description, achieved_at, claimed in achievements:
        status = "✅" if claimed else "🔄"
        date = datetime.fromisoformat(achieved_at).strftime("%d.%m.%Y")
        achievements_text += f"{status} **{name}**\n📅 {date}\n📝 {description}\n\n"

        if claimed:
            claimed_count += 1

    total_count = len(achievements)
    achievements_text += f"📊 Прогресс: {claimed_count}/{total_count} достижений получено"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Забрать награды", callback_data="achievements_claim")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await message.answer(achievements_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# СИСТЕМА ЕЖЕДНЕВНЫХ НАГРАД
# ==============================

@router.message(Command('daily'))
@router.message(lambda message: NaturalLanguageProcessor.process_text(message.text) == 'ежедневная награда')
async def cmd_daily(message: Message):
    user_id = message.from_user.id
    player = db.get_player(user_id)

    if not player:
        await message.answer("❌ Сначала создай персонажа!", show_alert=True)
        return

    cursor = db.conn.cursor()
    cursor.execute('SELECT last_reward_date, streak_count FROM daily_rewards WHERE user_id = ?', (user_id,))
    daily_data = cursor.fetchone()

    today = datetime.now().date()

    if not daily_data:
        # Первая награда
        await claim_daily_reward(message, user_id, 1, True)
        return

    last_reward_date_str, streak_count = daily_data
    last_reward_date = datetime.fromisoformat(last_reward_date_str).date() if last_reward_date_str else None

    if last_reward_date == today:
        # Уже получал сегодня
        next_reward = today + timedelta(days=1)
        await message.answer(
            f"🎁 **Ежедневная награда**\n\n"
            f"❌ Ты уже получал награду сегодня!\n"
            f"📅 Следующая награда: {next_reward.strftime('%d.%m.%Y')}\n"
            f"🔥 Серия: {streak_count} дней\n\n"
            f"Не пропусти завтра!",
            parse_mode='Markdown'
        )
        return

    elif last_reward_date and (today - last_reward_date).days == 1:
        # Продолжение серии
        new_streak = streak_count + 1
        await claim_daily_reward(message, user_id, new_streak, False)
    else:
        # Сброс серии
        await claim_daily_reward(message, user_id, 1, True)

async def claim_daily_reward(message: Message, user_id: int, streak: int, reset_streak: bool):
    """Выдает ежедневную награду"""
    # Рассчитываем награду в зависимости от серии
    base_gold = 100
    base_sapphires = 1

    streak_bonus = min(streak * 20, 200)  # Макс бонус 200 золота
    sapphire_bonus = streak // 7  # +1 сапфир каждые 7 дней

    total_gold = base_gold + streak_bonus
    total_sapphires = base_sapphires + sapphire_bonus

    # Выдаем награду
    player = db.get_player(user_id)
    db.update_player_stats(user_id, {
        'gold': player['gold'] + total_gold,
        'sapphires': player['sapphires'] + total_sapphires
    })

    # Обновляем запись
    cursor = db.conn.cursor()
    if reset_streak:
        cursor.execute('''
            INSERT OR REPLACE INTO daily_rewards (user_id, last_reward_date, streak_count, total_rewards)
            VALUES (?, DATE('now'), ?, COALESCE((SELECT total_rewards FROM daily_rewards WHERE user_id = ?), 0) + 1)
        ''', (user_id, streak, user_id))
    else:
        cursor.execute('''
            UPDATE daily_rewards
            SET last_reward_date = DATE('now'), streak_count = ?, total_rewards = total_rewards + 1
            WHERE user_id = ?
        ''', (streak, user_id))

    db.conn.commit()

    reward_text = (
        f"🎁 **Ежедневная награда получена!**\n\n"
        f"💰 Золото: +{total_gold}\n"
        f"💎 Сапфиры: +{total_sapphires}\n"
        f"🔥 Серия: {streak} дней\n\n"
    )

    if streak >= 7:
        reward_text += f"🎊 Поздравляем! Ты получаешь бонус за {streak} дней серии!\n\n"

    reward_text += f"💫 Заходи завтра для следующей награды!"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ На охоту", callback_data="hunt_start")],
        [InlineKeyboardButton(text="👤 В профиль", callback_data="back_to_profile")]
    ])

    await message.answer(reward_text, reply_markup=keyboard, parse_mode='Markdown')

# ==============================
# ОПТИМИЗАЦИЯ И УТИЛИТЫ
# ==============================

class GameUtils:
    @staticmethod
    def calculate_required_exp(level: int) -> int:
        """Рассчитывает необходимый опыт для уровня"""
        return level * 100

    @staticmethod
    def calculate_level_up_rewards(level: int) -> Dict:
        """Рассчитывает награды за повышение уровня"""
        return {
            'gold': level * 50,
            'sapphires': 1 if level % 5 == 0 else 0,
            'energy': GameConfig.ENERGY_MAX,
            'skill_points': 2
        }

    @staticmethod
    def apply_global_multipliers(base_value: int, value_type: str) -> int:
        """Применяет глобальные множители"""
        cursor = db.conn.cursor()

        if value_type == 'gold':
            cursor.execute('SELECT value FROM global_settings WHERE key = ?', ('gold_drop_multiplier',))
        elif value_type == 'exp':
            cursor.execute('SELECT value FROM global_settings WHERE key = ?', ('exp_multiplier',))
        else:
            return base_value

        result = cursor.fetchone()
        multiplier = float(result[0]) if result else 1.0

        return int(base_value * multiplier)

# Автоматическое обновление энергии
async def energy_update_task():
    """Фоновая задача для обновления энергии"""
    while True:
        try:
            await update_energy_system()
            await asyncio.sleep(60)  # Обновляем каждую минуту
        except Exception as e:
            print(f"Ошибка в задаче обновления энергии: {e}")
            await asyncio.sleep(60)

# Автоматический сброс боссов
async def boss_reset_task():
    """Фоновая задача для сброса боссов"""
    while True:
        try:
            await reset_daily_bosses()
            await asyncio.sleep(3600)  # Проверяем каждый час
        except Exception as e:
            print(f"Ошибка в задаче сброса боссов: {e}")
            await asyncio.sleep(3600)

async def reset_daily_bosses():
    """Сбрасывает боссов в полночь"""
    now = datetime.now()
    if now.hour == 0 and now.minute == 0:
        cursor = db.conn.cursor()
        cursor.execute('DELETE FROM boss_current_status')
        cursor.execute('UPDATE boss_battles SET reward_received = TRUE')
        db.conn.commit()
        print("✅ Боссы сброшены!")

# ==============================
# КОМАНДА СТАТУСА ИГРЫ
# ==============================

@router.message(Command('status'))
async def cmd_status(message: Message):
    """Показывает статус игры и онлайн статистику"""
    cursor = db.conn.cursor()

    # Статистика сервера
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM players WHERE DATE(created_at) = DATE("now")')
    new_today = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM clans')
    total_clans = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM royal_battles WHERE is_active = TRUE')
    active_battles = cursor.fetchone()[0]

    # Глобальные настройки
    cursor.execute('SELECT key, value FROM global_settings WHERE key IN ("game_version", "maintenance_mode")')
    settings = {key: value for key, value in cursor.fetchall()}

    status_text = (
        f"🎮 **Статус Magic RPG**\n\n"
        f"📊 Статистика сервера:\n"
        f"👥 Всего игроков: {total_players}\n"
        f"🆕 Новых сегодня: {new_today}\n"
        f"🏰 Кланов: {total_clans}\n"
        f"⚔️ Активных битв: {active_battles}\n\n"
        f"⚙️ Настройки:\n"
        f"🎯 Версия: {settings.get('game_version', '1.0.0')}\n"
        f"🔧 Техобслуживание: {'✅ Выкл' if settings.get('maintenance_mode') == 'false' else '❌ Вкл'}\n\n"
        f"🕐 Серверное время: {datetime.now().strftime('%H:%:%S %d.%m.%Y')}"
    )

    await message.answer(status_text, parse_mode='Markdown')

# ==============================
# ОБНОВЛЕНИЕ БАЗОВЫХ ФУНКЦИЙ
# ==============================

# Обновляем функцию создания игрока для инициализации энергии
def update_create_player():
    """Обновленная функция создания игрока"""
    original_create_player = db.create_player

    def new_create_player(user_id: int, username: str, character_name: str, character_class: str):
        original_create_player(user_id, username, character_name, character_class)
        initialize_player_energy(user_id)
        # Проверяем достижение за создание персонажа
        AchievementSystem.check_achievements(user_id, 'player_level', 1)

    db.create_player = new_create_player

# Обновляем функцию охоты для проверки достижений
async def update_hunt_victory(callback: CallbackQuery, state: FSMContext, player: Dict, monster: Dict):
    """Обновленная функция победы в охоте"""
    # Вызываем оригинальную логику (из части 3)
    # ... существующий код победы ...

    # Проверяем достижения
    AchievementSystem.check_achievements(player['user_id'], 'first_kill', 1)
    AchievementSystem.check_achievements(player['user_id'], 'player_level', player['level'])

# Инициализируем обновления
update_create_player()

# Запускаем фоновые задачи при старте
async def on_startup():
    """Запускается при старте бота"""
    asyncio.create_task(energy_update_task())
    asyncio.create_task(boss_reset_task())
    print("✅ Фоновые задачи запущены!")

# ==============================
# ФИНАЛЬНЫЕ КОМАНДЫ
# ==============================

@router.message(Command('guide'))
async def cmd_guide(message: Message):
    """Полное руководство по игре"""
    guide_text = (
        "📚 **Полное руководство по Magic RPG**\n\n"

        "🎯 **Основные команды:**\n"
        "• /start - Начать игру\n"
        "• /profile - Профиль персонажа\n"
        "• /hunt - Охота на монстров\n"
        "• /pvp - PvP дуэли\n"
        "• /boss - Ежедневные боссы\n"
        "• /clan - Кланы\n"
        "• /mine - Шахты\n"
        "• /shop - Магазин\n"
        "• /royal - Королевская битва\n"
        "• /daily - Ежедневная награда\n"
        "• /achievements - Достижения\n"
        "• /guide - Это руководство\n\n"

        "💰 **Экономика:**\n"
        "• Золото - основная валюта\n"
        "• Сапфиры - редкая валюта\n"
        "• Энергия - восстанавливается со временем\n\n"

        "⚔️ **Советы для новичков:**\n"
        "1. Начни с охоты на монстров\n"
        "2. Участвуй в ежедневных событиях\n"
        "3. Присоединяйся к клану\n"
        "4. Улучшай шахту для пассивного дохода\n"
        "5. Открывай кейсы для редких предметов\n\n"

        "🎮 **Удачи в игре!** 🎉"
    )

    await message.answer(guide_text, parse_mode='Markdown')

    # ==============================
# ЧАСТЬ 10: ФИНАЛЬНЫЙ КОД - ЗАПУСК И ИНТЕГРАЦИЯ
# ==============================

# Добавляем недостающие импорты в начало файла
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ==============================
# ФИНАЛЬНЫЕ НАСТРОЙКИ И КОНФИГУРАЦИЯ
# ==============================

class FinalConfig:
    # Настройки базы данных
    DB_BACKUP_INTERVAL = 24 * 3600  # 24 часа в секундах

    # Настройки событий
    EVENT_CHECK_INTERVAL = 300  # 5 минут

    # Лимиты игры
    MAX_INVENTORY_SLOTS = 100
    MAX_CLAN_MEMBERS = 20
    MAX_MINE_LEVEL = 10

    # Награды
    ROYAL_BATTLE_REWARDS = {
        1: {"gold": 5000, "sapphires": 10, "title": "👑 Король битвы"},
        2: {"gold": 3000, "sapphires": 5, "title": "🥈 Серебряный воин"},
        3: {"gold": 2000, "sapphires": 3, "title": "🥉 Бронзовый боец"}
    }

# ==============================
# СИСТЕМА РЕГУЛЯРНЫХ ЗАДАЧ
# ==============================

scheduler = AsyncIOScheduler()

async def schedule_background_tasks():
    """Планирует все фоновые задачи"""

    # Ежедневный сброс в полночь
    scheduler.add_job(
        reset_daily_activities,
        CronTrigger(hour=0, minute=0),
        id='daily_reset'
    )

    # Проверка энергии каждую минуту
    scheduler.add_job(
        update_energy_system,
        'interval',
        minutes=1,
        id='energy_update'
    )

    # Резервное копирование базы данных каждые 24 часа
    scheduler.add_job(
        backup_database,
        'interval',
        hours=24,
        id='db_backup'
    )

    # Проверка событий каждые 5 минут
    scheduler.add_job(
        check_events,
        'interval',
        minutes=5,
        id='events_check'
    )

    scheduler.start()
    print("✅ Фоновые задачи запланированы!")

async def reset_daily_activities():
    """Сбрасывает ежедневные активности"""
    cursor = db.conn.cursor()

    # Сбрасываем боссов
    cursor.execute('DELETE FROM boss_current_status')
    cursor.execute('DELETE FROM boss_battles')

    # Сбрасываем лимиты PvP
    cursor.execute('UPDATE pvp_ratings SET last_pvp_date = NULL')

    # Обновляем ежедневные награды для всех
    cursor.execute('''
        UPDATE daily_rewards
        SET last_reward_date = NULL
        WHERE last_reward_date < DATE('now', '-1 day')
    ''')

    db.conn.commit()
    print("✅ Ежедневные активности сброшены!")

async def backup_database():
    """Создает резервную копию базы данных"""
    try:
        backup_name = f"backup_{int(time.time())}.db"
        import shutil
        shutil.copy2('magic_rpg.db', f'backups/{backup_name}')
        print(f"✅ Резервная копия создана: {backup_name}")
    except Exception as e:
        print(f"❌ Ошибка резервного копирования: {e}")

async def check_events():
    """Проверяет и обновляет события"""
    cursor = db.conn.cursor()
    now = datetime.now()

    # Активируем новые события
    cursor.execute('''
        UPDATE game_events
        SET is_active = TRUE
        WHERE start_time <= ? AND end_time > ? AND is_active = FALSE
    ''', (now.isoformat(), now.isoformat()))

    # Деактивируем завершенные события
    cursor.execute('''
        UPDATE game_events
        SET is_active = FALSE
        WHERE end_time <= ? AND is_active = TRUE
    ''', (now.isoformat(),))

    db.conn.commit()

# ==============================
# ФИНАЛЬНАЯ ИНТЕГРАЦИЯ СИСТЕМ
# ==============================

class GameMaster:
    """Главный класс управления игрой"""

    @staticmethod
    async def on_player_level_up(user_id: int, old_level: int, new_level: int):
        """Обрабатывает повышение уровня игрока"""
        player = db.get_player(user_id)

        # Выдаем награды за уровень
        rewards = GameUtils.calculate_level_up_rewards(new_level)

        db.update_player_stats(user_id, {
            'gold': player['gold'] + rewards['gold'],
            'sapphires': player['sapphires'] + rewards['sapphires'],
            'energy': GameConfig.ENERGY_MAX
        })

        # Даем очки улучшений
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE character_upgrades
            SET available_points = available_points + ?
            WHERE user_id = ?
        ''', (rewards['skill_points'], user_id))

        # Проверяем достижения
        AchievementSystem.check_achievements(user_id, 'player_level', new_level)

        # Уведомляем игрока
        await notify_level_up(user_id, new_level, rewards)

    @staticmethod
    async def on_pvp_victory(winner_id: int, loser_id: int):
        """Обрабатывает победу в PvP"""
        # Обновляем рейтинги
        cursor = db.conn.cursor()
        cursor.execute('SELECT rating FROM pvp_ratings WHERE user_id = ?', (winner_id,))
        winner_rating = cursor.fetchone()[0] if cursor.fetchone() else 1000

        cursor.execute('SELECT rating FROM pvp_ratings WHERE user_id = ?', (loser_id,))
        loser_rating = cursor.fetchone()[0] if cursor.fetchone() else 1000

        rating_change = calculate_rating_change(winner_rating, loser_rating)

        cursor.execute('''
            UPDATE pvp_ratings
            SET rating = rating + ?, wins = wins + 1, last_pvp_date = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (rating_change, winner_id))

        cursor.execute('''
            UPDATE pvp_ratings
            SET rating = rating - ?, losses = losses + 1, last_pvp_date = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (rating_change, loser_id))

        # Проверяем достижения
        cursor.execute('SELECT wins FROM pvp_ratings WHERE user_id = ?', (winner_id,))
        wins = cursor.fetchone()[0]
        AchievementSystem.check_achievements(winner_id, 'pvp_wins', wins)

        db.conn.commit()

    @staticmethod
    async def on_boss_defeated(boss_id: int):
        """Обрабатывает победу над боссом"""
        cursor = db.conn.cursor()

        # Находим всех участников боя с этим боссом сегодня
        cursor.execute('''
            SELECT user_id, damage_dealt
            FROM boss_battles
            WHERE boss_id = ? AND DATE(battled_at) = DATE('now')
            ORDER BY damage_dealt DESC
        ''', (boss_id,))

        participants = cursor.fetchall()

        # Выдаем бонусные награды топ-3 участникам
        for i, (user_id, damage) in enumerate(participants[:3], 1):
            bonus_gold = 1000 // i  # 1000, 500, 333...
            bonus_sapphires = max(1, 3 - i)  # 3, 2, 1

            player = db.get_player(user_id)
            db.update_player_stats(user_id, {
                'gold': player['gold'] + bonus_gold,
                'sapphires': player['sapphires'] + bonus_sapphires
            })

            # Уведомляем игроков
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 **Бонус за босса!**\n\n"
                    f"Ты занял {i} место по урону и получаешь:\n"
                    f"💰 +{bonus_gold} золота\n"
                    f"💎 +{bonus_sapphires} сапфиров",
                    parse_mode='Markdown'
                )
            except:
                pass

        # Проверяем достижения
        for user_id, damage in participants:
            cursor.execute('''
                SELECT COUNT(DISTINCT boss_id)
                FROM boss_battles
                WHERE user_id = ?
            ''', (user_id,))
            boss_kills = cursor.fetchone()[0]
            AchievementSystem.check_achievements(user_id, 'boss_kills', boss_kills)

        db.conn.commit()

async def notify_level_up(user_id: int, new_level: int, rewards: Dict):
    """Уведомляет о повышении уровня"""
    try:
        await bot.send_message(
            user_id,
            f"🎊 **Повышение уровня!**\n\n"
            f"🎯 Новый уровень: {new_level}\n"
            f"🏆 Награды:\n"
            f"💰 +{rewards['gold']} золота\n"
            f"💎 +{rewards['sapphires']} сапфиров\n"
            f"⚡ Энергия восстановлена\n"
            f"🔧 +{rewards['skill_points']} очков улучшений\n\n"
            f"Напиши 'улучшить' чтобы распределить очки!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Не удалось уведомить о повышении уровня: {e}")

# ==============================
# ОБНОВЛЕНИЕ СУЩЕСТВУЮЩИХ ФУНКЦИЙ
# ==============================

# Обновляем функцию завершения PvP боя
async def update_finish_pvp_battle(callback: CallbackQuery, battle_id: int, winner_id: int, loser_id: int, battle_log: str):
    """Обновленная функция завершения PvP боя"""
    # Вызываем обработчик победы
    await GameMaster.on_pvp_victory(winner_id, loser_id)

    # Оригинальная логика из части 4...
    victory_text = (
        f"🎉 **Победа в PvP!**\n\n"
        f"{battle_log}\n"
        f"🏆 Награды:\n"
        f"💰 Золото: +{rating_change * 2}\n"
        f"⭐ Опыт: +50\n"
        f"📈 Рейтинг: +{rating_change}\n\n"
        f"Поздравляем с победой!"
    )

    # ... остальная логика сообщения

# Обновляем функцию победы над боссом
async def update_handle_boss_defeated(boss_id: int):
    """Обновленная функция победы над боссом"""
    await GameMaster.on_boss_defeated(boss_id)

# ==============================
# СИСТЕМА ВОССТАНОВЛЕНИЯ ДАННЫХ
# ==============================

class DataRecovery:
    """Система восстановления данных игроков"""

    @staticmethod
    async def recover_player_data(user_id: int):
        """Восстанавливает данные игрока при необходимости"""
        cursor = db.conn.cursor()

        # Проверяем целостность данных
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        player = cursor.fetchone()

        if not player:
            return False

        # Восстанавливаем недостающие таблицы
        tables_to_check = [
            ('pvp_ratings', 'INSERT INTO pvp_ratings (user_id) VALUES (?)'),
            ('character_upgrades', 'INSERT INTO character_upgrades (user_id, available_points) VALUES (?, ?)'),
            ('daily_rewards', 'INSERT INTO daily_rewards (user_id) VALUES (?)'),
            ('energy_system', 'INSERT INTO energy_system (user_id, energy_accumulated) VALUES (?, ?)'),
            ('player_mines', 'INSERT INTO player_mines (user_id) VALUES (?)')
        ]

        for table, query in tables_to_check:
            cursor.execute(f'SELECT 1 FROM {table} WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                if 'available_points' in query:
                    cursor.execute(query, (user_id, max(0, player[4] - 1) * 2))  # level
                elif 'energy_accumulated' in query:
                    cursor.execute(query, (user_id, GameConfig.ENERGY_MAX))
                else:
                    cursor.execute(query, (user_id,))

        db.conn.commit()
        return True

# ==============================
# КОМАНДА ТЕХНИЧЕСКОЙ ПОДДЕРЖКИ
# ==============================

@router.message(Command('support'))
async def cmd_support(message: Message):
    """Команда технической поддержки"""
    support_text = (
        "🛠️ **Техническая поддержка**\n\n"

        "Если у тебя возникли проблемы:\n\n"

        "🔧 **Частые проблемы:**\n"
        "• Не обновляется энергия - подожди 1-2 минуты\n"
        "• Пропали предметы - используй /recover\n"
        "• Ошибка в бою - перезайди в бой\n\n"

        "🔄 **Восстановление данных:**\n"
        "Напиши /recover чтобы восстановить данные персонажа\n\n"

        "📝 **Сообщить об ошибке:**\n"
        "Опиши проблему и отправь @твоему_разработчику\n\n"

        "🎮 **Быстрые команды:**\n"
        "/recover - Восстановить данные\n"
        "/status - Статус сервера\n"
        "/guide - Руководство по игре"
    )

    await message.answer(support_text, parse_mode='Markdown')

@router.message(Command('recover'))
async def cmd_recover(message: Message):
    """Восстановление данных игрока"""
    user_id = message.from_user.id

    try:
        success = await DataRecovery.recover_player_data(user_id)

        if success:
            await message.answer(
                "✅ **Данные восстановлены!**\n\n"
                "Все системы проверены и восстановлены при необходимости.\n"
                "Если проблемы остались, обратись в поддержку.",
                parse_mode='Markdown'
            )
        else:
            await message.answer(
                "❌ **Игрок не найден!**\n\n"
                "Сначала создай персонажа командой /start",
                parse_mode='Markdown'
            )
    except Exception as e:
        await message.answer(
            "❌ **Ошибка восстановления!**\n\n"
            "Попробуй позже или обратись в поддержку.",
            parse_mode='Markdown'
        )

# ==============================
# ФИНАЛЬНАЯ ИНИЦИАЛИЗАЦИЯ БОТА
# ==============================

async def initialize_bot():
    """Инициализирует бота при запуске"""
    print("🎮 Magic RPG Bot запускается...")

    # Проверяем базу данных
    await check_database_integrity()

    # Запускаем фоновые задачи
    await schedule_background_tasks()

    # Восстанавливаем активные сессии
    await recover_active_sessions()

    print("✅ Бот успешно инициализирован!")
    print("🤖 Бот готов к работе!")

async def check_database_integrity():
    """Проверяет целостность базы данных"""
    try:
        cursor = db.conn.cursor()

        # Проверяем основные таблицы
        required_tables = ['players', 'inventory', 'clans', 'pvp_ratings', 'daily_bosses']

        for table in required_tables:
            cursor.execute(f'SELECT 1 FROM {table} LIMIT 1')

        print("✅ База данных проверена")

    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        # Здесь можно добавить автоматическое восстановление

async def recover_active_sessions():
    """Восстанавливает активные игровые сессии"""
    cursor = db.conn.cursor()

    # Очищаем зависшие PvP бои
    cursor.execute('DELETE FROM pvp_battles WHERE created_at < datetime("now", "-1 hour")')

    # Очищаем старые королевские битвы
    cursor.execute('DELETE FROM royal_battles WHERE created_at < datetime("now", "-3 hour")')

    # Очищаем завершенные тёмные охоты
    cursor.execute('DELETE FROM dark_hunt_sessions WHERE created_at < datetime("now", "-1 hour")')

    db.conn.commit()
    print("✅ Активные сессии восстановлены")

# ==============================
# ОБРАБОТЧИКИ ОШИБОК
# ==============================

async def error_handler(update: types.Update, exception: Exception):
    """Глобальный обработчик ошибок"""
    try:
        print(f"❌ Ошибка: {exception}")

        # Логируем ошибку
        with open('errors.log', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()}: {exception}\n")

        # Уведомляем пользователя
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.answer(
                    "❌ **Произошла ошибка!**\n\n"
                    "Попробуй еще раз или используй /support для помощи.",
                    parse_mode='Markdown'
                )
            except:
                pass

    except Exception as e:
        print(f"❌ Ошибка в обработчике ошибок: {e}")

    return True

# ==============================
# ЗАПУСК БОТА
# ==============================

async def main():
    """Главная функция запуска бота"""

    # Инициализируем бота
    await initialize_bot()

    # Настраиваем обработчики ошибок
    dp.errors.register(error_handler)

    # Запускаем бота
    print("🚀 Бот запущен! Ожидаем сообщения...")

    # Удаляем вебхук (если использовался ранее)
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем опрос
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

# ==============================
# ТОЧКА ВХОДА ПРОГРАММЫ
# ==============================

async def main():
    # Проверка подключения
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.telegram.org') as resp:
                print(f"Telegram API доступен: {resp.status}")
    except Exception as e:
        print(f"❌ Нет подключения к Telegram: {e}")
        return

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("📖 Бот остановлен пользователем")
    except Exception as e:
        print(f"✗ Критическая ошибка: {e}")