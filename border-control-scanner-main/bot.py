"""
Telegram Bot Entry Point for Bojxona Passport Scanner
Handles bot commands and integrates with FastAPI backend

Token: 8319403923:AAH8LkaqsickGL980lJKEOk51tVyhI6onZA
"""

import os
import asyncio
import logging
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import uvicorn
from threading import Thread

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8319403923:AAH8LkaqsickGL980lJKEOk51tVyhI6onZA")
WEBAPP_URL = os.environ.get("RAILWAY_STATIC_URL", "http://localhost:8000")

# Ensure HTTPS for production Railway deployments
if "railway.app" in WEBAPP_URL:
    # Add https:// if no protocol is present
    if not WEBAPP_URL.startswith(("http://", "https://")):
        WEBAPP_URL = f"https://{WEBAPP_URL}"
    # Replace http:// with https:// if present
    elif WEBAPP_URL.startswith("http://"):
        WEBAPP_URL = WEBAPP_URL.replace("http://", "https://")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show Mini App button"""
    user = update.effective_user

    welcome_message = (
        f"🛂 <b>Bojxona MRZ Scanner</b>\n\n"
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        f"O'zbekiston Davlat Bojxona Qo'mitasi chegarа nazorati uchun "
        f"<b>biometrik pasport MRZ skaneri</b>.\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>Barcha davlatlar pasportlari</b> qo'llab-quvvatlanadi\n"
        f"📋 <b>ICAO Doc 9303</b> TD3 standarti asosida ishlaydi\n"
        f"🔒 <b>Oflayn OCR</b> — ma'lumotlar tashqariga chiqmaydi\n"
        f"✅ <b>Matematik haqiqiylik tekshiruvi</b> (Modulo 10)\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📌 <i>Pasportni skanerlash uchun quyidagi tugmani bosing:</i>"
    )

    # Create Web App button
    keyboard = [
        [InlineKeyboardButton(
            "📷 Pasportni Skanerlash",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )],
        [InlineKeyboardButton("❓ Yordam", callback_data="help"),
         InlineKeyboardButton("ℹ️ Tizim", callback_data="info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 <b>Foydalanish qo'llanmasi</b>\n\n"
        "1️⃣ /start — Mini App ni ochish\n"
        "2️⃣ 📷 tugmasini bosing\n"
        "3️⃣ Kamerani yoqing va ruxsat bering\n"
        "4️⃣ Pasportning <b>pastki qismi</b> (MRZ zona) ni yashil ramkaga joylang\n"
        "5️⃣ Yorug'lik yetarli bo'lsin — soya va aks yo'q\n"
        "6️⃣ 📸 tugmasini bosib rasmga oling\n"
        "7️⃣ Natijani ko'ring va tekshiring\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>Eslatmalar:</b>\n"
        "• MRZ zona — pasportning <i>eng pastki 2 qatori</i>\n"
        "• Rasm loyqa bo'lsa qayta oling\n"
        "• Yorug'lik yetarli bo'lishi shart\n\n"
        "🆘 Muammo bo'lsa administrator bilan bog'laning"
    )

    await update.message.reply_text(help_text, parse_mode='HTML')


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command - System information"""
    info_text = (
        "ℹ️ <b>Tizim ma'lumotlari</b>\n\n"
        "🏷 <b>Nomi:</b> Bojxona MRZ Scanner\n"
        "🔢 <b>Versiya:</b> 3.5.0\n"
        "📜 <b>Standart:</b> ICAO Doc 9303 TD3\n"
        "🤖 <b>OCR:</b> PaddleOCR (oflayn)\n"
        "⚙️ <b>Backend:</b> FastAPI + Python 3.10\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "🌍 <b>Qo'llab-quvvatlanadigan pasportlar:</b>\n"
        "Barcha davlatlar ICAO TD3 biometrik pasportlari\n\n"
        "📋 <b>O'qiladigan ma'lumotlar:</b>\n"
        "🔹 Pasport raqami\n"
        "🔹 Familiya va Ism\n"
        "🔹 Tug'ilgan sana\n"
        "🔹 Jins (M / F)\n"
        "🔹 Amal qilish muddati\n"
        "🔹 Millat (davlat kodi)\n"
        "🔹 JSHSHIR/PNFL — faqat UZB pasportlari\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "🔐 <b>Haqiqiylik tekshiruvi:</b>\n"
        "✔️ Composite checksum (ICAO §4.2.2)\n"
        "✔️ 4 ta alohida Modulo-10 checksum\n"
        "✔️ Muddati tekshiruvi\n"
        "✔️ JSHSHIR ↔ MRZ cross-validation (UZB)\n"
        "📊 Natija: <b>HAQIQIY / SHUBHALI / SOXTA</b>"
    )

    await update.message.reply_text(info_text, parse_mode='HTML')


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos sent directly to the bot (not through Mini App)"""
    await update.message.reply_text(
        "📸 Rasmni qabul qildim!\n\n"
        "⚠️ <b>Eslatma:</b> Iltimos, Mini App orqali skanerlang.\n"
        "Mini App avtomatik validatsiya va to'liq ma'lumot beradi.\n\n"
        "Mini App ni ishga tushirish: /start",
        parse_mode='HTML'
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors including Telegram conflicts"""
    error_msg = str(context.error)

    # Handle Telegram Conflict (multiple bot instances)
    if "Conflict" in error_msg or "terminated by other getUpdates" in error_msg:
        logger.warning("⚠️ Telegram Conflict detected - another bot instance is running")
        logger.warning("This deployment will continue and override the previous instance")
        return  # Don't send error message to user for conflicts

    logger.error(f"Exception while handling an update: {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring yoki /help ni ko'ring."
        )


# Global application instance (shared with main.py for webhooks)
telegram_application = None

def get_application():
    """Get or create the Telegram application instance"""
    global telegram_application
    if telegram_application is None:
        telegram_application = Application.builder().token(BOT_TOKEN).build()

        # Register handlers
        telegram_application.add_handler(CommandHandler("start", start_command))
        telegram_application.add_handler(CommandHandler("help", help_command))
        telegram_application.add_handler(CommandHandler("info", info_command))
        telegram_application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        telegram_application.add_error_handler(error_handler)

    return telegram_application


def run_fastapi():
    """Run FastAPI server in a separate thread"""
    from main import app as fastapi_app
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


async def main():
    """Main function to start bot and FastAPI server"""
    # Start FastAPI in background thread
    fastapi_thread = Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info("FastAPI server started in background thread")

    # Small delay to let FastAPI start
    await asyncio.sleep(2)

    # Build Telegram bot application
    application = get_application()

    # Start bot
    logger.info("Starting Telegram bot...")
    await application.initialize()
    await application.start()

    # Check if we're running on Railway (use webhooks) or locally (use polling)
    is_railway = "railway.app" in WEBAPP_URL or os.environ.get("RAILWAY_ENVIRONMENT")

    if is_railway:
        # Use webhooks for Railway deployment (prevents conflicts)
        webhook_url = f"{WEBAPP_URL}/telegram-webhook"
        logger.info(f"🌐 Setting up webhook at: {webhook_url}")

        # Set webhook
        await application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )

        logger.info("✅ Bojxona Passport Scanner is now running in WEBHOOK mode!")
        logger.info(f"📱 Mini App URL: {WEBAPP_URL}")
        logger.info(f"🔗 Webhook: {webhook_url}")

    else:
        # Use polling for local development
        logger.info("🔄 Running in POLLING mode (local development)")

        # Delete webhook to ensure clean polling
        logger.info("Clearing any existing webhooks...")
        await application.bot.delete_webhook(drop_pending_updates=True)

        await application.updater.start_polling(drop_pending_updates=True)

        logger.info("✅ Bojxona Passport Scanner is now running in POLLING mode!")
        logger.info(f"📱 Mini App URL: {WEBAPP_URL}")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if not is_railway and application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
