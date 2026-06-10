from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(is_admin: bool = False):
    buttons = [
        [KeyboardButton(text="🧸 Профиль")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="💬 Чат команды")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

admin_panel_buttons = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📋 Список участников", callback_data="admin_list_users")],
    [InlineKeyboardButton(text="💰 Начислить профит", callback_data="admin_add_profit")],
    [InlineKeyboardButton(text="🔄 Изменить роль", callback_data="admin_change_role")],
    [InlineKeyboardButton(text="📈 Обновить статы", callback_data="admin_update_stats")],
    [InlineKeyboardButton(text="🎬 Установить GIF", callback_data="admin_set_welcome_gif")],
    [InlineKeyboardButton(text="🔗 Ссылка на чат", callback_data="admin_set_chat_link")],
    [InlineKeyboardButton(text="📨 Канал заявок", callback_data="admin_set_app_channel")],
    [InlineKeyboardButton(text="📢 Канал логов", callback_data="admin_set_log_channel")],
    [InlineKeyboardButton(text="🎭 Эмодзи", callback_data="admin_show_emoji_help")],
    [InlineKeyboardButton(text="🔍 Настройки", callback_data="admin_show_settings")],
    [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
])

def approve_buttons(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")]
    ])

def edit_user_buttons(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Изменить роль", callback_data=f"edit_role_{user_id}")],
        [InlineKeyboardButton(text="💸 Начислить профит", callback_data=f"edit_profit_{user_id}")],
        [InlineKeyboardButton(text="📈 Изменить recruited_streamers", callback_data=f"edit_recruited_{user_id}")],
        [InlineKeyboardButton(text="🎥 Изменить streams_count", callback_data=f"edit_streams_{user_id}")],
        [InlineKeyboardButton(text="✏️ Изменить display_name", callback_data=f"edit_displayname_{user_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить участника", callback_data=f"delete_user_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_users")]
    ])

def pagination_buttons(page: int, total_pages: int):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"list_page_{page-1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"list_page_{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

def apply_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Подать заявку", callback_data="start_apply")]
    ])