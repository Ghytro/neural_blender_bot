import queue, logging, browsing, asyncio

from telegram import (
    InputMediaPhoto,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from cfg.config import BOT_CONFIG

# Logging
from telegram import __version__ as TG_VER
try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"Update PTB up to version 20.0a0 (your current version: {TG_VER})"
    )

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class Bot:
    def __init__(self):
        self.__application = Application.builder().token(BOT_CONFIG["token"]).build()
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and not attr_name.startswith("__"):
                self.__application.add_handler(CommandHandler(attr_name, attr))
        self.__application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.__message_handler
            )
        )
        # Needed for implementation of alternative of next_step_handler, provided by telebot.
        # The key in dictionary is user id, the value is a dictionary, where the key is chat id
        # and a value is a queue with pending callbacks. This approach is used to have separate queues for
        # the same user in different chats, which allows to store private and group chats queues separately.
        # The keys are deleted from the queue when message_handler method is called.
        self.__next_message_handlers = {}
        # These are the browser instances for different users
        # (the application does not allow concurrent queries for the same user to avoid high ram usage)
        self.__browser_instances = {}

    def run_polling(self):
        self.__application.run_polling()

    def __add_next_message_handler(self, update: Update, handler):
        user_id, chat_id = update.effective_user.id, update.effective_chat.id
        if self.__next_message_handlers.get(user_id, None) is None:
            self.__next_message_handlers[user_id] = {}
        if self.__next_message_handlers[user_id].get(chat_id, None) is None:
            self.__next_message_handlers[user_id][chat_id] = queue.Queue()
        self.__next_message_handlers[user_id][chat_id].put(handler)

    async def __exec_next_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Returns true if there were callbacks in queue and one was executed"""
        user_id, chat_id = update.effective_user.id, update.effective_chat.id
        user_queues = self.__next_message_handlers.get(user_id, None)
        if user_queues is None:
            return False
        q = user_queues.get(chat_id, None)
        if q is None:
            return False
        try:
            await q.get()(update, context)
            return True
        except queue.Empty:
            return False

    async def __message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.__exec_next_handler(update, context):
            return
        await self.message_handler(update, context)

    # User defined method
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Send me a title of a picture you want to be generated"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Send me a title of a picture you want to be generated"
        )

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.user_data.get("picture_name", None) is not None:
            await update.message.reply_text(
                "You already have an executing query. Please wait for it to finish."
            )
            return

        context.user_data["picture_name"] = update.message.text
        self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
        await update.message.reply_text("How many pictures you want to generate?")

    async def __get_amount_and_return_pics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            amount = int(update.message.text)
        except ValueError:
            await update.message.reply_text("That was not a number, try again")
            self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
            return
        if amount > 3:
            await update.message.reply_text("At most 3 pictures can be generated")
            return
        if amount <= 0:
            await update.message.reply_text("Amount of pictures can not be negative or zero")
            return
        context.user_data["picture_amount"] = amount
        await self.__return_pictures(update, context)

    async def __return_pictures(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        picture_name, picture_amount = context.user_data["picture_name"], context.user_data["picture_amount"]
        instances = browsing.generate_browser_instances(picture_amount)
        await asyncio.sleep(.5)
        urls = await asyncio.gather(
            *(browsing.get_picture(b, picture_name) for b in instances)
        )
        if len(urls) == 1:
            await update.message.reply_photo(photo=urls[0], caption="Here's what was generated")
        else:
            media_list = [InputMediaPhoto(media=url) for url in urls]
            media_list[0].caption = "Here's what was generated"
        context.user_data["picture_name"] = None
        context.user_data["picture_amount"] = None
