import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_ID
from db import *
from keyboards import main_menu, approve_buttons, edit_user_buttons, admin_panel_buttons, apply_button
from states import ApplyForm, UserSettings, AdminEditDisplayName
from emoji_config import format_emoji

router = Router()

def get_display_name(user_data: dict) -> str:
    return user_data.get('display_name') or user_data.get('username', f"user_{user_data['user_id']}")

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user and user.get('approved'):
        await update_last_active(user_id)
        is_admin = (user_id == ADMIN_ID)
        welcome_text = f"{format_emoji('welcome')} Добро пожаловать в CashFlow Team, {get_display_name(user)}!\nИспользуй кнопки меню."
        await message.answer(welcome_text, reply_markup=main_menu(is_admin), parse_mode=ParseMode.HTML)
    else:
        await message.answer(
            f"{format_emoji('welcome')} Привет! Ты ещё не в команде CashFlow Team.\nНажми на кнопку, чтобы подать заявку.",
            reply_markup=apply_button(),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda c: c.data == "start_apply")
async def callback_apply(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if user and user.get('approved'):
        await callback.message.answer("Ты уже в команде! Используй главное меню.")
        await callback.answer()
        return
    await state.set_state(ApplyForm.age)
    await callback.message.answer(f"{format_emoji('apply')} Заявка в CashFlow Team\nСколько тебе лет? (только число, от 18)", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(ApplyForm.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи число.", parse_mode=ParseMode.HTML)
        return
    age = int(message.text)
    if age < 18:
        await message.answer("Извини, только с 18 лет.", parse_mode=ParseMode.HTML)
        return
    await state.update_data(age=age)
    await state.set_state(ApplyForm.hours)
    await message.answer("Сколько времени готов уделять работе в день? (например: 3-4 часа)", parse_mode=ParseMode.HTML)

@router.message(ApplyForm.hours)
async def process_hours(message: Message, state: FSMContext):
    await state.update_data(hours=message.text)
    await state.set_state(ApplyForm.experience)
    await message.answer("Был ли опыт в стримах/накрутке/командной работе? Расскажи подробнее.", parse_mode=ParseMode.HTML)

@router.message(ApplyForm.experience)
async def process_experience(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    age = data['age']
    hours = data['hours']
    experience = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "без username"

    await save_pending_app(user_id, str(age), hours, experience)

    text = (f"📩 Новая заявка в CashFlow Team!\n"
            f"👤 @{username} (ID: {user_id})\n"
            f"📅 Возраст: {age}\n"
            f"⏳ Время: {hours}\n"
            f"📝 Опыт: {experience}")
    await bot.send_message(ADMIN_ID, text, reply_markup=approve_buttons(user_id), parse_mode=ParseMode.HTML)

    app_channel = await get_setting("application_channel_id")
    if app_channel and app_channel.isdigit():
        await bot.send_message(int(app_channel), text, reply_markup=approve_buttons(user_id), parse_mode=ParseMode.HTML)

    await message.answer("✅ Заявка отправлена! Ожидай решения.", parse_mode=ParseMode.HTML)
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_application(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    pending = await get_pending_app(user_id)
    if not pending:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await callback.message.delete()
        return
    user_info = await bot.get_chat(user_id)
    username = user_info.username or ""
    age = int(pending['age'])
    await create_user(user_id, username, age, role="новичок")
    gif_id = await get_setting("welcome_gif_file_id")
    caption = f"{format_emoji('welcome')} Поздравляю! Ты принят в команду CashFlow Team.\nТеперь у тебя есть доступ к главному меню.\nНе забудь заполнить настройки.\nУдачи!"
    if gif_id:
        try:
            await bot.send_animation(user_id, gif_id, caption=caption, parse_mode=ParseMode.HTML)
        except:
            await bot.send_message(user_id, caption, parse_mode=ParseMode.HTML)
    else:
        await bot.send_message(user_id, caption, parse_mode=ParseMode.HTML)
    await delete_pending_app(user_id)
    await callback.message.edit_text(f"{format_emoji('approved')} Заявка принята!", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_application(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    await delete_pending_app(user_id)
    try:
        await bot.send_message(user_id, f"{format_emoji('rejected')} К сожалению, твоя заявка отклонена. Спасибо за интерес!", parse_mode=ParseMode.HTML)
    except:
        pass
    await callback.message.edit_text(f"{format_emoji('rejected')} Заявка отклонена.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(F.text == "🧸 Профиль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user or not user.get('approved'):
        await message.answer("Ты не в команде. Напиши /start", parse_mode=ParseMode.HTML)
        return
    await update_last_active(user_id)
    display = get_display_name(user)
    role = user['role']
    profit = user['profit']
    recruited = user['recruited_streamers']
    streams = user['streams_count']
    join_date = user['join_date'][:10]
    age = user['age']
    text = (f"{format_emoji('profile')} Профиль участника CashFlow Team\n\n"
            f"👤 Имя: {display}\n"
            f"📅 Возраст: {age}\n"
            f"⭐ Роль: {role}\n"
            f"💰 Профит: {profit} руб.\n")
    if role == "трафер":
        text += f"📢 Приведено стримерш: {recruited}\n"
    elif role == "стримерша":
        text += f"🎥 Количество стримов: {streams}\n"
    text += f"📆 Дата вступления: {join_date}"
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать профиль (админ)", callback_data="admin_edit_any_profile")]
        ])
        await message.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await message.answer(text, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "admin_edit_any_profile")
async def admin_edit_any_profile(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав", show_alert=True)
        return
    users = await get_all_users(only_approved=True)
    if not users:
        await callback.message.edit_text("Нет участников.", parse_mode=ParseMode.HTML)
        return
    buttons = []
    for u in users:
        name = get_display_name(u)
        buttons.append([InlineKeyboardButton(text=f"{name} (@{u['username']})", callback_data=f"admin_edit_user_{u['user_id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_close")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выбери участника для редактирования:", reply_markup=markup, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("admin_edit_user_"))
async def edit_selected_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(f"Редактирование пользователя ID {user_id}", reply_markup=edit_user_buttons(user_id), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user or not user.get('approved'):
        await message.answer("Ты не в команде.", parse_mode=ParseMode.HTML)
        return
    await update_last_active(user_id)
    if user_id == ADMIN_ID:
        stats = await get_team_stats()
        text = (f"{format_emoji('stats')} Статистика CashFlow Team\n\n"
                f"👥 Всего участников: {stats['total']}\n"
                f"🎭 Стримерш: {stats['streamers']}\n"
                f"🚀 Траферов: {stats['traffers']}\n"
                f"🛡️ Модераторов: {stats['moders']}\n"
                f"💰 Общий профит: {stats['total_profit']} руб.\n"
                f"📅 Активных за неделю: {stats['active_week']}")
    else:
        role = user['role']
        profit = user['profit']
        recruited = user['recruited_streamers']
        streams = user['streams_count']
        text = (f"{format_emoji('stats')} Твоя статистика:\n"
                f"💰 Профит: {profit} руб.\n")
        if role == "трафер":
            text += f"📢 Приведено стримерш: {recruited}\n"
        elif role == "стримерша":
            text += f"🎥 Количество стримов: {streams}\n"
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user or not user.get('approved'):
        await message.answer("Ты не в команде.", parse_mode=ParseMode.HTML)
        return
    await update_last_active(user_id)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить отображаемое имя", callback_data="settings_change_name")],
        [InlineKeyboardButton(text="🖼️ Установить аватарку", callback_data="settings_change_avatar")],
        [InlineKeyboardButton(text="🔔 Включить/отключить уведомления", callback_data="settings_toggle_notify")]
    ])
    await message.answer(f"{format_emoji('settings')} Настройки профиля:", reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "settings_change_name")
async def change_name_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSettings.change_name)
    await callback.message.answer("Введите новое отображаемое имя:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(UserSettings.change_name)
async def change_name_process(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) > 50:
        await message.answer("Имя слишком длинное.", parse_mode=ParseMode.HTML)
        return
    await update_user(message.from_user.id, display_name=new_name)
    await message.answer(f"✅ Имя изменено на {new_name}", parse_mode=ParseMode.HTML)
    await state.clear()

@router.callback_query(lambda c: c.data == "settings_change_avatar")
async def change_avatar_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSettings.change_avatar)
    await callback.message.answer("Отправьте фото для аватарки:", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(UserSettings.change_avatar, F.photo)
async def change_avatar_process(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await update_user(message.from_user.id, avatar_file_id=file_id)
    await message.answer("✅ Аватарка сохранена!", parse_mode=ParseMode.HTML)
    await state.clear()

@router.message(UserSettings.change_avatar)
async def change_avatar_invalid(message: Message):
    await message.answer("Пожалуйста, отправьте фото.", parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data == "settings_toggle_notify")
async def toggle_notifications(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        await callback.answer("Ошибка")
        return
    new_setting = not user['notification_settings']
    await update_user(user_id, notification_settings=new_setting)
    status = "включены" if new_setting else "выключены"
    await callback.message.answer(f"🔔 Уведомления {status}.", parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(F.text == "💬 Чат команды")
async def chat_link(message: Message):
    link = await get_setting("chat_link")
    if link:
        await message.answer(f"{format_emoji('chat')} Ссылка на чат CashFlow Team:\n{link}", parse_mode=ParseMode.HTML)
    else:
        await message.answer("Ссылка на чат ещё не установлена.", parse_mode=ParseMode.HTML)

@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.", parse_mode=ParseMode.HTML)
        return
    await message.answer(f"{format_emoji('admin')} Панель управления CashFlow Team:", reply_markup=admin_panel_buttons, parse_mode=ParseMode.HTML)