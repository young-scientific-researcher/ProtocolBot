import os
import requests
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

SUPABASE_URL = "https://kplgemcfwgjszrwepitq.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwbGdlbWNmd2dqc3pyd2VwaXRxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTM0Nzg3OCwiZXhwIjoyMDcwOTIzODc4fQ.7QJ99pPkPDIYBEeOLGt0VuOZIU1vHwOjWZ7qOwybmxQ"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------- Команды бота -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для поиска протоколов от разных научных групп LIFT.\n"
        "Используйте /search <ключевые слова> для поиска протоколов.\n"
        "Например: /search astrocytes"
    )

async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем все доступные ключевые слова
    tags_resp = supabase.table("tags").select("name").execute()
    tags = [t['name'] for t in tags_resp.data]
    await update.message.reply_text("Доступные ключевые слова:\n" + ", ".join(tags))

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите хотя бы одно ключевое слово.")
        return

    keywords_list = [k.lower() for k in context.args]

    # Находим id тегов по ключевым словам
    tags_resp = supabase.table("tags").select("id, name").execute()
    tag_ids = [t['id'] for t in tags_resp.data if t['name'].lower() in keywords_list]

    if not tag_ids:
        await update.message.reply_text("Теги не найдены.")
        return

    # Находим id протоколов с этими тегами
    protocols_tags_resp = supabase.table("protocols_tags").select("protocol_id").in_("tag_id", tag_ids).execute()
    protocol_ids = list(set([pt['protocol_id'] for pt in protocols_tags_resp.data]))

    if not protocol_ids:
        await update.message.reply_text("Протоколы по этим ключевым словам не найдены.")
        return

    # Получаем сами протоколы
    protocols_resp = supabase.table("protocols").select("id, title").in_("id", protocol_ids).execute()
    found = protocols_resp.data

    if not found:
        await update.message.reply_text("Протоколы по этим ключевым словам не найдены.")
        return

    # Создаем кнопки для выбора протокола
    keyboard = [[InlineKeyboardButton(p['title'], callback_data=str(p['id']))] for p in found]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Найдены протоколы. Выберите нужный:", reply_markup=reply_markup)

async def protocol_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    protocol_id = int(query.data)
    resp = supabase.table("protocols").select("*").eq("id", protocol_id).execute()
    if not resp.data:
        await query.edit_message_text("Протокол не найден.")
        return

    protocol = resp.data[0]

    text = f"**{protocol['title']}**\n\n"
    if protocol.get("author"):
        text += f"Автор: {protocol['author']}\n"
    if protocol.get("keywords"):
        text += f"Ключевые слова: {protocol['keywords']}\n"
    if protocol.get("comment"):
        text += f"Комментарий: {protocol['comment']}\n"

    if protocol.get("materials"):
        text += "\n**Материалы:**\n"
        for m in protocol['materials']:
            text += f"- {m}\n"

    if protocol.get("procedure"):
        text += "\n**Процедура:**\n"
        for step in protocol['procedure']:
            text += f"{step['step_number']}. {step['text']}\n"

    await query.edit_message_text(text, parse_mode="Markdown")

# ----------------- Запуск бота -----------------
if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    APP_URL = os.getenv("https://protocolbot-08w8.onrender.com")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tags", list_tags))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CallbackQueryHandler(protocol_detail))

    if APP_URL:  # Если деплой на Render
        webhook_url = f"{APP_URL}/{TELEGRAM_TOKEN}"
        print(f"Запуск webhook на {webhook_url}...")
        app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url_path=TELEGRAM_TOKEN, url_path=TELEGRAM_TOKEN)
    if not APP_URL:  # локальный запуск
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
        print("Старый webhook удалён, запускаем polling...")
        app.run_polling()