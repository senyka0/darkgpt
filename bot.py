import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from main import AnswerResult, ask_question

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_MAX = 4096


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Send me a question and I will answer it.")


async def send_text(update: Update, text: str) -> None:
    for i in range(0, len(text), TELEGRAM_MAX):
        await update.message.reply_text(text[i : i + TELEGRAM_MAX])


async def send_images(update: Update, images: list[bytes]) -> None:
    for img_data in images:
        try:
            await update.message.reply_photo(photo=img_data)
        except Exception as exc:
            logger.warning("failed to send image: %s", exc)
            await update.message.reply_text(f"(image: {len(img_data)} bytes, failed to send: {exc})")


async def send_answer(update: Update, result: AnswerResult) -> None:
    if result.text:
        await send_text(update, result.text)
    if result.images:
        await send_images(update, result.images)


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = (update.message.text or "").strip()
    if not question:
        return

    loading = await update.message.reply_text("Processing...")
    loop = asyncio.get_running_loop()

    def status(message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            loading.edit_text(f"Processing...\n{message}"),
            loop,
        )

    try:
        result = await asyncio.to_thread(ask_question, question, status)
        await loading.delete()
        await send_answer(update, result)
    except Exception as exc:
        logger.exception("question failed")
        try:
            await loading.delete()
        except Exception:
            pass
        await update.message.reply_text(f"Error: {exc}")


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("set TELEGRAM_BOT_TOKEN environment variable")
        return 1

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    logger.info("bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())