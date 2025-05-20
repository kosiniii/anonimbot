import re
from utils.other import import_functions, error_logger, menu_chats
import asyncio
from aiogram.types import Message
from typing import Any
import random
from data.redis_instance import __redis_room__, __redis_users__, redis_random, random_users, room, users
from utils.time import dateMSC
from config import ADMIN_ID
from kos_Htools.telethon_core import multi
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.types import ChatAdminRights
from telethon import TelegramClient
import logging
from config import BOT_ID
import random
from utils.other import bot
from data.celery.tasks import  add_user_to_search,  remove_user_from_search, create_private_chat


logger = logging.getLogger(__name__)
title_chat = 'Чатик знакомств'

async def time_event_user(event) -> bool:
    try:
        await asyncio.sleep(300)
        
        chat = await event.get_chat()
        if not chat:
            logger.error("Не удалось получить информацию о чате")
            return False
            
        participants = await event.client.get_participants(chat)
        
        data: dict = room.redis_data()
        chat_data = data.get(chat.id)
        
        if not chat_data:
            logger.error(f"Не найдены данные чата {chat.id} в Redis")
            return False
            
        expected_users: dict = chat_data.get('users', {})
        joined_users = [p.id for p in participants if not p.bot]
        
        if len(joined_users) < 2 and expected_users:
            logger.warning(f"Не все пользователи присоединились к чату {chat.id}")
            logger.info(f"Ожидаемые пользователи: {expected_users}")
            logger.info(f"Присоединившиеся пользователи: {joined_users}")
            return False
            
        if not all(user_id in joined_users for user_id in expected_users.keys()):
            logger.warning(f"Присоединились не те пользователи, которые ожидались")
            return False
            
        logger.info(f"Все пользователи успешно присоединились к чату {chat.id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке времени входа: {e}")
        return False


async def find_func(message: Message, user_id: int, chat_id: int | None) -> bool | None:
    try:
        if not add_user_to_search.delay(user_id).get():
            await message.answer(text='⏳ Вы уже в очереди. Пожалуйста, подождите...')
            await asyncio.sleep(1)
            return False

        partner_data = None
        if not partner_data:
            return False

        partner_id = partner_data["partner_id"]
        
        if partner_id and chat_id:
            chat = await message.bot.create_chat_invite_link(
                chat_id=chat_id,
                name=title_chat,
                member_limit=2,
            )
            
            message_id = message.message_id
            chat_message_id = message.chat.id
            list_ids_message = [message_id, chat_message_id]

            if chat:
                for partner in [user_id, partner_id]:
                    await asyncio.sleep(1)
                    await message.bot.send_message(
                        chat_id=partner,
                        text=f"🔗 Собеседник найден! Войдите в чат:\n {chat.invite_link}"
                    )
                
                remove_user_from_search.delay(user_id)
                remove_user_from_search.delay(partner_id)
                
                room_data = create_private_chat.delay([user_id, partner_id], chat.invite_link).get()
                if room_data:
                    logger.info(f'[Created]:\n {room_data}')
                    return True
                else:
                    await message.answer(error_logger(True))
                    logger.error(f'[Ошибка] при получении Json чата {chat_id}')
                    return False
                    
            else:
                logger.error(f'Чат не создался с ID: {chat_id}')
                return None
        return False
                    
    except Exception as e:
        logger.error(error_logger(False, 'find_func', e)) 
        return False


async def create_private_group() -> Any:
    try:
        client = await multi()
        await multi.get_or_switch_client(switch=True)

        group = await client.create_supergroup(
            title=title_chat,
            about="Только по приглашению",
            for_channel=False
        )
        logger.info(f'Группа создана с ID: {group.id}')

        await client.invoke(AddChatUserRequest(
            chat_id=group.id,
            user_id=BOT_ID,
        ))
        
        admin_rights = ChatAdminRights(
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=True,
            anonymous=True,
            manage_call=True,
            other=True,
            manage_topics=True,
            change_info=True,
            create_invite=True,
            delete_chat=True,
            manage_chat=True,
            manage_video_chats=True,
            can_manage_voice_chats=True,
            can_manage_chat=True,
            can_manage_channel=True
        )
        
        admin_add = await client.invoke(EditAdminRequest(
            channel=group.id,
            user_id=BOT_ID,
            admin_rights=admin_rights,
            rank="caretaker"
        ))
        
        logger.info(f"Бот-администратор добавлен в группу {group.id} с правами администратора")   
        if group and admin_add:
            return group
        else:
            logger.error('[Ошибка] функция create_private_group не вернула группу')
            return None
        
    except Exception as e:
        logger.error(error_logger(False, 'create_private_group', e))
        return None


async def delete_chat_after_timeout(message: Message, chat_id: int, data_room: dict, client: TelegramClient):
    try:
        await multi.start_clients()
        await asyncio.sleep(300)
        
        if len(data_room['users']) != 2:
            success = await message.bot.send_message(chat_id=chat_id, text=f'❌ Собеседник не присоединился за отведенное время,\n {chat_id} чат будет удален.')
            if success:
                await client.delete_dialog(chat_id)
                logger.info(f"Чат {chat_id} удален из-за отсутствия второго участника")
                return True
            else:
                logger.error(f"Ошибка при удалении чата {chat_id} после таймаута: {e}")
                return False
                
    except Exception as e:
        logger.error(error_logger(False, 'delete_chat_after_timeout', e))
        return False
    

class ProgressBar:
    def __init__(self, message_id: int, chat_id: int, message_text: str, user_id: int) -> None:
        self.message_id = message_id
        self.chat_id = chat_id
        self.user_id = user_id
        
        self.message_text = message_text
        self.running = False
        self.progress_states = ['.  ', '.. ', '...']
        self.current_state = 0

    async def start_progressbar(self):
        self.running = True
        while self.running:
            progress = self.progress_states[self.current_state]
            await bot.edit_message_text(
                text=f"{self.message_text} {progress}",
                chat_id=self.chat_id,
                message_id=self.message_id
            )
            self.current_state = (self.current_state + 1) % len(self.progress_states)
            await asyncio.sleep(1)

    def stop_progressbar(self):
        self.running = False

    async def search_random(self):
        progress_task = asyncio.create_task(self.start_progressbar())
        try:
            while True:
                size_users = len(random_users.search_online())
                if size_users > 0:
                    partner_id = random_users[random.randint(1, size_users)]
                    partner_obj = await bot.get_chat(partner_id)
                    
                    random_users.redis_data().remove(self.user_id)
                    data = random_users.redis_data().remove(partner_id)

                    self.stop_progressbar()
                    await progress_task
                    return data, partner_obj
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(error_logger(False, 'search_random', e))
            self.stop_progressbar()
            await progress_task
            return False
                
