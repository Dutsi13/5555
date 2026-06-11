"""
╔══════════════════════════════════════════════╗
║              TELEGRAM BOT                    ║
║  Один файл — просто запусти и работает       ║
╚══════════════════════════════════════════════╝

Перед запуском заполни блок НАСТРОЙКИ ниже.

Установка:   pip install aiogram
Запуск:      python bot.py
"""

# ════════════════════════════════════════════════
#  ⚙️  НАСТРОЙКИ — заполни здесь
# ════════════════════════════════════════════════

BOT_TOKEN = "8944195871:AAHVYncfEok_Y8oiwF3CrMGNgXI75M53jCc"

# Админы через код: просто добавляй сюда нужные Telegram ID и username.
OWNER_IDS = [8794980269, 7785932103]
OWNER_USERNAMES = ["liviaskya", "stv18"]

# Ссылки для кнопок под профилем (можно менять)
PROFILE_LINK_ETERNAL  = "https://t.me/your_channel"   # «Вечная ссылка»
PROFILE_LINK_PROJECTS = "https://t.me/your_projects"  # «Другие наши проекты»
GUARANTORS_INFO_URL   = "https://t.me/your_guarant_info"
GUARANTORS_SEARCH_URL = "https://t.me/your_guarant_search"

# Название бота для строки «Проверено в @...»
BOT_USERNAME = "Xscam_bot"

# ════════════════════════════════════════════════
#  Импорты
# ════════════════════════════════════════════════

import asyncio
import html
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    MessageEntity,
    ReplyKeyboardMarkup,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ════════════════════════════════════════════════
#  💾  Хранилище
# ════════════════════════════════════════════════

_DIR           = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR      = os.path.join(_DIR, "data")
_SECTIONS_FILE = os.path.join(_DATA_DIR, "sections.json")
_ADMINS_FILE   = os.path.join(_DATA_DIR, "admins.json")
_USERS_FILE    = os.path.join(_DATA_DIR, "users.json")      # счётчик поисков
os.makedirs(_DATA_DIR, exist_ok=True)
_SETTINGS_FILE = os.path.join(_DATA_DIR, "settings.json")
_DEALS_FILE    = os.path.join(_DATA_DIR, "deals.json")

SPECIAL_URL_SELF_PROFILE = "__SELF_PROFILE__"
SPECIAL_URL_REPORT       = "__REPORT_SCAMMER__"
SPECIAL_URL_PROJECTS     = "__PROJECTS__"

DEFAULT_PROFILE_BUTTONS = [
    {"label": "🔗 Вечная ссылка", "url": SPECIAL_URL_SELF_PROFILE, "row": 1},
    {"label": "⚠️ Слить скамера в базу", "url": SPECIAL_URL_REPORT, "row": 2},
    {"label": "📁 Другие наши проекты", "url": SPECIAL_URL_PROJECTS, "row": 3},
]

DEFAULT_GUARANTOR_BUTTONS = [
    {"label": "❓ Кто такой гарант", "url": GUARANTORS_INFO_URL, "row": 2},
    {"label": "🔎 Поиск гарантов", "url": GUARANTORS_SEARCH_URL, "row": 2},
    {"label": "📁 Другие наши проекты", "url": SPECIAL_URL_PROJECTS, "row": 3},
]

DEAL_OPTIONS = [
    "MM2",
    "Деньги",
    "Адопт",
    "Блоксфрукт",
    "Робуксы",
    "Blade Ball",
    "Grow Garden",
]

DEAL_CANCEL_TEXT = "Отменить сделку"

_DEFAULT_SECTIONS: dict = {
    "profile": {
        "title":   "👁 Мой профиль",
        "text":    "",          # для профиля текст генерируется динамически
        "photo":   None,
        "sticker": None,
        "buttons": list(DEFAULT_PROFILE_BUTTONS),   # список {"label": "...", "url": "...", "row": 1}
    },
    "guarantors": {
        "title":   "🛡 Список гарантов",
        "text":    "🛡 Список гарантов:\n\n[здесь будет список гарантов]",
        "photo":   None,
        "sticker": None,
        "buttons": list(DEFAULT_GUARANTOR_BUTTONS),
    },
    "deal": {
        "title":   "🔄 Провести сделку через гаранта 🔄",
        "text":    "🔄 Создание сделки через гаранта:\n\n[здесь будет логика сделки]",
        "photo":   None,
        "sticker": None,
        "buttons": [],
    },
    "scammer": {
        "title":   "⚠️ Слить скамера",
        "text":    "⚠️ Сообщить о скамере:\n\n[здесь будет форма репорта]",
        "photo":   None,
        "sticker": None,
        "buttons": [],
    },
    "commands": {
        "title":   "📁 Команды",
        "text":    "📁 Доступные команды:\n\n/start — запустить бота\n/admin — войти в админ-панель",
        "photo":   None,
        "sticker": None,
        "buttons": [],
    },
    "about": {
        "title":   "ℹ️ О проекте",
        "text":    "ℹ️ О проекте:\n\n[здесь будет информация о проекте]",
        "photo":   None,
        "sticker": None,
        "buttons": [],
    },
    "sponsors": {
        "title":   "🤝 Спонсоры",
        "text":    "🤝 Наши спонсоры/партнёры:\n\n[здесь будет информация о спонсорах]",
        "photo":   None,
        "sticker": None,
        "buttons": [],
    },
}

BUTTON_TO_KEY = {s["title"]: k for k, s in _DEFAULT_SECTIONS.items()}


# ── Разделы ───────────────────────────────────────

def _load_sections() -> dict:
    if not os.path.exists(_SECTIONS_FILE):
        _save_sections(_DEFAULT_SECTIONS)
        return dict(_DEFAULT_SECTIONS)
    with open(_SECTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # добавляем новые поля если их нет (обратная совместимость)
    for k, v in _DEFAULT_SECTIONS.items():
        if k not in data:
            data[k] = dict(v)
        for field in ("sticker", "buttons", "entities", "template_chat_id", "template_message_id"):
            if field not in data[k]:
                data[k][field] = v.get(field)
    return data


def _save_sections(data: dict) -> None:
    with open(_SECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_section(key: str) -> dict:
    section = _load_sections().get(key, dict(_DEFAULT_SECTIONS[key]))
    section.setdefault("entities", [])
    section.setdefault("template_chat_id", None)
    section.setdefault("template_message_id", None)
    return section


def update_section_text(key: str, text: str, entities: Optional[list] = None) -> None:
    s = _load_sections()
    s[key]["text"] = text
    s[key]["entities"] = entities or []
    s[key]["template_chat_id"] = None
    s[key]["template_message_id"] = None
    _save_sections(s)


def update_section_template(key: str, chat_id: int, message_id: int, text: str, entities: Optional[list] = None) -> None:
    s = _load_sections()
    s[key]["text"] = text
    s[key]["entities"] = entities or []
    s[key]["template_chat_id"] = chat_id
    s[key]["template_message_id"] = message_id
    _save_sections(s)

def update_section_photo(key: str, file_id: Optional[str]) -> None:
    s = _load_sections(); s[key]["photo"] = file_id; _save_sections(s)

def update_section_sticker(key: str, file_id: Optional[str]) -> None:
    s = _load_sections(); s[key]["sticker"] = file_id; _save_sections(s)

def update_section_buttons(key: str, buttons: list) -> None:
    s = _load_sections(); s[key]["buttons"] = buttons; _save_sections(s)


def build_user_profile_url(user_id: int, username: Optional[str]) -> str:
    if username:
        return f"https://t.me/{username}"
    return f"tg://user?id={user_id}"


def normalize_admin_text_input(msg: Message) -> str:
    """Сохраняем сырой текст, чтобы Telegram Premium emoji не превращались в битый HTML."""
    return (msg.text or msg.caption or "").strip()


def normalize_admin_entities_input(msg: Message) -> list[dict]:
    source = msg.entities or msg.caption_entities or []
    return [entity.model_dump(exclude_none=True) for entity in source]


def build_entities(entity_data: Optional[list]) -> Optional[list[MessageEntity]]:
    if not entity_data:
        return None
    return [MessageEntity(**item) for item in entity_data]


def shift_entities(entity_data: Optional[list], offset: int) -> list[dict]:
    if not entity_data:
        return []
    shifted = []
    for item in entity_data:
        new_item = dict(item)
        new_item["offset"] = int(new_item.get("offset", 0)) + offset
        shifted.append(new_item)
    return shifted


def combine_text_entities(prefix_text: str, prefix_entities: Optional[list], suffix_text: str) -> tuple[str, list[dict]]:
    if not prefix_text:
        return suffix_text, []
    full_text = f"{prefix_text}\n\n{suffix_text}"
    return full_text, shift_entities(prefix_entities, 0)


def apply_text_replacements(text: str, entities: Optional[list], replacements: list[tuple[int, int, str]]) -> tuple[str, list[dict]]:
    if not replacements:
        return text, list(entities or [])

    result_text = text
    result_entities = [dict(entity) for entity in (entities or [])]

    for start, end, new_value in sorted(replacements, key=lambda item: item[0], reverse=True):
        old_len = end - start
        delta = len(new_value) - old_len
        result_text = result_text[:start] + new_value + result_text[end:]

        updated_entities = []
        for entity in result_entities:
            ent_start = int(entity.get("offset", 0))
            ent_end = ent_start + int(entity.get("length", 0))

            if ent_end <= start:
                updated_entities.append(entity)
                continue
            if ent_start >= end:
                shifted = dict(entity)
                shifted["offset"] = ent_start + delta
                updated_entities.append(shifted)
                continue

            # Если сущность пересекается с заменяемым куском, безопаснее её убрать.
        result_entities = updated_entities

    return result_text, result_entities


def render_profile_template_text(template_text: str, template_entities: Optional[list], username_text: str, user_id_text: str) -> tuple[str, list[dict]]:
    text = template_text or ""
    entities = list(template_entities or [])
    replacements: list[tuple[int, int, str]] = []

    placeholder_patterns = [
        (r"\{username\}", username_text),
        (r"\{user_id\}", user_id_text),
    ]
    for pattern, value in placeholder_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            replacements.append((match.start(), match.end(), value))

    if not replacements:
        name_match = re.search(r"(Имя:\s*)([^\n]+)", text, flags=re.IGNORECASE)
        if name_match:
            replacements.append((name_match.start(2), name_match.end(2), username_text))

        id_match = re.search(r"((?:🆔\s*)?(?:id|ID)\s*:\s*)([^\n]+)", text)
        if id_match:
            replacements.append((id_match.start(2), id_match.end(2), user_id_text))

    return apply_text_replacements(text, entities, replacements)


def apply_named_placeholders(text: str, entities: Optional[list], values: dict[str, str]) -> tuple[str, list[dict]]:
    replacements: list[tuple[int, int, str]] = []
    for key, value in values.items():
        pattern = r"\{" + re.escape(key) + r"\}"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            replacements.append((match.start(), match.end(), value))
    return apply_text_replacements(text, entities, replacements)


def split_text_and_entities_by_pages(text: str, entities: Optional[list]) -> list[tuple[str, list[dict]]]:
    separator = "\n---PAGE---\n"
    if not text:
        return [("🛡 Список гарантов:\n\n[здесь будет список гарантов]", [])]

    pages: list[tuple[str, list[dict]]] = []
    start = 0
    while True:
        index = text.find(separator, start)
        if index == -1:
            raw_page = text[start:]
            page_start = start
            page_end = len(text)
        else:
            raw_page = text[start:index]
            page_start = start
            page_end = index

        leading_trimmed = len(raw_page) - len(raw_page.lstrip())
        trailing_trimmed = len(raw_page.rstrip())
        trimmed_page = raw_page.strip()

        if trimmed_page:
            abs_start = page_start + leading_trimmed
            abs_end = page_start + trailing_trimmed
            page_entities = []
            for entity in entities or []:
                ent_start = int(entity.get("offset", 0))
                ent_end = ent_start + int(entity.get("length", 0))
                if ent_start >= abs_start and ent_end <= abs_end:
                    new_item = dict(entity)
                    new_item["offset"] = ent_start - abs_start
                    page_entities.append(new_item)
            pages.append((trimmed_page, page_entities))

        if index == -1:
            break
        start = index + len(separator)

    return pages or [("🛡 Список гарантов:\n\n[здесь будет список гарантов]", [])]


def sanitize_custom_emoji_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", r"\1", text, flags=re.DOTALL)


def render_section_text(text: str) -> str:
    return sanitize_custom_emoji_html(text or "")


def format_send_error_fallback(text: str) -> str:
    return html.escape(re.sub(r"<[^>]+>", "", sanitize_custom_emoji_html(text or "")))


def is_bad_photo_error(error: TelegramBadRequest) -> bool:
    return "wrong file identifier" in str(error).lower() or "http url specified" in str(error).lower()


def get_code_owner_ids() -> set[int]:
    raw = globals().get("OWNER_IDS", [])
    if not isinstance(raw, (list, tuple, set)):
        raw = [raw]
    result: set[int] = set()
    for item in raw:
        try:
            result.add(int(str(item).strip()))
        except (TypeError, ValueError):
            continue
    return result


def get_code_owner_usernames() -> set[str]:
    raw = globals().get("OWNER_USERNAMES", [])
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    elif not isinstance(raw, (list, tuple, set)):
        raw = [raw]

    result: set[str] = set()
    for item in raw:
        value = str(item or "").strip().lstrip("@").lower()
        if value:
            result.add(value)
    return result


def resolve_button_url(url: str, user_id: Optional[int] = None, username: Optional[str] = None) -> str:
    if url == SPECIAL_URL_SELF_PROFILE:
        return build_user_profile_url(user_id or 0, username)
    if url == SPECIAL_URL_REPORT:
        uname = f"@{username}" if username else str(user_id or 0)
        return f"https://t.me/share/url?url={uname}&text=Скамер"
    if url == SPECIAL_URL_PROJECTS:
        return PROFILE_LINK_PROJECTS
    return url


def build_inline_keyboard(buttons: list, user_id: Optional[int] = None, username: Optional[str] = None) -> Optional[InlineKeyboardMarkup]:
    """Строим inline-клавиатуру из сохранённых кнопок раздела с поддержкой рядов."""
    if not buttons:
        return None

    grouped_rows: dict[int, list[InlineKeyboardButton]] = {}
    for index, button in enumerate(buttons, 1):
        label = button.get("label", "").strip()
        url = button.get("url", "").strip()
        if not label or not url:
            continue
        row = button.get("row", index)
        try:
            row = int(row)
        except (TypeError, ValueError):
            row = index
        grouped_rows.setdefault(row, []).append(
            InlineKeyboardButton(
                text=label,
                url=resolve_button_url(url, user_id=user_id, username=username),
            )
        )

    if not grouped_rows:
        return None

    rows = [grouped_rows[row] for row in sorted(grouped_rows)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_guarantor_pages(text: str) -> list[str]:
    pages = [page.strip() for page in text.split("\n---PAGE---\n")]
    pages = [page for page in pages if page]
    return pages or ["🛡 Список гарантов:\n\n[здесь будет список гарантов]"]


def ikb_guarantors(page: int, total_pages: int, user_id: int, username: Optional[str]) -> InlineKeyboardMarkup:
    buttons = get_section("guarantors").get("buttons", [])
    extra = build_inline_keyboard(buttons, user_id=user_id, username=username)

    nav_rows = [[
        InlineKeyboardButton(text="◀️", callback_data=f"guarantors_page_{max(page - 1, 0)}"),
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="guarantors_page_info"),
        InlineKeyboardButton(text="▶️", callback_data=f"guarantors_page_{min(page + 1, total_pages - 1)}"),
    ]]
    if extra:
        nav_rows.extend(extra.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=nav_rows)


# ── Пользователи (счётчик поисков) ───────────────

def _load_users() -> dict:
    if not os.path.exists(_USERS_FILE):
        return {}
    with open(_USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_users(data: dict) -> None:
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_user_storage_key(user_id: Optional[int], username: Optional[str]) -> str:
    if user_id:
        return str(user_id)
    if username:
        return f"uname:{username.lower().lstrip('@')}"
    return "unknown"


def ensure_user_storage_key(user_id: Optional[int], username: Optional[str]) -> str:
    primary_key = make_user_storage_key(user_id, username)
    if not user_id or not username:
        return primary_key

    users = _load_users()
    id_key = str(user_id)
    username_key = f"uname:{username.lower().lstrip('@')}"
    username_data = users.get(username_key)
    if not username_data:
        return id_key

    id_data = users.get(id_key)
    if not id_data:
        users[id_key] = username_data
    else:
        users[id_key] = {
            "searches": int(id_data.get("searches", 0)) + int(username_data.get("searches", 0)),
            "likes": int(id_data.get("likes", 0)) + int(username_data.get("likes", 0)),
            "dislikes": int(id_data.get("dislikes", 0)) + int(username_data.get("dislikes", 0)),
            "in_base": bool(id_data.get("in_base", False) or username_data.get("in_base", False)),
            "role": id_data.get("role") or username_data.get("role") or "Пользователь",
        }
    users.pop(username_key, None)
    _save_users(users)
    return id_key


def get_user_data_by_key(user_key: str) -> dict:
    users = _load_users()
    return users.get(user_key, {"searches": 0, "role": "Пользователь", "in_base": False, "likes": 0, "dislikes": 0})


def get_user_data(user_id: int) -> dict:
    return get_user_data_by_key(ensure_user_storage_key(user_id, None))


def increment_search_by_key(user_key: str) -> int:
    users = _load_users()
    if user_key not in users:
        users[user_key] = {"searches": 0, "role": "Пользователь", "in_base": False, "likes": 0, "dislikes": 0}
    users[user_key]["searches"] += 1
    _save_users(users)
    return users[user_key]["searches"]


def increment_search(user_id: int) -> int:
    return increment_search_by_key(str(user_id))


def increment_reaction(user_key: str, reaction: str) -> tuple[int, int]:
    users = _load_users()
    if user_key not in users:
        users[user_key] = {"searches": 0, "role": "Пользователь", "in_base": False, "likes": 0, "dislikes": 0}
    users[user_key][reaction] = int(users[user_key].get(reaction, 0)) + 1
    _save_users(users)
    return int(users[user_key].get("likes", 0)), int(users[user_key].get("dislikes", 0))


def _load_settings() -> dict:
    if not os.path.exists(_SETTINGS_FILE):
        data = {
            "deal_group_link": "https://t.me/your_deal_group",
            "check_photo": None,
            "check_sticker": None,
            "check_text": "",
            "check_entities": [],
            "checker_guarantor_role": "",
            "checker_guarantor_channel": "",
            "checker_rating": "",
            "checker_deal_price": "",
            "checker_proofs": "",
        }
        _save_settings(data)
        return data
    with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("deal_group_link", "https://t.me/your_deal_group")
    data.setdefault("check_photo", None)
    data.setdefault("check_sticker", None)
    data.setdefault("check_text", "")
    data.setdefault("check_entities", [])
    data.setdefault("checker_guarantor_role", "")
    data.setdefault("checker_guarantor_channel", "")
    data.setdefault("checker_rating", "")
    data.setdefault("checker_deal_price", "")
    data.setdefault("checker_proofs", "")
    return data


def _save_settings(data: dict) -> None:
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_deal_group_link() -> str:
    return _load_settings().get("deal_group_link", "https://t.me/your_deal_group")


def set_deal_group_link(url: str) -> None:
    data = _load_settings()
    data["deal_group_link"] = url
    _save_settings(data)


def get_check_photo() -> Optional[str]:
    return _load_settings().get("check_photo")


def set_check_photo(file_id: Optional[str]) -> None:
    data = _load_settings()
    data["check_photo"] = file_id
    _save_settings(data)


def get_check_sticker() -> Optional[str]:
    return _load_settings().get("check_sticker")


def set_check_sticker(file_id: Optional[str]) -> None:
    data = _load_settings()
    data["check_sticker"] = file_id
    _save_settings(data)


def get_check_text() -> str:
    return _load_settings().get("check_text", "")


def get_check_entities() -> list:
    return _load_settings().get("check_entities", [])


def set_check_text(text: str, entities: Optional[list] = None) -> None:
    data = _load_settings()
    data["check_text"] = text
    data["check_entities"] = entities or []
    _save_settings(data)


def get_checker_fields() -> dict:
    data = _load_settings()
    return {
        "guarantor_role": data.get("checker_guarantor_role", ""),
        "guarantor_channel": data.get("checker_guarantor_channel", ""),
        "rating": data.get("checker_rating", ""),
        "deal_price": data.get("checker_deal_price", ""),
        "proofs": data.get("checker_proofs", ""),
    }


def set_checker_fields(fields: dict) -> None:
    data = _load_settings()
    data["checker_guarantor_role"] = fields.get("guarantor_role", "")
    data["checker_guarantor_channel"] = fields.get("guarantor_channel", "")
    data["checker_rating"] = fields.get("rating", "")
    data["checker_deal_price"] = fields.get("deal_price", "")
    data["checker_proofs"] = fields.get("proofs", "")
    _save_settings(data)


def _load_deals() -> dict:
    if not os.path.exists(_DEALS_FILE):
        data = {"counter_by_date": {}, "users_last_deal": {}}
        _save_deals(data)
        return data
    with open(_DEALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_deals(data: dict) -> None:
    with open(_DEALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def can_create_deal_today(user_id: int, date_key: str) -> bool:
    deals = _load_deals()
    return deals.get("users_last_deal", {}).get(str(user_id)) != date_key


def create_deal_record(user_id: int, date_key: str) -> str:
    deals = _load_deals()
    counter_by_date = deals.setdefault("counter_by_date", {})
    users_last_deal = deals.setdefault("users_last_deal", {})

    next_number = int(counter_by_date.get(date_key, 0)) + 1
    counter_by_date[date_key] = next_number
    users_last_deal[str(user_id)] = date_key
    _save_deals(deals)
    return f"{date_key}{next_number:04d}"


# ── Администраторы ────────────────────────────────

def _load_admins() -> list:
    if not os.path.exists(_ADMINS_FILE):
        _save_admins([]); return []
    with open(_ADMINS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_admins(admins: list) -> None:
    with open(_ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)

def is_admin(user_id: int, username: Optional[str] = None) -> bool:
    if user_id in get_code_owner_ids():
        return True
    if username and username.lower().lstrip("@") in get_code_owner_usernames():
        return True
    for a in _load_admins():
        if a["id"] == user_id:
            return True
        if username and a.get("username", "").lower() == username.lower():
            return True
    return False

def add_admin(user_id: int, username: Optional[str] = None) -> bool:
    admins = _load_admins()
    if any(a["id"] == user_id for a in admins):
        return False
    admins.append({"id": user_id, "username": username or ""})
    _save_admins(admins); return True

def remove_admin_by_id(user_id: int) -> bool:
    admins = _load_admins()
    new = [a for a in admins if a["id"] != user_id]
    if len(new) == len(admins): return False
    _save_admins(new); return True

def remove_admin_by_username(username: str) -> bool:
    admins = _load_admins()
    new = [a for a in admins if a.get("username", "").lower() != username.lower()]
    if len(new) == len(admins): return False
    _save_admins(new); return True


# ════════════════════════════════════════════════
#  🔑  Фильтры
# ════════════════════════════════════════════════

class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        u = message.from_user
        return is_admin(u.id, u.username) if u else False

class IsAdminCB(BaseFilter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        u = cb.from_user
        return is_admin(u.id, u.username) if u else False


# ════════════════════════════════════════════════
#  ⌨️  Клавиатуры
# ════════════════════════════════════════════════

def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👁 Мой профиль"),
             KeyboardButton(text="🛡 Список гарантов")],
            [KeyboardButton(text="🔄 Провести сделку через гаранта 🔄")],
            [KeyboardButton(text="⚠️ Слить скамера")],
            [KeyboardButton(text="📁 Команды"),
             KeyboardButton(text="ℹ️ О проекте")],
        ],
        resize_keyboard=True,
    )

def kb_admin_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Редактировать разделы")],
            [KeyboardButton(text="🛡 Чекер")],
            [KeyboardButton(text="🔗 Ссылка группы сделок")],
            [KeyboardButton(text="👥 Управление админами")],
            [KeyboardButton(text="🔙 Выйти из админ-панели")],
        ],
        resize_keyboard=True,
    )

def ikb_sections() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=s["title"], callback_data=f"edit_{k}")]
        for k, s in _DEFAULT_SECTIONS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ikb_section_actions(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст",   callback_data=f"set_text_{key}"),
         InlineKeyboardButton(text="🖼 Изменить фото",    callback_data=f"set_photo_{key}")],
        [InlineKeyboardButton(text="🎭 Добавить стикер",  callback_data=f"set_sticker_{key}"),
         InlineKeyboardButton(text="🗑 Удалить стикер",   callback_data=f"del_sticker_{key}")],
        [InlineKeyboardButton(text="🔗 Кнопки-ссылки",   callback_data=f"set_buttons_{key}"),
         InlineKeyboardButton(text="🗑 Удалить фото",     callback_data=f"del_photo_{key}")],
        [InlineKeyboardButton(text="◀️ Назад",            callback_data="back_to_sections")],
    ])

def ikb_admins_manage() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="➖ Удалить админа",  callback_data="admin_remove")],
        [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
    ])


def ikb_checker_manage() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Текст /check", callback_data="checker_text")],
        [InlineKeyboardButton(text="🖼 Фото /check", callback_data="checker_photo")],
        [InlineKeyboardButton(text="🎭 Стикер /check", callback_data="checker_sticker")],
        [InlineKeyboardButton(text="🛡 Данные гаранта", callback_data="checker_fields")],
    ])

def ikb_profile(user_id: int, username: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    """Inline-кнопки под карточкой профиля."""
    user_key = ensure_user_storage_key(user_id, username)
    stats = get_user_data_by_key(user_key)
    extra = build_inline_keyboard(
        get_section("profile").get("buttons", []),
        user_id=user_id,
        username=username,
    )
    rows = [[
        InlineKeyboardButton(text=f"👍 [{int(stats.get('likes', 0))}]", callback_data=f"profile_like:{user_key}"),
        InlineKeyboardButton(text=f"👎 [{int(stats.get('dislikes', 0))}]", callback_data=f"profile_dislike:{user_key}"),
    ]]
    if extra:
        rows.extend(extra.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_deal_choices() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=option)] for option in DEAL_OPTIONS]
    rows.append([KeyboardButton(text=DEAL_CANCEL_TEXT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def kb_deal_confirm() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Начать сделку")],
            [KeyboardButton(text=DEAL_CANCEL_TEXT)],
        ],
        resize_keyboard=True,
    )


def ikb_deal_group() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в группу ↗️", url=get_deal_group_link())]
        ]
    )


def commands_text() -> str:
    return (
        "🪼 Для всех пользователей\n"
        "/check — Проверить на скам (ответом на сообщение или по @user/ID)\n"
        "/me — Мой профиль и статус\n"
        "/info — О проекте и ссылки\n"
        "/sponsors — Наши спонсоры/партнёры\n"
        "/garants — Список гарантов\n"
        "/admins — Список администраторов\n"
        "/start_deal — Начать сделку через гаранта\n"
        "/help — Справка по командам"
    )


def ensure_commands_section_text() -> None:
    sec = get_section("commands")
    if not (sec.get("text") or "").strip():
        update_section_text("commands", commands_text())


ensure_commands_section_text()


def admins_text() -> str:
    admins = _load_admins()
    code_owner_ids = sorted(get_code_owner_ids())
    code_owner_usernames = sorted(get_code_owner_usernames())
    owner_lines = []
    max_len = max(len(code_owner_ids), len(code_owner_usernames), 1)
    for idx in range(max_len):
        owner_id = code_owner_ids[idx] if idx < len(code_owner_ids) else "не указан"
        owner_username = code_owner_usernames[idx] if idx < len(code_owner_usernames) else "нет username"
        owner_lines.append(f"👑 @{owner_username} (ID: <code>{owner_id}</code>) — <b>Владелец</b>")
    lines = owner_lines
    for a in admins:
        uname = f"@{a['username']}" if a.get("username") else "нет username"
        lines.append(f"🔹 {uname} (ID: <code>{a['id']}</code>)")
    return "👥 <b>Администраторы:</b>\n\n" + "\n".join(lines)


async def open_admin_panel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer(
        "🔐 <b>Админ-панель</b>\n\nДобро пожаловать!",
        reply_markup=kb_admin_main(),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════
#  📋  FSM States
# ════════════════════════════════════════════════

class S(StatesGroup):
    editing_text    = State()
    editing_photo   = State()
    editing_check_photo = State()
    editing_check_sticker = State()
    editing_check_text = State()
    editing_checker_fields = State()
    editing_sticker = State()
    editing_buttons = State()   # принимаем строки «Название|https://...»
    editing_deal_group_link = State()
    deal_username  = State()
    deal_give      = State()
    deal_receive   = State()
    deal_desc      = State()
    deal_confirm   = State()
    adding_admin    = State()
    removing_admin  = State()


# ════════════════════════════════════════════════
#  🛠  Хелперы отправки раздела
# ════════════════════════════════════════════════

async def send_section(msg: Message, key: str, reply_markup=None):
    """Отправляет раздел: стикер (если есть) → фото/текст → inline-кнопки."""
    sec     = get_section(key)
    text    = sec.get("text", "")
    entities = build_entities(sec.get("entities", []))
    photo   = sec.get("photo")
    sticker = sec.get("sticker")
    buttons = sec.get("buttons", [])
    user    = msg.from_user
    ikb     = reply_markup or build_inline_keyboard(
        buttons,
        user_id=user.id if user else None,
        username=user.username if user else None,
    )

    if sticker:
        await msg.answer_sticker(sticker)

    template_chat_id = sec.get("template_chat_id")
    template_message_id = sec.get("template_message_id")

    if template_chat_id and template_message_id and not photo:
        try:
            await msg.bot.copy_message(
                chat_id=msg.chat.id,
                from_chat_id=template_chat_id,
                message_id=template_message_id,
                reply_markup=ikb,
            )
            return
        except TelegramBadRequest:
            pass

    if photo:
        try:
            if entities:
                await msg.answer_photo(
                    photo=photo,
                    caption=text or None,
                    caption_entities=entities,
                    reply_markup=ikb,
                )
            else:
                await msg.answer_photo(photo=photo, caption=text or None, reply_markup=ikb, parse_mode="HTML")
        except TelegramBadRequest as e:
            if is_bad_photo_error(e):
                update_section_photo(key, None)
                if text:
                    if entities:
                        await msg.answer(text, reply_markup=ikb, entities=entities)
                    else:
                        await msg.answer(format_send_error_fallback(text), reply_markup=ikb, parse_mode="HTML")
                return
            if "can't parse entities" not in str(e):
                raise
            await msg.answer_photo(
                photo=photo,
                caption=format_send_error_fallback(text) or None,
                reply_markup=ikb,
                parse_mode="HTML",
            )
    elif text:
        if entities:
            await msg.answer(text, reply_markup=ikb, entities=entities)
        else:
            try:
                await msg.answer(text, reply_markup=ikb, parse_mode="HTML")
            except TelegramBadRequest as e:
                if "can't parse entities" not in str(e):
                    raise
                await msg.answer(format_send_error_fallback(text), reply_markup=ikb, parse_mode="HTML")


async def show_guarantors_section(msg: Message):
    sec = get_section("guarantors")
    template_chat_id = sec.get("template_chat_id")
    template_message_id = sec.get("template_message_id")
    pages = split_text_and_entities_by_pages(sec.get("text", ""), sec.get("entities", []))
    text, page_entities = pages[0]
    photo = sec.get("photo")
    sticker = sec.get("sticker")
    built_entities = build_entities(page_entities)
    reply_markup = ikb_guarantors(0, len(pages), msg.from_user.id, msg.from_user.username)

    if sticker:
        await msg.answer_sticker(sticker)
    if template_chat_id and template_message_id and not photo:
        try:
            await msg.bot.copy_message(
                chat_id=msg.chat.id,
                from_chat_id=template_chat_id,
                message_id=template_message_id,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest:
            pass
    if photo:
        try:
            if built_entities:
                await msg.answer_photo(
                    photo=photo,
                    caption=text or None,
                    caption_entities=built_entities,
                    reply_markup=reply_markup,
                )
            else:
                await msg.answer_photo(photo=photo, caption=text or None, reply_markup=reply_markup, parse_mode="HTML")
        except TelegramBadRequest as e:
            if is_bad_photo_error(e):
                update_section_photo("guarantors", None)
                if built_entities:
                    await msg.answer(text, reply_markup=reply_markup, entities=built_entities)
                else:
                    await msg.answer(format_send_error_fallback(text), reply_markup=reply_markup, parse_mode="HTML")
                return
            if "can't parse entities" not in str(e):
                raise
            await msg.answer_photo(
                photo=photo,
                caption=format_send_error_fallback(text) or None,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
    elif text:
        if built_entities:
            await msg.answer(text, reply_markup=reply_markup, entities=built_entities)
        else:
            try:
                await msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")
            except TelegramBadRequest as e:
                if "can't parse entities" not in str(e):
                    raise
                await msg.answer(format_send_error_fallback(text), reply_markup=reply_markup, parse_mode="HTML")


async def send_profile_card(
    msg: Message,
    target_user_id: Optional[int],
    target_username: Optional[str],
    *,
    increment_counter: bool,
    use_check_photo: bool = False,
):
    user_key = ensure_user_storage_key(target_user_id, target_username)
    udata = get_user_data_by_key(user_key)
    searches = increment_search_by_key(user_key) if increment_counter else int(udata.get("searches", 0))
    today = datetime.now().strftime("%d.%m.%Y")
    uname = f"@{target_username}" if target_username else "нет username"
    in_base = bool(udata.get("in_base", False))

    sec = get_section("profile")
    sticker = get_check_sticker() if use_check_photo else sec.get("sticker")
    photo = get_check_photo() if use_check_photo else sec.get("photo")
    custom_top = get_check_text().strip() if use_check_photo else sec.get("text", "").strip()
    custom_entities = get_check_entities() if use_check_photo else sec.get("entities", [])
    if sticker:
        await msg.answer_sticker(sticker)

    profile_text = (
        f"👤 Имя: {uname}\n"
        f"🪪 id: [{target_user_id if target_user_id is not None else 'неизвестно'}]\n\n"
        f"⚙️ Проверка в базе данных...\n\n"
        f"🖇 Роль пользователя...\n"
        f"▷ {'Пользователь найден в базе 🔴' if in_base else 'Пользователя нет в базе 🟢'}\n\n"
        f"🔍 Пользователя искали: {searches} раз\n"
        f"🛡 Проверено в @{BOT_USERNAME}\n"
        f"📅 Дата проверки [{today}]"
    )
    if custom_top:
        text, prepared_entities = render_profile_template_text(
            custom_top,
            custom_entities,
            uname,
            str(target_user_id) if target_user_id is not None else "неизвестно",
        )
        if use_check_photo:
            checker_fields = get_checker_fields()
            text, prepared_entities = apply_named_placeholders(
                text,
                prepared_entities,
                {
                    "guarantor_role": checker_fields.get("guarantor_role", ""),
                    "guarantor_channel": checker_fields.get("guarantor_channel", ""),
                    "rating": checker_fields.get("rating", ""),
                    "deal_price": checker_fields.get("deal_price", ""),
                    "proofs": checker_fields.get("proofs", ""),
                    "searches": str(searches),
                    "date": today,
                    "bot_username": f"@{BOT_USERNAME}",
                },
            )
        built_entities = build_entities(prepared_entities)
    else:
        text = profile_text
        built_entities = None

    reply_markup = ikb_profile(target_user_id or 0, target_username)
    if photo:
        try:
            if built_entities:
                await msg.answer_photo(photo=photo, caption=text, caption_entities=built_entities, reply_markup=reply_markup)
            else:
                await msg.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        except TelegramBadRequest as e:
            if is_bad_photo_error(e):
                if use_check_photo:
                    set_check_photo(None)
                else:
                    update_section_photo("profile", None)
                if built_entities:
                    await msg.answer(text, reply_markup=reply_markup, entities=built_entities)
                else:
                    await msg.answer(format_send_error_fallback(text), reply_markup=reply_markup, parse_mode="HTML")
                return
            if "can't parse entities" not in str(e):
                raise
            await msg.answer_photo(
                photo=photo,
                caption=format_send_error_fallback(text),
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        return

    if built_entities:
        await msg.answer(text, reply_markup=reply_markup, entities=built_entities)
    else:
        try:
            await msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "can't parse entities" not in str(e):
                raise
            await msg.answer(format_send_error_fallback(text), reply_markup=reply_markup, parse_mode="HTML")


# ════════════════════════════════════════════════
#  👤  Роутер пользователя
# ════════════════════════════════════════════════

user_router = Router()


@user_router.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer("👋 Добро пожаловать!\n\nВыбери нужный раздел:", reply_markup=kb_main())


@user_router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(commands_text(), reply_markup=kb_main())


@user_router.message(Command("admin"))
async def cmd_admin_entry(msg: Message, state: FSMContext):
    u = msg.from_user
    if not u or not is_admin(u.id, u.username):
        await msg.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await open_admin_panel(msg, state)


@user_router.message(Command("me"))
async def cmd_me(msg: Message):
    await profile_handler(msg)


@user_router.message(Command("info"))
async def cmd_info(msg: Message):
    await send_section(msg, "about")


@user_router.message(Command("sponsors"))
async def cmd_sponsors(msg: Message):
    await send_section(msg, "sponsors")


@user_router.message(Command("garants"))
async def cmd_garants(msg: Message):
    await show_guarantors_section(msg)


@user_router.message(Command("start_deal"))
async def cmd_start_deal(msg: Message, state: FSMContext):
    await start_deal_flow(msg, state)


@user_router.message(Command("admins"))
async def cmd_admins_public(msg: Message):
    await msg.answer(admins_text(), parse_mode="HTML")


@user_router.message(Command("check"))
async def cmd_check(msg: Message):
    target_user_id = None
    target_username = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        replied = msg.reply_to_message.from_user
        target_user_id = replied.id
        target_username = replied.username
    else:
        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) > 1:
            raw = parts[1].strip()
            if raw.isdigit():
                target_user_id = int(raw)
            else:
                target_username = raw.lstrip("@")

    if target_user_id is None and not target_username:
        await msg.answer(
            "⚠️ Проверка на скам\n\n"
            "Отправьте команду ответом на сообщение пользователя или укажите @username / ID.\n\n"
            "Пример:\n"
            "/check @username",
            reply_markup=kb_main(),
        )
        return

    await send_profile_card(
        msg,
        target_user_id,
        target_username,
        increment_counter=True,
        use_check_photo=True,
    )


@user_router.message(F.text == "👁 Мой профиль")
async def profile_handler(msg: Message):
    u = msg.from_user
    await send_profile_card(msg, u.id, u.username, increment_counter=True)


@user_router.message(F.text == "🔄 Провести сделку через гаранта 🔄")
async def start_deal_flow(msg: Message, state: FSMContext):
    date_key = datetime.now().strftime("%Y%m%d")
    if not can_create_deal_today(msg.from_user.id, date_key):
        await msg.answer(
            "⚠️ Лимит на создание: 1 сделка в день.\n\nПопробуйте снова завтра.",
            reply_markup=kb_main(),
        )
        return

    await state.clear()
    await state.set_state(S.deal_username)
    await msg.answer(
        "Введите @username пользователя, которому хотите предложить сделку:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=DEAL_CANCEL_TEXT)]],
            resize_keyboard=True,
        ),
    )


@user_router.message(S.deal_username)
async def deal_get_username(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw == DEAL_CANCEL_TEXT:
        await state.clear()
        await msg.answer("Сделка отменена.", reply_markup=kb_main())
        return

    if not raw:
        await msg.answer("Нужно отправить @username пользователя.")
        return

    if not raw.startswith("@"):
        raw = f"@{raw.lstrip('@')}"

    await state.update_data(deal_username=raw)
    await state.set_state(S.deal_give)
    await msg.answer(
        f"Вы собираетесь провести сделку с {raw}\n\n"
        f"⚠️ Лимит на СОЗДАНИЕ: 1 сделка в день\n\n"
        f"Что вы даёте {raw}?",
        reply_markup=kb_deal_choices(),
    )


@user_router.message(S.deal_give)
async def deal_get_give(msg: Message, state: FSMContext):
    choice = (msg.text or "").strip()
    if choice == DEAL_CANCEL_TEXT:
        await state.clear()
        await msg.answer("Сделка отменена.", reply_markup=kb_main())
        return
    if choice not in DEAL_OPTIONS:
        await msg.answer("Выберите вариант кнопкой ниже.", reply_markup=kb_deal_choices())
        return

    data = await state.get_data()
    username = data["deal_username"]
    await state.update_data(deal_give=choice)
    await state.set_state(S.deal_receive)
    await msg.answer(
        f"Вы собираетесь провести сделку с {username}\n\n"
        f"Вы отдаёте: {choice}\n\n"
        f"Что вы получаете от {username}?",
        reply_markup=kb_deal_choices(),
    )


@user_router.message(S.deal_receive)
async def deal_get_receive(msg: Message, state: FSMContext):
    choice = (msg.text or "").strip()
    if choice == DEAL_CANCEL_TEXT:
        await state.clear()
        await msg.answer("Сделка отменена.", reply_markup=kb_main())
        return
    if choice not in DEAL_OPTIONS:
        await msg.answer("Выберите вариант кнопкой ниже.", reply_markup=kb_deal_choices())
        return

    data = await state.get_data()
    await state.update_data(deal_receive=choice)
    await state.set_state(S.deal_desc)
    await msg.answer(
        f"Вы собираетесь провести сделку с {data['deal_username']}\n\n"
        f"Вы отдаёте: {data['deal_give']}\n"
        f"Вы получаете: {choice}\n\n"
        f"Кратко опишите сумму или условия:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=DEAL_CANCEL_TEXT)]],
            resize_keyboard=True,
        ),
    )


@user_router.message(S.deal_desc)
async def deal_get_desc(msg: Message, state: FSMContext):
    desc = (msg.text or "").strip()
    if desc == DEAL_CANCEL_TEXT:
        await state.clear()
        await msg.answer("Сделка отменена.", reply_markup=kb_main())
        return
    if not desc:
        await msg.answer("Нужно кратко описать условия сделки.")
        return

    data = await state.get_data()
    await state.update_data(deal_desc=desc)
    await state.set_state(S.deal_confirm)
    await msg.answer(
        "Проверьте условия и запустите сделку.\n\n"
        f"Вы отдаёте: {data['deal_give']}\n"
        f"Вы получаете: {data['deal_receive']}\n"
        f"Описание: {desc}\n\n"
        "Выберите действие:",
        reply_markup=kb_deal_confirm(),
    )


@user_router.message(S.deal_confirm)
async def deal_confirm(msg: Message, state: FSMContext):
    choice = (msg.text or "").strip()
    if choice == DEAL_CANCEL_TEXT:
        await state.clear()
        await msg.answer("Сделка отменена.", reply_markup=kb_main())
        return
    if choice != "Начать сделку":
        await msg.answer("Нажмите `Начать сделку` или `Отменить сделку`.", reply_markup=kb_deal_confirm())
        return

    date_key = datetime.now().strftime("%Y%m%d")
    if not can_create_deal_today(msg.from_user.id, date_key):
        await state.clear()
        await msg.answer(
            "⚠️ Лимит на создание: 1 сделка в день.\n\nПопробуйте снова завтра.",
            reply_markup=kb_main(),
        )
        return

    deal_number = create_deal_record(msg.from_user.id, date_key)
    await state.clear()
    await msg.answer(
        f"Сделка №{deal_number} создана.\n"
        "Вступите в группу и ожидайте гаранта.",
        reply_markup=ikb_deal_group(),
    )
    await msg.answer("Главное меню:", reply_markup=kb_main())


@user_router.message(lambda m: m.text in BUTTON_TO_KEY and m.text != "👁 Мой профиль")
async def section_handler(msg: Message):
    if BUTTON_TO_KEY[msg.text] == "guarantors":
        await show_guarantors_section(msg)
        return

    await send_section(msg, BUTTON_TO_KEY[msg.text])


@user_router.callback_query(F.data == "guarantors_page_info")
async def guarantors_page_info(cb: CallbackQuery):
    await cb.answer()


@user_router.callback_query(F.data.startswith("profile_like:"))
async def profile_like(cb: CallbackQuery):
    user_key = cb.data.split(":", 1)[1]
    likes, dislikes = increment_reaction(user_key, "likes")
    rows = list((cb.message.reply_markup.inline_keyboard if cb.message.reply_markup else []))
    if rows:
        rows[0] = [
            InlineKeyboardButton(text=f"👍 [{likes}]", callback_data=f"profile_like:{user_key}"),
            InlineKeyboardButton(text=f"👎 [{dislikes}]", callback_data=f"profile_dislike:{user_key}"),
        ]
        await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer("Лайк учтён")


@user_router.callback_query(F.data.startswith("profile_dislike:"))
async def profile_dislike(cb: CallbackQuery):
    user_key = cb.data.split(":", 1)[1]
    likes, dislikes = increment_reaction(user_key, "dislikes")
    rows = list((cb.message.reply_markup.inline_keyboard if cb.message.reply_markup else []))
    if rows:
        rows[0] = [
            InlineKeyboardButton(text=f"👍 [{likes}]", callback_data=f"profile_like:{user_key}"),
            InlineKeyboardButton(text=f"👎 [{dislikes}]", callback_data=f"profile_dislike:{user_key}"),
        ]
        await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer("Дизлайк учтён")


@user_router.callback_query(F.data.startswith("guarantors_page_"))
async def guarantors_page_change(cb: CallbackQuery):
    sec = get_section("guarantors")
    pages = split_text_and_entities_by_pages(sec.get("text", ""), sec.get("entities", []))
    try:
        page = int(cb.data.rsplit("_", 1)[1])
    except ValueError:
        page = 0
    page = max(0, min(page, len(pages) - 1))

    text, page_entities = pages[page]
    built_entities = build_entities(page_entities)
    reply_markup = ikb_guarantors(page, len(pages), cb.from_user.id, cb.from_user.username)

    try:
        if sec.get("photo"):
            if built_entities:
                await cb.message.edit_caption(
                    caption=text or None,
                    caption_entities=built_entities,
                    reply_markup=reply_markup,
                )
            else:
                await cb.message.edit_caption(caption=text or None, reply_markup=reply_markup, parse_mode="HTML")
        else:
            if built_entities:
                await cb.message.edit_text(text, reply_markup=reply_markup, entities=built_entities)
            else:
                await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            if "can't parse entities" in str(e):
                if sec.get("photo"):
                    await cb.message.edit_caption(
                        caption=format_send_error_fallback(text) or None,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
                else:
                    await cb.message.edit_text(
                        format_send_error_fallback(text),
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )
            else:
                raise
    await cb.answer()


# ════════════════════════════════════════════════
#  🔐  Роутер администратора
# ════════════════════════════════════════════════

admin_router = Router()
admin_router.message.filter(IsAdmin())
admin_router.callback_query.filter(IsAdminCB())


@admin_router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    await open_admin_panel(msg, state)


@admin_router.message(F.text == "✏️ Редактировать разделы")
async def admin_edit_sections(msg: Message):
    await msg.answer("Выбери раздел:", reply_markup=ikb_sections())


@admin_router.message(F.text == "👥 Управление админами")
async def admin_manage(msg: Message):
    await msg.answer("👥 <b>Управление администраторами</b>",
                     reply_markup=ikb_admins_manage(), parse_mode="HTML")


@admin_router.message(F.text == "🔗 Ссылка группы сделок")
async def admin_deal_group_link(msg: Message, state: FSMContext):
    await state.set_state(S.editing_deal_group_link)
    await msg.answer(
        "Отправь новую ссылку на группу для сделок.\n\n"
        f"Текущая ссылка:\n{get_deal_group_link()}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Выйти из админ-панели")]],
            resize_keyboard=True,
        ),
    )


@admin_router.message(F.text == "🛡 Чекер")
async def admin_checker(msg: Message):
    await msg.answer("Настройки чекера /check:", reply_markup=ikb_checker_manage())


@admin_router.message(F.text == "🖼 Фото /check")
async def admin_check_photo(msg: Message, state: FSMContext):
    await state.set_state(S.editing_check_photo)
    current = "есть" if get_check_photo() else "нет"
    await msg.answer(
        "Отправь новое фото для карточки `/check`.\n\n"
        f"Сейчас фото: {current}\n"
        "Чтобы удалить фото, отправь слово: удалить",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Выйти из админ-панели")]],
            resize_keyboard=True,
        ),
    )


@admin_router.message(F.text == "✏️ Текст /check")
async def admin_check_text(msg: Message, state: FSMContext):
    await state.set_state(S.editing_check_text)
    current = get_check_text().strip()
    preview = current if current else "(сейчас используется стандартный текст проверки)"
    await msg.answer(
        "Отправь новый текст для `/check`.\n\n"
        "В тексте можно использовать:\n"
        "{username}\n"
        "{user_id}\n\n"
        f"Текущий текст:\n{preview}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Выйти из админ-панели")]],
            resize_keyboard=True,
        ),
    )


@admin_router.callback_query(F.data == "checker_text")
async def checker_text_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await admin_check_text(cb.message, state)


@admin_router.callback_query(F.data == "checker_photo")
async def checker_photo_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await admin_check_photo(cb.message, state)


@admin_router.callback_query(F.data == "checker_sticker")
async def checker_sticker_cb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(S.editing_check_sticker)
    current = "есть" if get_check_sticker() else "нет"
    await cb.message.answer(
        "Отправь новый premium-стикер или обычный стикер для `/check`.\n\n"
        f"Сейчас стикер: {current}\n"
        "Чтобы удалить стикер, отправь слово: удалить",
    )
    await cb.answer()


@admin_router.callback_query(F.data == "checker_fields")
async def checker_fields_cb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(S.editing_checker_fields)
    fields = get_checker_fields()
    await cb.message.answer(
        "Отправь данные гаранта для /check, каждая строка в формате:\n"
        "<code>ключ: значение</code>\n\n"
        "Доступные ключи:\n"
        "<code>guarantor_role</code>\n"
        "<code>guarantor_channel</code>\n"
        "<code>rating</code>\n"
        "<code>deal_price</code>\n"
        "<code>proofs</code>\n\n"
        "Пример:\n"
        "<code>guarantor_role: Элитный гарант [🇷🇺/🇺🇦]\n"
        "guarantor_channel: @liviskayaa_tgk\n"
        "rating: 5.0/5 (0) ★★★★★\n"
        "deal_price: 100₽\n"
        "proofs: 800+</code>\n\n"
        f"Текущие данные:\n"
        f"<code>guarantor_role: {fields.get('guarantor_role', '')}\n"
        f"guarantor_channel: {fields.get('guarantor_channel', '')}\n"
        f"rating: {fields.get('rating', '')}\n"
        f"deal_price: {fields.get('deal_price', '')}\n"
        f"proofs: {fields.get('proofs', '')}</code>",
        parse_mode="HTML",
    )
    await cb.answer()


@admin_router.message(F.text == "🔙 Выйти из админ-панели")
async def admin_exit(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Вышел из админ-панели.", reply_markup=kb_main())


@admin_router.message(S.editing_deal_group_link)
async def save_deal_group_link(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw == "🔙 Выйти из админ-панели":
        await state.clear()
        await msg.answer("Вышел из настройки ссылки.", reply_markup=kb_admin_main())
        return
    if not raw.startswith("http"):
        await msg.answer("Ссылка должна начинаться с http или https.")
        return
    set_deal_group_link(raw)
    await state.clear()
    await msg.answer("✅ Ссылка на группу сделок обновлена.", reply_markup=kb_admin_main())


@admin_router.message(S.editing_check_photo, F.photo)
async def save_check_photo(msg: Message, state: FSMContext):
    set_check_photo(msg.photo[-1].file_id)
    await state.clear()
    await msg.answer("✅ Фото для /check обновлено.", reply_markup=kb_admin_main())


@admin_router.message(S.editing_check_photo)
async def save_check_photo_text(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip().lower()
    if raw == "🔙 выйти из админ-панели".lower():
        await state.clear()
        await msg.answer("Вышел из настройки фото /check.", reply_markup=kb_admin_main())
        return
    if raw == "удалить":
        set_check_photo(None)
        await state.clear()
        await msg.answer("✅ Фото для /check удалено.", reply_markup=kb_admin_main())
        return
    await msg.answer("Нужно отправить фото, `удалить` или `🔙 Выйти из админ-панели`.", parse_mode="Markdown")


@admin_router.message(S.editing_check_sticker, F.sticker)
async def save_check_sticker_handler(msg: Message, state: FSMContext):
    set_check_sticker(msg.sticker.file_id)
    await state.clear()
    await msg.answer("✅ Стикер для /check обновлён.", reply_markup=kb_admin_main())


@admin_router.message(S.editing_check_sticker)
async def save_check_sticker_text_handler(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip().lower()
    if raw == "🔙 выйти из админ-панели".lower():
        await state.clear()
        await msg.answer("Вышел из настройки стикера /check.", reply_markup=kb_admin_main())
        return
    if raw == "удалить":
        set_check_sticker(None)
        await state.clear()
        await msg.answer("✅ Стикер для /check удалён.", reply_markup=kb_admin_main())
        return
    await msg.answer("Нужно отправить стикер, `удалить` или `🔙 Выйти из админ-панели`.", parse_mode="Markdown")


@admin_router.message(S.editing_check_text)
async def save_check_text_handler(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw.lower() == "🔙 выйти из админ-панели".lower():
        await state.clear()
        await msg.answer("Вышел из настройки текста /check.", reply_markup=kb_admin_main())
        return
    if raw.lower() == "удалить":
        set_check_text("", [])
        await state.clear()
        await msg.answer("✅ Текст /check сброшен на стандартный.", reply_markup=kb_admin_main())
        return
    set_check_text(normalize_admin_text_input(msg), normalize_admin_entities_input(msg))
    await state.clear()
    await msg.answer("✅ Текст /check обновлён.", reply_markup=kb_admin_main())


@admin_router.message(S.editing_checker_fields)
async def save_checker_fields_handler(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    if raw.lower() == "🔙 выйти из админ-панели".lower():
        await state.clear()
        await msg.answer("Вышел из настройки данных гаранта.", reply_markup=kb_admin_main())
        return

    allowed = {"guarantor_role", "guarantor_channel", "rating", "deal_price", "proofs"}
    fields = get_checker_fields()
    errors = []
    for i, line in enumerate(raw.splitlines(), 1):
        if ":" not in line:
            errors.append(f"Строка {i}: нужен формат ключ: значение")
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key not in allowed:
            errors.append(f"Строка {i}: неизвестный ключ {key}")
            continue
        fields[key] = value

    if errors:
        await msg.answer("❌ Ошибки:\n" + "\n".join(errors))
        return

    set_checker_fields(fields)
    await state.clear()
    await msg.answer("✅ Данные гаранта для /check обновлены.", reply_markup=kb_admin_main())


# ── Выбор раздела ─────────────────────────────────

def _section_info_text(key: str) -> str:
    sec     = get_section(key)
    text    = html.escape(sec.get("text", "") or "(динамический)")
    photo   = "✅ есть" if sec.get("photo")   else "❌ нет"
    sticker = "✅ есть" if sec.get("sticker") else "❌ нет"
    btns    = sec.get("buttons", [])
    btns_s  = (
        "\n".join(f"  • [ряд {b.get('row', i)}] {b['label']} → {b['url']}" for i, b in enumerate(btns, 1))
        if btns else "❌ нет"
    )
    return (
        f"📄 <b>Текст:</b>\n{text}\n\n"
        f"🖼 <b>Фото:</b> {photo}\n"
        f"🎭 <b>Стикер:</b> {sticker}\n"
        f"🔗 <b>Кнопки-ссылки:</b>\n{btns_s}"
    )


@admin_router.callback_query(F.data.startswith("edit_"))
async def cb_select_section(cb: CallbackQuery):
    key = cb.data[5:]
    await cb.message.edit_text(
        _section_info_text(key),
        reply_markup=ikb_section_actions(key),
        parse_mode="HTML",
    )
    await cb.answer()


@admin_router.callback_query(F.data == "back_to_sections")
async def cb_back(cb: CallbackQuery):
    await cb.message.edit_text("Выбери раздел:", reply_markup=ikb_sections())
    await cb.answer()


# ── Изменить текст ────────────────────────────────

@admin_router.callback_query(F.data.startswith("set_text_"))
async def cb_ask_text(cb: CallbackQuery, state: FSMContext):
    key = cb.data[9:]
    await state.set_state(S.editing_text)
    await state.update_data(section_key=key)
    await cb.message.answer(
        "✏️ Отправь новый текст одним сообщением.\n\n"
        "Пиши текст как обычное сообщение в Telegram.\n"
        "Можно использовать:\n"
        "• обычные emoji\n"
        "• Premium emoji\n"
        "• жирный, курсив, подчёркивание через встроенное оформление Telegram\n"
        "• ссылки, если вставляешь их в текст\n\n"
        "Premium emoji будут сохранены как в оригинальном сообщении.\n"
        "Лучше не отправлять HTML-теги вручную, если используешь Premium emoji."
    )
    await cb.answer()


@admin_router.message(S.editing_text)
async def save_text(msg: Message, state: FSMContext):
    data = await state.get_data()
    raw_text = normalize_admin_text_input(msg)
    raw_entities = normalize_admin_entities_input(msg)
    if msg.chat and msg.message_id:
        update_section_template(
            data["section_key"],
            msg.chat.id,
            msg.message_id,
            raw_text,
            raw_entities,
        )
    else:
        update_section_text(data["section_key"], raw_text, raw_entities)
    await state.clear()
    await msg.answer("✅ Текст обновлён!", reply_markup=kb_admin_main())


# ── Изменить фото ─────────────────────────────────

@admin_router.callback_query(F.data.startswith("set_photo_"))
async def cb_ask_photo(cb: CallbackQuery, state: FSMContext):
    key = cb.data[10:]
    await state.set_state(S.editing_photo)
    await state.update_data(section_key=key)
    await cb.message.answer("🖼 Отправь фото для раздела:")
    await cb.answer()


@admin_router.message(S.editing_photo, F.photo)
async def save_photo(msg: Message, state: FSMContext):
    data = await state.get_data()
    update_section_photo(data["section_key"], msg.photo[-1].file_id)
    await state.clear()
    await msg.answer("✅ Фото обновлено!", reply_markup=kb_admin_main())


@admin_router.message(S.editing_photo)
async def wrong_photo(msg: Message):
    await msg.answer("❌ Нужно отправить именно фото.")


# ── Удалить фото ──────────────────────────────────

@admin_router.callback_query(F.data.startswith("del_photo_"))
async def cb_del_photo(cb: CallbackQuery):
    key = cb.data[10:]
    update_section_photo(key, None)
    await cb.message.edit_text(
        _section_info_text(key),
        reply_markup=ikb_section_actions(key),
        parse_mode="HTML",
    )
    await cb.answer("🗑 Фото удалено!", show_alert=True)


# ── Добавить стикер ───────────────────────────────

@admin_router.callback_query(F.data.startswith("set_sticker_"))
async def cb_ask_sticker(cb: CallbackQuery, state: FSMContext):
    key = cb.data[12:]
    await state.set_state(S.editing_sticker)
    await state.update_data(section_key=key)
    await cb.message.answer(
        "🎭 Отправь стикер (обычный или Telegram Premium) для этого раздела.\n\n"
        "Стикер будет отправляться перед основным сообщением."
    )
    await cb.answer()


@admin_router.message(S.editing_sticker, F.sticker)
async def save_sticker(msg: Message, state: FSMContext):
    data = await state.get_data()
    update_section_sticker(data["section_key"], msg.sticker.file_id)
    await state.clear()
    await msg.answer("✅ Стикер сохранён!", reply_markup=kb_admin_main())


@admin_router.message(S.editing_sticker)
async def wrong_sticker(msg: Message):
    await msg.answer("❌ Нужно отправить именно стикер.")


# ── Удалить стикер ────────────────────────────────

@admin_router.callback_query(F.data.startswith("del_sticker_"))
async def cb_del_sticker(cb: CallbackQuery):
    key = cb.data[12:]
    update_section_sticker(key, None)
    await cb.message.edit_text(
        _section_info_text(key),
        reply_markup=ikb_section_actions(key),
        parse_mode="HTML",
    )
    await cb.answer("🗑 Стикер удалён!", show_alert=True)


# ── Кнопки-ссылки ─────────────────────────────────

@admin_router.callback_query(F.data.startswith("set_buttons_"))
async def cb_ask_buttons(cb: CallbackQuery, state: FSMContext):
    key = cb.data[12:]
    await state.set_state(S.editing_buttons)
    await state.update_data(section_key=key)
    await cb.message.answer(
        "🔗 <b>Настройка кнопок</b>\n\n"
        "Каждую кнопку отправляй с новой строки в таком виде:\n"
        "<code>Текст кнопки|ссылка|ряд</code>\n\n"
        "Что означает:\n"
        "<code>Текст кнопки</code> — что будет написано на кнопке\n"
        "<code>ссылка</code> — куда ведёт кнопка\n"
        "<code>ряд</code> — номер строки, в которой будет кнопка\n\n"
        "Если у двух кнопок одинаковый ряд, они будут стоять рядом.\n"
        "Если ряд не указать, кнопка будет на отдельной строке.\n\n"
        "Спец-ссылки для профиля:\n"
        f"<code>{SPECIAL_URL_SELF_PROFILE}</code> — открыть профиль текущего пользователя\n"
        f"<code>{SPECIAL_URL_REPORT}</code> — кнопка жалобы\n"
        f"<code>{SPECIAL_URL_PROJECTS}</code> — другие проекты\n\n"
        "Пример:\n"
        "<code>❓ Кто такой гарант|https://t.me/example1|2\n"
        "🔎 Поиск гарантов|https://t.me/example2|2\n"
        f"📁 Другие наши проекты|{SPECIAL_URL_PROJECTS}|3</code>\n\n"
        "Чтобы удалить все кнопки раздела, отправь: <code>удалить</code>",
        parse_mode="HTML",
    )
    await cb.answer()


@admin_router.message(S.editing_buttons)
async def save_buttons(msg: Message, state: FSMContext):
    data = await state.get_data()
    key  = data["section_key"]

    if msg.text.strip().lower() == "удалить":
        update_section_buttons(key, [])
        await state.clear()
        await msg.answer("✅ Кнопки удалены.", reply_markup=kb_admin_main())
        return

    buttons = []
    errors  = []
    for i, line in enumerate(msg.text.strip().splitlines(), 1):
        if "|" not in line:
            errors.append(f"Строка {i}: нет символа |")
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            errors.append(f"Строка {i}: нужен формат Название|ссылка|ряд")
            continue

        label, url = parts[0], parts[1]
        row = i
        if len(parts) >= 3 and parts[2]:
            if not parts[2].isdigit():
                errors.append(f"Строка {i}: ряд должен быть числом")
                continue
            row = int(parts[2])

        if not (url.startswith("http") or url.startswith("tg://") or url.startswith("__")):
            errors.append(f"Строка {i}: ссылка должна начинаться с http, tg:// или __")
            continue
        buttons.append({"label": label, "url": url, "row": row})

    if errors:
        await msg.answer("❌ Ошибки:\n" + "\n".join(errors) + "\n\nИсправь и отправь снова.")
        return

    update_section_buttons(key, buttons)
    await state.clear()
    await msg.answer(
        f"✅ Сохранено {len(buttons)} кнопок!",
        reply_markup=kb_admin_main(),
    )


# ── Список админов ────────────────────────────────

@admin_router.callback_query(F.data == "admin_list")
async def cb_admin_list(cb: CallbackQuery):
    admins = _load_admins()
    code_owner_ids = sorted(get_code_owner_ids())
    code_owner_usernames = sorted(get_code_owner_usernames())
    lines = []
    max_len = max(len(code_owner_ids), len(code_owner_usernames), 1)
    for idx in range(max_len):
        owner_id = code_owner_ids[idx] if idx < len(code_owner_ids) else "не указан"
        owner_username = code_owner_usernames[idx] if idx < len(code_owner_usernames) else "нет username"
        lines.append(f"👑 @{owner_username} (ID: <code>{owner_id}</code>) — <b>Владелец</b>")
    for a in admins:
        uname = f"@{a['username']}" if a.get("username") else "нет username"
        lines.append(f"🔹 {uname} (ID: <code>{a['id']}</code>)")
    await cb.message.answer("👥 <b>Администраторы:</b>\n\n" + "\n".join(lines), parse_mode="HTML")
    await cb.answer()


# ── Добавить админа ───────────────────────────────

@admin_router.callback_query(F.data == "admin_add")
async def cb_admin_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(S.adding_admin)
    await cb.message.answer("➕ Отправь <b>числовой ID</b> или <b>@username</b> нового админа:",
                             parse_mode="HTML")
    await cb.answer()


@admin_router.message(S.adding_admin)
async def process_add(msg: Message, state: FSMContext):
    raw = msg.text.strip().lstrip("@")
    await state.clear()
    if raw.isdigit():
        ok   = add_admin(int(raw))
        text = "✅ Администратор добавлен!" if ok else "⚠️ Уже есть в списке."
    else:
        add_admin(0, raw)
        text = (f"✅ @{raw} добавлен как админ.\n"
                "⚠️ ID не известен — права активируются, когда он напишет боту.")
    await msg.answer(text, reply_markup=kb_admin_main())


# ── Удалить админа ────────────────────────────────

@admin_router.callback_query(F.data == "admin_remove")
async def cb_admin_remove(cb: CallbackQuery, state: FSMContext):
    await state.set_state(S.removing_admin)
    await cb.message.answer("➖ Отправь <b>числовой ID</b> или <b>@username</b> админа для удаления:",
                             parse_mode="HTML")
    await cb.answer()


@admin_router.message(S.removing_admin)
async def process_remove(msg: Message, state: FSMContext):
    raw = msg.text.strip().lstrip("@")
    await state.clear()
    if raw.isdigit():
        uid = int(raw)
        if uid in get_code_owner_ids():
            await msg.answer("❌ Нельзя удалить владельца.", reply_markup=kb_admin_main())
            return
        ok = remove_admin_by_id(uid)
    else:
        if raw.lower() in get_code_owner_usernames():
            await msg.answer("❌ Нельзя удалить владельца.", reply_markup=kb_admin_main())
            return
        ok = remove_admin_by_username(raw)
    text = "✅ Администратор удалён." if ok else "❌ Такой администратор не найден."
    await msg.answer(text, reply_markup=kb_admin_main())


# ════════════════════════════════════════════════
#  🚀  Запуск
# ════════════════════════════════════════════════

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)
    logging.info("✅ Бот запущен")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
