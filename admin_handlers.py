import asyncio
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_ID
from db import *
from keyboards import pagination_buttons, edit_user_buttons
from states import (
    AdminAddProfit, AdminChangeRole, AdminUpdateStats,
    AdminSetChatLink, AdminBroadcast, AdminEditDisplayName,
    SetChannel, ProfitMedia
)
from emoji_config import format_emoji

router = Router()

# ---------- Список участников (пагинация) ----------
async def list_users_page(message_or_callback, page: int = 0, edit: bool = False):
    users = await get_all_users(only_approved=True)
    if not users:
        text = "Нет участников."
        if edit:
            await message_or_callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        else:
            await message_or_callback.answer(text, parse_mode=ParseMode.HTML)
        return
    per_page = 5
    total_pages = (len(users) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]
    text = f"{format_emoji('admin_list')} Список участников:\n\n"
    for u in page_users:
        name = u.get('display_name') or u.get('username', str(u['user_id']))
        text += f"• {name} (@{u['username']}) — {u['role']}\n"
    markup = pagination_buttons(page, total_pages)
    if edit:
        await message_or_callback.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await message_or_callback.message.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data.startswith("list_page_"))
async def paginate_users(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    await list_users_page(callback, page, edit=True)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_list_users")
async def admin_list_users(callback: CallbackQuery):
    await list_users_page(callback, 0, edit=False)
    await callback.answer()

# ---------- Редактирование участника ----------
@router.callback_query(lambda c: c.data.startswith("edit_role_"))
async def edit_role_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminChangeRole.role)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="стримерша", callback_data="role_streamer")],
        [InlineKeyboardButton(text="трафер", callback_data="role_traffer")],
        [InlineKeyboardButton(text="модератор", callback_data="role_moder")],
        [InlineKeyboardButton(text="новичок", callback_data="role_newbie")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin_close")]
    ])
    await callback.message.edit_text("Выбери новую роль:", reply_markup=markup, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("role_"))
async def change_role(callback: CallbackQuery, state: FSMContext):
    role_map = {
        "streamer": "стримерша",
        "traffer": "трафер",
        "moder": "модератор",
        "newbie": "новичок"
    }
    role_key = callback.data.split("_")[1]
    role = role_map.get(role_key, "новичок")
    data = await state.get_data()
    user_id = data['user_id']
    await update_user(user_id, role=role)
    await callback.message.edit_text(f"Роль изменена на {role}.", parse_mode=ParseMode.HTML)
    await state.clear()
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("edit_profit_"))
async def edit_profit_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id)
    await state.set_state(ProfitMedia.amount)
    await callback.message.edit_text(f"{format_emoji('admin_profit')} Введи сумму профита для начисления (в рублях):", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(ProfitMedia.amount)
async def process_profit_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи число.", parse_mode=ParseMode.HTML)
        return
    amount = int(message.text)
    await state.update_data(amount=amount)
    await state.set_state(ProfitMedia.media_type)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Только текст", callback_data="profit_media_text")],
        [InlineKeyboardButton(text="🖼️ Фото", callback_data="profit_media_photo")],
        [InlineKeyboardButton(text="🎬 Гифка", callback_data="profit_media_gif")],
        [InlineKeyboardButton(text="🎥 Видео", callback_data="profit_media_video")],
        [InlineKeyboardButton(text="🚫 Без уведомления", callback_data="profit_media_skip")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_close")]
    ])
    await message.answer("Что отправить пользователю вместе с начислением?", reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data.startswith("profit_media_"))
async def profit_media_choice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    choice = callback.data.split("_")[2]  # text, photo, gif, video, skip
    if choice == "skip":
        await finalize_profit(callback, state, bot)
        return
    await state.update_data(media_type=choice)
    if choice == "text":
        await state.set_state(ProfitMedia.caption)
        await callback.message.edit_text("✏️ Введи текст сообщения для пользователя (можно с HTML и эмодзи):", parse_mode=ParseMode.HTML)
    else:
        await state.set_state(ProfitMedia.file_id)
        await callback.message.edit_text(f"📤 Отправь {'фото' if choice == 'photo' else 'гифку' if choice == 'gif' else 'видео'} (файлом или пересылкой).\nПосле отправки я спрошу подпись.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(ProfitMedia.caption)
async def profit_caption(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(caption=message.text or "")
    await finalize_profit(message, state, bot)

@router.message(ProfitMedia.file_id, F.photo | F.animation | F.video)
async def profit_file_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    media_type = data.get("media_type")
    file_id = None
    if media_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    elif media_type == "gif" and message.animation:
        file_id = message.animation.file_id
    elif media_type == "video" and message.video:
        file_id = message.video.file_id
    else:
        await message.answer("❌ Отправь правильный тип медиа.", parse_mode=ParseMode.HTML)
        return
    await state.update_data(file_id=file_id)
    await state.set_state(ProfitMedia.caption)
    await message.answer("✏️ Теперь введи подпись к медиа (можно с HTML и эмодзи):", parse_mode=ParseMode.HTML)

async def finalize_profit(event, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = data['user_id']
    amount = data['amount']
    media_type = data.get('media_type')
    caption = data.get('caption', '')
    file_id = data.get('file_id')
    await add_profit(user_id, amount, "manual", ADMIN_ID)
    user = await get_user(user_id)
    display = user.get('display_name') or user.get('username', str(user_id))
    new_profit = user['profit'] + amount
    admin_text = f"{format_emoji('profit')} Начислено {amount} руб. пользователю @{user['username']} ({display}). Новый профит: {new_profit} руб."
    user_text = f"{format_emoji('profit')} <b>Тебе начислено {amount} руб. на счёт CashFlow Team!</b>\n💰 Новый профит: {new_profit} руб."
    if caption:
        user_text += f"\n\n{caption}"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(admin_text, parse_mode=ParseMode.HTML)
        await event.answer()
    else:
        await event.answer(admin_text, parse_mode=ParseMode.HTML)
    log_channel = await get_setting("log_channel_id")
    if log_channel and log_channel.isdigit():
        try:
            await bot.send_message(int(log_channel), admin_text, parse_mode=ParseMode.HTML)
        except:
            pass
    if user.get('notification_settings', True):
        try:
            if media_type == "skip":
                await bot.send_message(user_id, user_text, parse_mode=ParseMode.HTML)
            elif media_type == "text":
                await bot.send_message(user_id, user_text, parse_mode=ParseMode.HTML)
            elif media_type == "photo" and file_id:
                await bot.send_photo(user_id, file_id, caption=user_text, parse_mode=ParseMode.HTML)
            elif media_type == "gif" and file_id:
                await bot.send_animation(user_id, file_id, caption=user_text, parse_mode=ParseMode.HTML)
            elif media_type == "video" and file_id:
                await bot.send_video(user_id, file_id, caption=user_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Не удалось отправить уведомление: {e}")
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("edit_recruited_"))
async def edit_recruited_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id, stat_type="recruited")
    await state.set_state(AdminUpdateStats.value)
    await callback.message.edit_text("📊 Введи новое значение recruited_streamers:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("edit_streams_"))
async def edit_streams_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id, stat_type="streams")
    await state.set_state(AdminUpdateStats.value)
    await callback.message.edit_text("🎥 Введи новое значение streams_count:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(AdminUpdateStats.value)
async def update_stat_value(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи число.", parse_mode=ParseMode.HTML)
        return
    value = int(message.text)
    data = await state.get_data()
    user_id = data['user_id']
    stat_type = data['stat_type']
    if stat_type == "recruited":
        await update_user(user_id, recruited_streamers=value)
        await message.answer(f"✅ recruited_streamers изменено на {value}.", parse_mode=ParseMode.HTML)
    else:
        await update_user(user_id, streams_count=value)
        await message.answer(f"✅ streams_count изменено на {value}.", parse_mode=ParseMode.HTML)
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("edit_displayname_"))
async def edit_displayname_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminEditDisplayName.name)
    await callback.message.edit_text("✏️ Введи новое отображаемое имя:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(AdminEditDisplayName.name)
async def set_display_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    data = await state.get_data()
    user_id = data['user_id']
    await update_user(user_id, display_name=new_name)
    await message.answer(f"✅ display_name изменён на {new_name}.", parse_mode=ParseMode.HTML)
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("delete_user_"))
async def delete_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await update_user(user_id, approved=0)
    await callback.message.edit_text(f"🗑️ Пользователь {user_id} удалён.", parse_mode=ParseMode.HTML)
    await callback.answer()

# ---------- Общие админ-меню ----------
@router.callback_query(lambda c: c.data == "admin_add_profit")
async def admin_add_profit_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfitMedia.amount)
    await callback.message.answer("💰 Введи ID пользователя для начисления профита:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(ProfitMedia.amount)
async def admin_add_profit_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи числовой ID.", parse_mode=ParseMode.HTML)
        return
    user_id = int(message.text)
    user = await get_user(user_id)
    if not user or not user.get('approved'):
        await message.answer("❌ Пользователь не найден или не одобрен.", parse_mode=ParseMode.HTML)
        return
    await state.update_data(user_id=user_id)
    await state.set_state(ProfitMedia.amount)
    await message.answer("💰 Введи сумму профита (в рублях):", parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "admin_change_role")
async def admin_change_role_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminChangeRole.user_id)
    await callback.message.answer("🔄 Введи ID пользователя для смены роли:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(AdminChangeRole.user_id)
async def admin_change_role_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи числовой ID.", parse_mode=ParseMode.HTML)
        return
    user_id = int(message.text)
    user = await get_user(user_id)
    if not user or not user.get('approved'):
        await message.answer("❌ Пользователь не найден.", parse_mode=ParseMode.HTML)
        return
    await state.update_data(user_id=user_id)
    await state.set_state(AdminChangeRole.role)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="стримерша", callback_data="role_streamer")],
        [InlineKeyboardButton(text="трафер", callback_data="role_traffer")],
        [InlineKeyboardButton(text="модератор", callback_data="role_moder")],
        [InlineKeyboardButton(text="новичок", callback_data="role_newbie")]
    ])
    await message.answer("Выбери новую роль:", reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "admin_update_stats")
async def admin_update_stats_menu(callback: CallbackQuery):
    await callback.message.answer("📈 Используй список участников для изменения статов.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_set_welcome_gif")
async def set_welcome_gif(callback: CallbackQuery):
    await callback.message.answer("🎬 Отправь гифку (GIF или MPEG4) ФАЙЛОМ.\nПросто перешли существующую гифку или загрузи новую.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(F.animation | F.document)
async def save_welcome_gif(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    file_id = None
    if message.animation:
        file_id = message.animation.file_id
    elif message.document and message.document.mime_type == "image/gif":
        file_id = message.document.file_id
    if file_id:
        await set_setting("welcome_gif_file_id", file_id)
        await message.answer("✅ Гифка сохранена! Теперь она будет отправляться новым участникам.", parse_mode=ParseMode.HTML)
    else:
        await message.answer("❌ Это не GIF-файл. Отправь именно гифку.", parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "admin_set_chat_link")
async def set_chat_link_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSetChatLink.link)
    await callback.message.answer("🔗 Введи ссылку-приглашение в чат команды:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(AdminSetChatLink.link)
async def set_chat_link_process(message: Message, state: FSMContext):
    link = message.text.strip()
    await set_setting("chat_link", link)
    await message.answer("✅ Ссылка сохранена.", parse_mode=ParseMode.HTML)
    await state.clear()

# ---------- Настройка каналов ----------
@router.callback_query(lambda c: c.data == "admin_set_app_channel")
async def start_set_app_channel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SetChannel.channel_type)
    await state.update_data(channel_type="app")
    await callback.message.answer("📢 Перешли ЛЮБОЕ сообщение из того канала, куда будут дублироваться заявки.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_set_log_channel")
async def start_set_log_channel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SetChannel.channel_type)
    await state.update_data(channel_type="log")
    await callback.message.answer("📢 Перешли ЛЮБОЕ сообщение из того канала, куда будут приходить логи о начислениях.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(SetChannel.channel_type, F.forward_from_chat)
async def save_channel_forward(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    channel_type = data.get("channel_type")
    chat_id = message.forward_from_chat.id
    try:
        await bot.send_message(chat_id, "✅ Бот успешно подключён к этому каналу! (тестовое сообщение)", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка: бот не может писать в этот канал. Убедитесь, что бот добавлен в канал как администратор. Ошибка: {e}", parse_mode=ParseMode.HTML)
        await state.clear()
        return
    if channel_type == "app":
        await set_setting("application_channel_id", str(chat_id))
        await message.answer(f"✅ Канал для заявок установлен: {chat_id}", parse_mode=ParseMode.HTML)
    elif channel_type == "log":
        await set_setting("log_channel_id", str(chat_id))
        await message.answer(f"✅ Канал для логов установлен: {chat_id}", parse_mode=ParseMode.HTML)
    await state.clear()

# ---------- Рассылка ----------
@router.callback_query(lambda c: c.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcast.message)
    await callback.message.answer("📢 Введи текст сообщения для рассылки (можно с HTML и эмодзи):", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(AdminBroadcast.message)
async def broadcast_message(message: Message, state: FSMContext):
    await state.update_data(message=message.text)
    await state.set_state(AdminBroadcast.confirm)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_close")]
    ])
    await message.answer(f"Подтверди рассылку:\n\n{message.text}", reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data['message']
    users = await get_all_users(only_approved=True)
    count = 0
    for u in users:
        try:
            await bot.send_message(u['user_id'], f"📢 <b>Рассылка от администрации CashFlow Team</b>\n\n{text}", parse_mode=ParseMode.HTML)
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await callback.message.edit_text(f"✅ Рассылка завершена. Отправлено {count} участникам.", parse_mode=ParseMode.HTML)
    await state.clear()
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_show_settings")
async def show_settings(callback: CallbackQuery):
    settings = {
        "chat_link": await get_setting("chat_link"),
        "app_channel": await get_setting("application_channel_id"),
        "log_channel": await get_setting("log_channel_id"),
        "welcome_gif": "установлена" if await get_setting("welcome_gif_file_id") else "не установлена"
    }
    text = "<b>📌 Текущие настройки:</b>\n"
    for k, v in settings.items():
        text += f"• {k}: {v}\n"
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_show_emoji_help")
async def show_emoji_help(callback: CallbackQuery):
    await callback.message.answer(
        "🎭 Премиум-эмодзи настраиваются в файле <code>emoji_config.py</code>.\n"
        "Чтобы добавить новый ID, вставь его в словарь EMOJI_DATA.\n"
        "ID можно получить через бота @getidsbot, отправив ему нужный эмодзи.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "admin_close")
async def close_admin_panel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()