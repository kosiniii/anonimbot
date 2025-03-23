from aiogram import F, Router
from data.sqlchem import User as user_sql
from sqlalchemy import select
from aiogram.types import Message
from telethon import events
from telethon.tl.types import Channel, User, ChatInviteExported
from telethon.tl.functions.messages import AddChatUserRequest
import logging
from utils.date_time_moscow import date_moscow
from utils.db_work import time_event_user, list_ids_message
import asyncio
from data.redis_instance import __redis_room__, __redis_users__
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from config import loadenvr
from telethon_core.clients import multi
from aiogram.utils import markdown
from utils.db_work import delete_chat_after_timeout
from utils.db_work import find_func

logger = logging.getLogger(__name__)
l = loadenvr

async def setup_handlers(client):
    @client.on(events.ChatAction)
    async def handle_chat_action(event):
        try:
            if event.is_group or event.is_channel:
                chat = await event.get_chat()
                if isinstance(chat, Channel):
                    chat_id = chat.id
                    data = __redis_room__.get_cashed()
                    if f'room-{chat_id}' not in data:
                        return
                    
                    if event.user_joined:
                        user = await event.get_user()
                        if isinstance(user, User):
                            logger.info(f"Пользователь {user.id} присоединился к чату {chat_id}")
                            data_room = data[f'room-{chat_id}']
                            data_room['date'] = date_moscow('time_now')
                            if 'users' not in data_room:
                                data_room['users'] = []
                            if user.id not in data_room['users']:
                                data_room['users'].append(user.id)
                            __redis_room__.cashed(key='rooms', data=data, ex=0)
                            
                            time_event = await time_event_user(event)
                            if not time_event:
                                if len(list_ids_message) >= 2:
                                    chat_message_id, message_id = list_ids_message[-2:]
                                    try:
                                        await client.delete_messages(chat_message_id, message_id)
                                        await client.send_message(
                                            chat_id,
                                            "❌ Один из пользователей не успел присоединиться к чату. Чат будет удален."
                                        )
                                        logger.info(f'Удаление приглашения и чата...\n ID:{chat_id}')
                                        list_ids_message.clear()
                                        await client.delete_dialog(chat_id)
                                    except Exception as e:
                                        logger.error(f"Ошибка при удалении сообщения/чата: {e}")
                                else:
                                    logger.error(f'Недостаточно элементов в списке {list_ids_message}')
                                    return
                            else:
                                asyncio.create_task(__redis_room__.check_inactivity(chat_id))
                    
                    elif event.user_left:
                        user = await event.get_user()
                        if isinstance(user, User):
                            logger.info(f"Пользователь {user.id} покинул чат {chat_id}")
                            data_room = data[f'room-{chat_id}']
                            data_room['date'] = date_moscow('time_now')
                            if 'users' in data_room:
                                if user.id in data_room['users']:
                                    data_room['users'].remove(user.id)
                                    logger.info(f"Пользователь {user.id} удален из списка пользователей чата {chat_id}")
                                    
                                    if len(data_room['users']) == 0:
                                        logger.info(f'Все юзеры вышли, ведется удаление чата..\n id: {chat_id}')
                                        await client.delete_dialog(chat_id)
                                        return

                                    if multi.bot_client:
                                        await multi.bot_client.send_message(
                                            chat_id,
                                            f'❗️ Чат будет удален через {markdown.hbold('5')} минут,\n если собеседник не присоединится. ❗️'
                                        )
                                    
                                    asyncio.create_task(delete_chat_after_timeout(
                                        chat_id=chat_id,
                                        data_room=data_room,
                                        client=client
                                    ))
                                    
                            __redis_room__.cashed(key='rooms', data=data, ex=0)
                            
        except Exception as e:
            logger.error(f"Ошибка в обработчике событий чата: {e}")

    @client.on(events.NewMessage)
    async def handle_new_message(event, db_session: AsyncSession):
        try:
            if event.is_group or event.is_channel:
                chat = await event.get_chat()
                user_id = event.sender_id
                if isinstance(chat, Channel):
                    chat_id = chat.id
                    data = __redis_room__.get_cashed()
                    message_id = event.message.id
                    if f'room-{chat_id}' not in data:
                        return
                    
                    data[f'room-{chat_id}']['date'] = date_moscow('time_now')
                    __redis_room__.cashed(key='rooms', data=data, ex=0)
                    logger.info(f"Обновлено время активности в чате {chat_id}")
            
                    name = await db_session.execute(select(user_sql.full_name).where(user_sql.user_id == user_id)) 
                    if name and multi.bot_client:
                        try:
                            await multi.bot_client.delete_messages(chat_id, message_id)
                        except Exception as e:
                            logger.error(f"Ошибка при удалении сообщения: {e}")

                        try:
                            await multi.bot_client.send_message(
                                chat_id,
                                f"{name}:\n {event.message.text}",
                            )
                        except Exception as e:
                            logger.error(f"Ошибка при отправке переделанного сообщения: {e}")
                    else:
                        logger.error(f'Не найдено имя для пользователя {user_id}')
                    
        except Exception as e:
            logger.error(f"Ошибка при обработке нового сообщения: {e}")