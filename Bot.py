import os
import requests
import asyncio
import logging
from typing import List
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, InlineQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Supabase
SUPABASE_URL = "https://kplgemcfwgjszrwepitq.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwbGdlbWNmd2dqc3pyd2VwaXRxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTM0Nzg3OCwiZXhwIjoyMDcwOTIzODc4fQ.7QJ99pPkPDIYBEeOLGt0VuOZIU1vHwOjWZ7qOwybmxQ"
# TELEGRAM_TOKEN = '8217325864:AAE7Jpx06kA5TL7rPwYNAj_Mz54iUhKwLXg'
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Кэш тегов
TAGS_CACHE = []

async def refresh_tags_cache():
    """Обновление кэша тегов из базы данных"""
    global TAGS_CACHE
    try:
        response = supabase.table("tags").select("id, name").execute()
        if response.data:
            TAGS_CACHE = response.data
            logger.info(f"Tags cache refreshed. Total tags: {len(TAGS_CACHE)}")
        else:
            logger.warning("No tags found in database")
    except Exception as e:
        logger.error(f"Error refreshing tags cache: {e}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        await update.message.reply_text(
            "🔬 <b>Protocol Search Bot</b>\n\n"
            "Я помогу найти научные протоколы лабораторий LIFT.\n\n"
            "<b>Основные команды:</b>\n"
            "Введите <code>/search ключевое_слово</code> для поиска протоколов\n"
            "Введите <code>/tags<code> для просмотра всех тэгов\n\n",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in start: {e}")

async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все теги с клавиатурой для быстрого выбора"""
    try:
        if not TAGS_CACHE:
            await refresh_tags_cache()
        
        if not TAGS_CACHE:
            await update.message.reply_text("ℹ️ В базе данных нет тегов.")
            return
        
        # Создаем кнопки для тегов (3 в ряд)
        buttons = [
            InlineKeyboardButton(tag['name'], callback_data=f"search_tag_{tag['name']}")
            for tag in TAGS_CACHE
        ]
        
        # Группируем кнопки по 3 в ряд
        keyboard = []
        for i in range(0, len(buttons), 3):
            keyboard.append(buttons[i:i+3])
        
        await update.message.reply_text(
            "🏷 <b>Доступные теги:</b>\n\n"
            "Выберите тег для поиска:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in list_tags: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при загрузке тегов. Попробуйте позже.",
            parse_mode="HTML"
        )

async def handle_tag_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора тега из списка"""
    query = update.callback_query
    await query.answer()
    
    try:
        tag_name = query.data.replace("search_tag_", "")
        await perform_search(update, [tag_name], is_callback=True)
    except Exception as e:
        logger.error(f"Error in handle_tag_selection: {e}")
        await query.edit_message_text("⚠️ Ошибка при поиске по тегу.")

async def perform_search(update: Update, keywords: List[str], is_callback: bool = False):
    """Основная логика поиска"""
    try:
        if not TAGS_CACHE:
            await refresh_tags_cache()
        
        keywords_list = [k.lower().strip() for k in keywords]
        tag_ids = [t['id'] for t in TAGS_CACHE if t['name'].lower().strip() in keywords_list]
        
        if not tag_ids:
            available_tags = "\n".join(f"• {tag['name']}" for tag in TAGS_CACHE[:10])
            message = (
                "🔍 <b>Теги не найдены</b>\n\n"
                f"Популярные теги:\n{available_tags}\n\n"
                "Попробуйте другой запрос или посмотрите /tags"
            )
            
            if is_callback:
                await update.callback_query.edit_message_text(message, parse_mode="HTML")
            else:
                await update.message.reply_text(message, parse_mode="HTML")
            return
        
        protocol_ids = supabase.table("protocol_tags") \
            .select("protocol_id") \
            .in_("tag_id", tag_ids) \
            .execute()
        protocol_ids = list({p['protocol_id'] for p in protocol_ids.data})
        
        if not protocol_ids:
            message = "📭 Протоколы по этим тегам не найдены."
            if is_callback:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
            
        protocols = supabase.table("protocols") \
            .select("id, title") \
            .in_("id", protocol_ids) \
            .execute()
            
        keyboard = [
            [InlineKeyboardButton(p['title'], callback_data=str(p['id']))]
            for p in protocols.data
        ]
        
        message = f"🔍 Найдено протоколов: {len(protocols.data)}\nВыберите нужный:"
        
        if is_callback:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        error_msg = "⚠️ Ошибка при поиске. Попробуйте позже."
        if is_callback:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-запросов"""
    query = update.inline_query.query.lower()
    
    if not TAGS_CACHE:
        await refresh_tags_cache()
    
    results = []
    for tag in TAGS_CACHE:
        if query in tag['name'].lower():
            results.append(
                InlineQueryResultArticle(
                    id=tag['name'],
                    title=f"🔍 {tag['name']}",
                    description=f"Поиск протоколов по тегу {tag['name']}",
                    input_message_content=InputTextMessageContent(
                        f"/search {tag['name']}"
                    )
                )
            )
    
    await update.inline_query.answer(results[:15], cache_time=300)
    
async def protocol_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        protocol_id = int(query.data)
        resp = supabase.table("protocols").select("*").eq("id", protocol_id).execute()
        
        if not resp.data:
            await query.edit_message_text("Протокол не найден.")
            return

        protocol = resp.data[0]
        
        # Формируем заголовок
        text = f"<b>{protocol['title']}</b>\n\n"
        
        # Добавляем мета-информацию
        meta_info = []
        if protocol.get("author"):
            meta_info.append(f"👤 <b>Author:</b> {protocol['author']}")
        if protocol.get("keywords"):
            meta_info.append(f"🏷 <b>Keywords:</b> {protocol['keywords']}")
        if protocol.get("comment"):
            meta_info.append(f"💬 <b>Comment:</b> {protocol['comment']}")
        
        text += "\n".join(meta_info) + "\n"
        
        # Форматируем материалы
        if protocol.get("materials"):
            text += "\n<b>🛠 Materials and reagents:</b>\n"
            if isinstance(protocol['materials'], list):
                for item in protocol['materials']:
                    if isinstance(item, dict):
                        text += f"• {item.get('text', '')}\n"
                    else:
                        text += f"• {item}\n"
        
        # Форматируем процедуру
        if protocol.get("procedure"):
            text += "\n<b>🔬 Procedure:</b>\n"
            if isinstance(protocol['procedure'], list):
                for step in protocol['procedure']:
                    if isinstance(step, dict):
                        step_num = step.get('step_number', '?')
                        step_text = step.get('text', '')
                        text += f"{step_num}. {step_text}\n"
                    else:
                        text += f"• {step}\n"
        
        # Добавляем разделитель в конце
        text += "\n━━━━━━━━━━━━━━\n"
        
        await query.edit_message_text(
            text, 
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Protocol detail error: {str(e)}")
        await query.edit_message_text(
            "Ошибка при загрузке протокола.",
            parse_mode="HTML"
        )



def main():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8217325864:AAE7Jpx06kA5TL7rPwYNAj_Mz54iUhKwLXg"
    PORT = int(os.environ.get("PORT", 8443))
    APP_URL = os.getenv("APP_URL")
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tags", list_tags))
    application.add_handler(CommandHandler("search", lambda u, c: perform_search(u, c.args)))
    
    # Обработчики callback'ов
    application.add_handler(CallbackQueryHandler(protocol_detail, pattern=r"^\d+$"))
    application.add_handler(CallbackQueryHandler(handle_tag_selection, pattern=r"^search_tag_"))
    
    # Inline-обработчик
    application.add_handler(InlineQueryHandler(inline_query))
    
    # Запуск бота
    if APP_URL:
        webhook_url = f"{APP_URL}/{TELEGRAM_TOKEN}"
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url,
            url_path=TELEGRAM_TOKEN
        )
    else:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
        application.run_polling()

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    
    main()