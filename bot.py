import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ─────────────────────────────────────────
#  КОНФИГУРАЦИЯ
# ─────────────────────────────────────────
BOT_TOKEN = "8857561371:AAH9mnpw-70SoDK1TOpSWjgPvqJFe25Sp6w"

DATA_FILE = "data.json"

# ─────────────────────────────────────────
#  РАБОТА С ДАННЫМИ
# ─────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "super_admins": [599952947, 8531243207, 7201046344],
        "content_admins": [],
        "users": [8531243207, 8422967271, 791428991, 7201046344, 6359224120, 599952947],
        "broadcast_message": "✏️ Сообщение ещё не загружено.",
        "broadcast_photo": None,
        "folders_message": "📁 Папки и чаты ещё не добавлены.",
        "folders_photo": None
    }

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_data():
    if not os.path.exists(DATA_FILE):
        save_data(load_data())
    else:
        # Добавить новые поля если их нет (миграция)
        data = load_data()
        changed = False
        for key, default in [("broadcast_photo", None), ("folders_photo", None)]:
            if key not in data:
                data[key] = default
                changed = True
        if changed:
            save_data(data)

# ─────────────────────────────────────────
#  ПРОВЕРКИ ПРАВ
# ─────────────────────────────────────────
def is_user(uid: int, data: dict) -> bool:
    return uid in data["users"] or uid in data["super_admins"] or uid in data["content_admins"]

def can_edit_content(uid: int, data: dict) -> bool:
    return uid in data["super_admins"] or uid in data["content_admins"]

def is_super_admin(uid: int, data: dict) -> bool:
    return uid in data["super_admins"]

# ─────────────────────────────────────────
#  КЛАВИАТУРЫ
# ─────────────────────────────────────────
def get_keyboard(uid: int, data: dict):
    base = [
        [KeyboardButton("📢 Актуальное сообщение для рассылки")],
        [KeyboardButton("📂 Папки и чаты для рассылок")],
    ]
    if can_edit_content(uid, data):
        base.append([KeyboardButton("✏️ Обновить сообщение для рассылки")])
        base.append([KeyboardButton("🗂 Обновить папки и чаты")])
    if is_super_admin(uid, data):
        base.append([KeyboardButton("👥 Управление пользователями")])
    return ReplyKeyboardMarkup(base, resize_keyboard=True)

# ─────────────────────────────────────────
#  ОТПРАВКА МАТЕРИАЛА (текст + фото)
# ─────────────────────────────────────────
async def send_material(update: Update, text: str, photo_id: str | None, keyboard):
    """Отправляет материал — с фото или без, сохраняя форматирование."""
    if photo_id:
        await update.message.reply_photo(
            photo=photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

# ─────────────────────────────────────────
#  /start
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    name = update.effective_user.first_name

    if not is_user(uid, data):
        await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        return

    context.user_data.clear()

    if is_super_admin(uid, data):
        role = "🔑 Супер-администратор"
    elif can_edit_content(uid, data):
        role = "🛠 Контент-администратор"
    else:
        role = "👤 Пользователь"

    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n"
        f"🤖 <b>Materials for admins of OpusGuru</b>\n"
        f"Ваша роль: {role}\n\n"
        "Выберите нужный раздел 👇",
        parse_mode="HTML",
        reply_markup=get_keyboard(uid, data)
    )

# ─────────────────────────────────────────
#  ОБРАБОТКА ФОТО (при загрузке материала)
# ─────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id

    if not is_user(uid, data):
        return

    waiting = context.user_data.get("waiting_for")

    if waiting not in ("broadcast_photo", "folders_photo"):
        await update.message.reply_text(
            "Фото принято только в режиме обновления материала. Используйте кнопки меню 👇",
            reply_markup=get_keyboard(uid, data)
        )
        return

    # Берём file_id самого большого размера фото
    photo_id = update.message.photo[-1].file_id
    caption = update.message.caption or ""

    if waiting == "broadcast_photo":
        # Если есть подпись — сохраняем и текст и фото
        if caption:
            data["broadcast_message"] = caption
        data["broadcast_photo"] = photo_id
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Фото (и текст) для сообщения рассылки обновлены!",
            reply_markup=get_keyboard(uid, data)
        )

    elif waiting == "folders_photo":
        if caption:
            data["folders_message"] = caption
        data["folders_photo"] = photo_id
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Фото (и текст) для папок и чатов обновлены!",
            reply_markup=get_keyboard(uid, data)
        )

# ─────────────────────────────────────────
#  ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА
# ─────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    text = update.message.text

    if not is_user(uid, data):
        await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        return

    waiting = context.user_data.get("waiting_for")

    # ── Ожидание текста для материалов ─────────────────────────
    if waiting == "broadcast_message":
        # Сохраняем текст как есть (HTML-entities уже в тексте от пользователя)
        data["broadcast_message"] = text
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text("✅ Текст сообщения для рассылки обновлён!", reply_markup=get_keyboard(uid, data))
        return

    if waiting == "broadcast_photo":
        # Пользователь прислал текст вместо фото — предлагаем варианты
        await update.message.reply_text(
            "Пришлите фото 📷 (можно с подписью).\n\nЕсли хотите убрать фото и оставить только текст — /remove_broadcast_photo\n\nДля отмены — /cancel"
        )
        return

    if waiting == "folders_message":
        data["folders_message"] = text
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text("✅ Текст папок и чатов обновлён!", reply_markup=get_keyboard(uid, data))
        return

    if waiting == "folders_photo":
        await update.message.reply_text(
            "Пришлите фото 📷 (можно с подписью).\n\nЕсли хотите убрать фото — /remove_folders_photo\n\nДля отмены — /cancel"
        )
        return

    # ── Ожидание ID для управления пользователями ───────────────
    if waiting == "add_content_admin":
        try:
            new_id = int(text.strip())
            if new_id not in data["content_admins"]:
                data["content_admins"].append(new_id)
                if new_id not in data["users"]:
                    data["users"].append(new_id)
                save_data(data)
                await update.message.reply_text(
                    f"✅ <code>{new_id}</code> добавлен как <b>контент-администратор</b>.\nМожет обновлять материалы и пользоваться ботом.",
                    parse_mode="HTML", reply_markup=get_keyboard(uid, data))
            else:
                await update.message.reply_text("ℹ️ Уже является контент-администратором.", reply_markup=get_keyboard(uid, data))
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите числовой Telegram ID.", reply_markup=get_keyboard(uid, data))
        context.user_data.clear()
        return

    if waiting == "add_user":
        try:
            new_id = int(text.strip())
            if new_id not in data["users"]:
                data["users"].append(new_id)
                save_data(data)
                await update.message.reply_text(
                    f"✅ <code>{new_id}</code> добавлен как <b>пользователь</b>.\nМожет просматривать материалы бота.",
                    parse_mode="HTML", reply_markup=get_keyboard(uid, data))
            else:
                await update.message.reply_text("ℹ️ Уже есть в списке.", reply_markup=get_keyboard(uid, data))
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите числовой Telegram ID.", reply_markup=get_keyboard(uid, data))
        context.user_data.clear()
        return

    if waiting == "remove_user":
        try:
            rem_id = int(text.strip())
            removed_from = []
            if rem_id in data["users"]:
                data["users"].remove(rem_id)
                removed_from.append("пользователи")
            if rem_id in data["content_admins"]:
                data["content_admins"].remove(rem_id)
                removed_from.append("контент-администраторы")
            if removed_from:
                save_data(data)
                await update.message.reply_text(
                    f"✅ <code>{rem_id}</code> удалён из: {', '.join(removed_from)}.",
                    parse_mode="HTML", reply_markup=get_keyboard(uid, data))
            else:
                await update.message.reply_text("ℹ️ Пользователь не найден.", reply_markup=get_keyboard(uid, data))
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите числовой Telegram ID.", reply_markup=get_keyboard(uid, data))
        context.user_data.clear()
        return

    # ── Просмотр материалов ─────────────────────────────────────
    if text == "📢 Актуальное сообщение для рассылки":
        await send_material(
            update,
            data["broadcast_message"],
            data.get("broadcast_photo"),
            get_keyboard(uid, data)
        )

    elif text == "📂 Папки и чаты для рассылок":
        await send_material(
            update,
            data["folders_message"],
            data.get("folders_photo"),
            get_keyboard(uid, data)
        )

    # ── Редактирование материалов ───────────────────────────────
    elif text == "✏️ Обновить сообщение для рассылки":
        if not can_edit_content(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return

        update_kb = ReplyKeyboardMarkup([
            [KeyboardButton("📝 Обновить только текст")],
            [KeyboardButton("🖼 Обновить только фото")],
            [KeyboardButton("🔙 Назад")],
        ], resize_keyboard=True)
        context.user_data["edit_target"] = "broadcast"
        await update.message.reply_text(
            "Что хотите обновить в сообщении для рассылки?",
            reply_markup=update_kb
        )

    elif text == "🗂 Обновить папки и чаты":
        if not can_edit_content(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return

        update_kb = ReplyKeyboardMarkup([
            [KeyboardButton("📝 Обновить только текст")],
            [KeyboardButton("🖼 Обновить только фото")],
            [KeyboardButton("🔙 Назад")],
        ], resize_keyboard=True)
        context.user_data["edit_target"] = "folders"
        await update.message.reply_text(
            "Что хотите обновить в папках и чатах?",
            reply_markup=update_kb
        )

    # ── Подменю редактирования ──────────────────────────────────
    elif text == "📝 Обновить только текст":
        target = context.user_data.get("edit_target")
        if not target or not can_edit_content(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return
        context.user_data["waiting_for"] = f"{target}_message"
        await update.message.reply_text(
            "✏️ Отправьте новый текст.\n\n"
            "<b>Поддерживается HTML-форматирование:</b>\n"
            "<code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
            "<code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
            "<code>&lt;a href='ссылка'&gt;текст&lt;/a&gt;</code>\n\n"
            "Для отмены — /cancel",
            parse_mode="HTML"
        )

    elif text == "🖼 Обновить только фото":
        target = context.user_data.get("edit_target")
        if not target or not can_edit_content(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return
        context.user_data["waiting_for"] = f"{target}_photo"
        await update.message.reply_text(
            "🖼 Пришлите фото.\n\nМожно добавить подпись к фото — тогда текст тоже обновится.\n\nДля отмены — /cancel"
        )

    # ── Управление пользователями ───────────────────────────────
    elif text == "👥 Управление пользователями":
        if not is_super_admin(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return

        super_list = "\n".join([f"• <code>{i}</code>" for i in data["super_admins"]])
        content_list = "\n".join([f"• <code>{i}</code>" for i in data["content_admins"]]) or "<i>(пусто)</i>"
        users_list = "\n".join([f"• <code>{i}</code>" for i in data["users"]]) or "<i>(пусто)</i>"

        mgmt_kb = ReplyKeyboardMarkup([
            [KeyboardButton("➕ Добавить контент-администратора")],
            [KeyboardButton("➕ Добавить пользователя")],
            [KeyboardButton("❌ Удалить пользователя / администратора")],
            [KeyboardButton("🔙 Назад")],
        ], resize_keyboard=True)

        await update.message.reply_text(
            f"👥 <b>Управление пользователями</b>\n\n"
            f"🔑 <b>Супер-админы</b> (заданы в коде):\n{super_list}\n\n"
            f"🛠 <b>Контент-администраторы:</b>\n{content_list}\n\n"
            f"👤 <b>Пользователи:</b>\n{users_list}",
            parse_mode="HTML", reply_markup=mgmt_kb)

    elif text == "➕ Добавить контент-администратора":
        if not is_super_admin(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return
        context.user_data["waiting_for"] = "add_content_admin"
        await update.message.reply_text(
            "🛠 Введите Telegram ID нового <b>контент-администратора</b>.\n"
            "Он сможет обновлять материалы и пользоваться ботом.\n\n"
            "Для отмены — /cancel", parse_mode="HTML")

    elif text == "➕ Добавить пользователя":
        if not is_super_admin(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return
        context.user_data["waiting_for"] = "add_user"
        await update.message.reply_text(
            "👤 Введите Telegram ID нового <b>пользователя</b>.\n"
            "Он сможет просматривать материалы бота.\n\n"
            "Для отмены — /cancel", parse_mode="HTML")

    elif text == "❌ Удалить пользователя / администратора":
        if not is_super_admin(uid, data):
            await update.message.reply_text("⛔️ Нет прав.", reply_markup=get_keyboard(uid, data))
            return
        context.user_data["waiting_for"] = "remove_user"
        await update.message.reply_text("❌ Введите Telegram ID пользователя для удаления.\n\nДля отмены — /cancel")

    elif text == "🔙 Назад":
        context.user_data.clear()
        await update.message.reply_text("Главное меню 👇", reply_markup=get_keyboard(uid, data))

    else:
        await update.message.reply_text("Используйте кнопки меню 👇", reply_markup=get_keyboard(uid, data))


# ─────────────────────────────────────────
#  КОМАНДЫ УДАЛЕНИЯ ФОТО
# ─────────────────────────────────────────
async def remove_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    if not can_edit_content(uid, data):
        return
    data["broadcast_photo"] = None
    save_data(data)
    context.user_data.clear()
    await update.message.reply_text("✅ Фото из сообщения для рассылки удалено.", reply_markup=get_keyboard(uid, data))

async def remove_folders_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    if not can_edit_content(uid, data):
        return
    data["folders_photo"] = None
    save_data(data)
    context.user_data.clear()
    await update.message.reply_text("✅ Фото из папок и чатов удалено.", reply_markup=get_keyboard(uid, data))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    if not is_user(uid, data):
        return
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.", reply_markup=get_keyboard(uid, data))


# ─────────────────────────────────────────
#  ЗАПУСК
# ─────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def main():
    init_data()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("remove_broadcast_photo", remove_broadcast_photo))
    app.add_handler(CommandHandler("remove_folders_photo", remove_folders_photo))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
