import asyncio
import logging
from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from commands.states.state import Main_menu, Menu_chats, create_room_into_tg, okno
from data.sqlchem import User
from keyboards.reply_button import chats, main_commands
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils import markdown
from data.redis_instance import __redis_room__, __redis_users__
from keyboards.lists_command import command_chats, main_command_list
from utils.db_work import create_private_group, find_func,  set_users_active

text_chats = markdown.text(
    f'Инструкцию не придумал пока в падлу'
    f'{markdown.hblockquote(f'{markdown.hbold('1')} Создание отдельного чата в телеграмм')}\n'
    f'{markdown.hblockquote(f'{markdown.hbold('2')} Анонимная переписка на сайте')}\n'
    f'Перейдите в меню и выберите для себя удобный вариант ;)'
)
logger = logging.getLogger(__name__)
router = Router(__name__)
result = ''

async def main_menu(message: Message, state: FSMContext, db_session: AsyncSession):
    await state.set_state(Main_menu.main)
    user_id = message.from_user.id
    name = await db_session.scalar(select(User.full_name).where(User.user_id == user_id))
    if name:
        await menu_chats(f'Добро пожаловать, {name}', message, state)
    else:
        await message.answer('Пройдите регистрацию')
        logger.error('Ошибка пользователь прошел без регистрации') 

@router.message(F.text == '🥷 Система чатов', StateFilter(Menu_chats.limit_alert))
async def menu_chats(text: str, message: Message, state: FSMContext):
    await message.answer(
        text=f"{text}\n\n {text_chats}",
            reply_markup=chats()
            )
    await state.set_state(Menu_chats.system_chats)

@router.message(F.text.in_(command_chats), StateFilter(Menu_chats.system_chats))
async def system_chats(message: Message, state: FSMContext):
    text = message.text
    if text == '1':
        if result == 'no':
            await message.answer('Не работает по системным обстоятельствам')
            logger.info('Нет запуска telethon')
            return await system_chats(message, state)
        else:
            await message.answer(
                text='/find - искать собеседника\n\n /stop - остановка поиска\n\n'
                'После того как нашелся собеседник, бот вам отправит пригласительную ссылку в чат\n',
                reply_markup=main_commands()
                )
            await state.get_state(create_room_into_tg.main)
    elif text == '2':
        pass

@router.message(
    F.text.in_(main_command_list) or Command(commands=['find',  'stop'], prefix='/'),
    StateFilter(create_room_into_tg.main)
    )
async def reply_command(message: Message, state: FSMContext, db_session: AsyncSession):
    user_id = message.from_user.id
    text = message.text
    if text == '/find':
        chat = await create_private_group()
        chat_id = chat.id
        ff = await find_func(message, user_id, chat_id)
        if not ff:
            logger.info(f'Ошибка при поиске собеседника: {user_id} или Поиск уже идет')
            return False

    elif text == '/stop':
        if user_id in set_users_active:
            set_users_active.discard(user_id)
            __redis_users__.cashed(key='active_users', data=list(set_users_active), ex=0)
            await message.answer(text='🛑 Вы прекратили поиск')
        else:
            await message.answer(text='🚀 Вы еще не в поиске нажмите скорее /find')
        
    elif text == "⬅️ Вернуться в выбору":
        await main_menu(message, state, db_session)