import logging, src.browsing, asyncio

from collections import deque

from telegram import (
    InputMediaPhoto,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)
from telegram.constants import ChatType
from cfg.config import BOT_CONFIG

# Logging
from telegram import __version__ as TG_VER
print(f"Your current python-telegram-bot-version: {TG_VER}")

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
                self.__message_handler,
                block=False
            )
        )
        # Needed for implementation of alternative of next_step_handler, provided by telebot.
        # The key in dictionary is user id, the value is a dictionary, where the key is chat id
        # and a value is a queue with pending callbacks. This approach is used to have separate queues for
        # the same user in different chats, which allows to store private and group chats queues separately.
        # The keys are deleted from the queue when message_handler method is called.
        self.__next_message_handlers = {}

    def run_polling(self):
        self.__application.run_polling()

    def __add_next_message_handler(self, update, handler):
        user_id, chat_id = update.effective_user.id, update.effective_chat.id
        if self.__next_message_handlers.get(user_id, None) is None:
            self.__next_message_handlers[user_id] = {}
        if self.__next_message_handlers[user_id].get(chat_id, None) is None:
            self.__next_message_handlers[user_id][chat_id] = deque()
        self.__next_message_handlers[user_id][chat_id].append(handler)

    async def __exec_next_handler(self, update, context) -> bool:
        """Returns true if there were callbacks in queue and one was executed"""
        user_id, chat_id = update.effective_user.id, update.effective_chat.id
        try:
            await self.__next_message_handlers[user_id][chat_id].popleft()(update, context)
        except (KeyError, TypeError, AttributeError, IndexError) as e:
            logger.info(f"An exception occured: {e}")
            return False
        return True

    async def __message_handler(self, update, context) -> None:
        logger.info(f"Incoming message from {update.effective_user.id}, text: {update.message.text}")
        try:
            logger.info(f"Next handler queue size: {len(self.__next_message_handlers[update.effective_user.id][update.effective_chat.id])}")
        except:
            logger.info(f"Queue wasnt created yet")
        was_executed = await self.__exec_next_handler(update, context)
        if was_executed:
            logger.info("Executing queued handlers")
            return
        try:
            logger.info(f"After execution: next handler queue size: {len(self.__next_message_handlers[update.effective_user.id][update.effective_chat.id])}")
        except:
            logger.info(f"Queue wasnt created yet")
        logger.info("executing main handler")
        await self.message_handler(update, context)

    # User defined method
    async def start(self, update, context) -> None:
        await update.message.reply_text(
            "Send me a title of a picture you want to be generated"
        )

    async def help(self, update, context) -> None:
        await update.message.reply_text(
            "Send me a title of a picture you want to be generated"
        )

    async def message_handler(self, update, context) -> None:
        if update.effective_chat.type != ChatType.PRIVATE:
            return
        if context.user_data.get("picture_name", None) is not None:
            await update.message.reply_text(
                "You already have an executing query. Please wait for it to finish."
            )
            return

        context.user_data["picture_name"] = update.message.text
        self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
        await update.message.reply_text("How many pictures you want to generate?")

    async def __get_amount_and_return_pics(self, update, context) -> None:
        try:
            amount = int(update.message.text)
        except ValueError:
            await update.message.reply_text("That was not a number, try again")
            self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
            return
        if amount > 3:
            await update.message.reply_text("At most 3 pictures can be generated, try again")
            self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
            return
        if amount <= 0:
            await update.message.reply_text("Amount of pictures can not be negative or zero, try again")
            self.__add_next_message_handler(update, self.__get_amount_and_return_pics)
            return
        context.user_data["picture_amount"] = amount
        reply = await update.message.reply_text("Wait a minute, image generating (1/3)")
        context.user_data["progress_message"] = reply
        await self.__return_pictures(update, context)

    async def __return_pictures(self, update, context) -> None:
        picture_name, picture_amount = context.user_data["picture_name"], context.user_data["picture_amount"]
        instances = await src.browsing.generate_browser_instances(picture_amount)
        await asyncio.sleep(.5)
        logger.info("here")
        await context.user_data["progress_message"].edit_text("Wait a minute, image generating (2/3)")
        urls = await asyncio.gather(
            *(src.browsing.get_picture(b, picture_name) for b in instances)
        )
        await context.user_data["progress_message"].edit_text("Wait a minute, image generating (3/3)")
        if len(urls) == 1:
            await update.message.reply_photo(photo=urls[0], caption="Here's what was generated")
        else:
            media_list = [InputMediaPhoto(media=url) for url in urls]
            media_list[0].caption = "Here's what was generated"
            await update.message.reply_media_group(media=media_list)
        await context.user_data["progress_message"].delete()
        context.user_data["picture_name"] = None
        context.user_data["picture_amount"] = None
        context.user_data["progress_message"] = None
