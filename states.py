from aiogram.fsm.state import State, StatesGroup

class ApplyForm(StatesGroup):
    age = State()
    hours = State()
    experience = State()

class AdminAddProfit(StatesGroup):
    user_id = State()
    amount = State()

class AdminChangeRole(StatesGroup):
    user_id = State()
    role = State()

class AdminUpdateStats(StatesGroup):
    user_id = State()
    stat_type = State()
    value = State()

class AdminSetChatLink(StatesGroup):
    link = State()

class AdminBroadcast(StatesGroup):
    message = State()
    confirm = State()

class UserSettings(StatesGroup):
    change_name = State()
    change_avatar = State()

class AdminEditDisplayName(StatesGroup):
    name = State()

class SetChannel(StatesGroup):
    channel_type = State()
    forward = State()

class ProfitMedia(StatesGroup):
    amount = State()
    media_type = State()
    caption = State()
    file_id = State()