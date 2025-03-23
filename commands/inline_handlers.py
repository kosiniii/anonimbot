import asyncio
import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from data.redis_instance import __redis_room__, __redis_users__

logger = logging.getLogger(__name__)
router = Router(__name__)

@router.callback_query('chacker_button')
async def button_checker_subscriber(callback: CallbackQuery, data: dict):
    try:
        if data.get('is_subscribed', False):
            await callback.answer("✅ Вы подписаны!", show_alert=True)
            await callback.message.delete(
                callback.message.chat.id,
                callback.message.message_id,
            )
            
            if 'saved_command' in data:
                saved_command = data['saved_command']
                new_message = Message(
                    message_id=callback.message.message_id + 1,
                    date=callback.message.date,
                    chat=callback.message.chat,
                    from_user=callback.message.from_user,
                    text=saved_command
                )
                from main import dp
                await dp.message.middleware.trigger(new_message, data)
                data.pop('saved_command', None)
        else:
            await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        await callback.answer("Произошла ошибка при проверке подписки", show_alert=True)