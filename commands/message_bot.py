from email import message
import logging
import stat
from sqlalchemy import select
from commands.state import Main_menu, Menu_chats, find_groups, Admin_menu, random_user, Back
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils import markdown
from data.redis_instance import __redis_room__, __redis_users__, RAccess, users, random_users, room, redis_random, redis_random_waiting
from keyboards.lists_command import command_chats, main_command_list
from utils.db_work import create_private_group, find_func, ProgressBar
from utils.other import error_logger, import_functions, menu_chats, bot
from aiogram import F, Bot, Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from data.sqlchem import User
from keyboards.button_names import chats_bt, main_commands_bt, search_again_bt
from keyboards.reply_button import admin_command, chats, main_commands, back_bt
from sqlalchemy.ext.asyncio import AsyncSession
from utils.dataclass import BasicUser
from keyboards.inline_buttons import go_tolk
from utils.other import remove_invisible, kats_emodjes, count_meetings
from data.utils import CreatingJson
from data.sql_instance import userb

pseudonym = 'psdn.'
anonim = 'Anonim'
logger = logging.getLogger(__name__)
router = Router(__name__)

text_instructions = markdown.text(
    '/find - искать собеседника(ов)\n\n'
    "/stop - выйти из поиска\n\n"
    f'⏭️ {markdown.blockquote("После того как нашелся собеседник, бот вам отправит пригласительную ссылку в чат")}\n',
    )

@router.message(F.text.in_(command_chats), StateFilter(Menu_chats.system_chats))
async def system_chats(message: Message, state: FSMContext):
    text = message.text
    if text == chats_bt.one:
        await message.answer(
            text=
            f'Сейчас в поиске {users.search_online()}'
            f'Введите с каким кол-во участников хотите начать общение [мин от {markdown.hpre('3')}]'
        )
        await state.set_state(find_groups.enter_users)

    elif text == chats_bt.two:
        await message.answer(text=text_instructions, reply_markup=main_commands())
        await state.set_state(random_user.main)


@router.message(
    F.text.in_(main_command_list) or Command(commands=['find',  'stop'], prefix='/'),
    StateFilter(find_groups.main)
    )
async def reply_command(message: Message, state: FSMContext, db_session: AsyncSession):
    user_id = message.from_user.id
    text = message.text
    if text == main_commands_bt.find:
        chat = await create_private_group()
        chat_id = chat.id
        ff = await find_func(message, user_id, chat_id)
        if not ff:
            logger.info(f'Ошибка при поиске собеседника: {user_id} или Поиск уже идет')
            return False
            
    elif text == main_commands_bt.stop:
        data: list = users.redis_data()
        if user_id in data and data:
            data.remove(user_id)
            __redis_users__.cashed(key='active_users', data=data, ex=0)
            await message.answer(text='🛑 Вы прекратили поиск')
        else:
            await message.answer(text='🚀 Вы еще не в поиске нажмите скорее /find')
        
    elif text == main_commands_bt.back:
        await menu_chats(message, state)


@router.message(
    F.text.in_(main_command_list) or Command(commands=['find',  'stop'] or search_again_bt.search, prefix='/'),
    StateFilter(random_user.main, random_user.search_again)
    )
async def send_random_user(message: Message, state: FSMContext):
    user = BasicUser.from_message(message)
    text = message.text
    message_text = 'Начался поиск🔍'
    try:
        if not remove_invisible(user.full_name):
            await state.set_state(random_user.if_null)
            await message.answer(
                text=f'Я вижу у тебя невидимый никнейм. Прошу ввести свой псевдоним 📝',
                reply_markup=back_bt()
                )

        if text == main_commands_bt.find:
            data = random_users.redis_data()
            random_users.redis_cashed(data.append[user.user_id])

            pb = ProgressBar(redis_random, message_id, chat_id, message_text, user.user_id)
            message_obj = await message.answer(message_text)
            chat_id = message_obj.chat.id
            message_id = message_obj.message_id
            

            data, partner_obj = await pb.search_random()
            partner_id = partner_obj.id
            partner = await userb.get_one(User.user_id == partner_id)
            if not partner:
                logger.error(f'[Ошибка] не найден {partner_id} в базе')
                return False

            partner_full_name = partner.full_name
            users_party = [user.user_id, partner_id]
            # {num_meet: {users: {user_id: {skip_users: [int], tolk_users: [int], ready: bool}}}, created: datetime}
            save = random_users.redis_cashed(data, None)
            
            waiting_data = redis_random_waiting.redis_data()

            users_data = {}
            for us in users_party:
                new_data = waiting_data.get('users', {}).get(us, {})
                if new_data:
                    users_data[us] = {
                        'skip_users': new_data.get('skip_users', 1),
                        'tolk_users': new_data.get('tolk_users', 1)
                    }

            if len(users_data) == 2:
                new_data = CreatingJson.random_waiting({'users': users_data}, count_meetings())
            else:
                logger.error(f'[Ошибка] Недостаточно данных для обоих пользователей: {users_data}')
                return False

            if save and new_data:
                for user_ids, names in zip(users_party, [user.full_name, partner_full_name]):
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    message_send = await bot.send_message(
                        text=
                        f'Начать общение с {markdown.hpre(names)} .?\n Если в конце никнейма {markdown.hpre(pseudonym)} - это всевдоним',
                        chat_id=user_ids,
                        reply_markup=go_tolk()
                    )
                    await bot.edit_message_reply_markup(
                        chat_id=user_ids,
                        message_id=message_send.message_id,
                        reply_markup=go_tolk(message_send.message_id)
                    )

            else:
                logger.error('[Ошибка] не изменились Redis данные random_users')
                return False
        
        if text == main_commands_bt.stop:
            data = random_users.redis_data()
            if data:
                data.remove(user.user_id)
                random_users.redis_cashed(data=data, ex=None)
                logger.info(f'{user.user_id} вышел из поиска')
                await message.answer(
                    text='⛔️ Вы вышли из поиска.\n Нажмите /find чтобы возобновить поиск или на кнопки в панели ниже.',
                    reply_markup=main_commands()
                    )
                await state.set_state(random_user.search_again)
        
        if text == main_commands_bt.back:
            await state.set_state(Back.main_menu)


    except Exception as e:
        logger.error(error_logger(False, 'send_random_user', e))


@router.message(F.text, StateFilter(random_user.if_null))
async def saved_name_user(message: Message, state: FSMContext):
    user = BasicUser.from_message(message)
    data = await state.get_data()
    text: str = data.get('name')
    if not text:
        text = message.text

    if not remove_invisible(text):
        await message.answer(f'Я виду что вы опять ввели невидимый никнейм, прошу повторить попытку снова 🔄')
        await state.set_state(random_user.again_name)

    save = await userb.update(User.user_id == user.user_id, {'full_name': text.join(f" {pseudonym}")})
    if save:
        await state.set_state(random_user.main)
        await message.answer(
            text=f'👌 Успешно сохранено.\n\n Ваш текущий псевдоним: {text}\n Теперь у вас есть доступ к поиску.',
            reply_markup=main_commands()
            )
    else:
        logger.info(f'[Ошибка] При сохранении псевдонима {text} юзера {user.user_id}, произошла ошибка')
        await message.answer(error_logger(True))

@router.message(F.text, StateFilter(random_user.again_name))
async def again_enter_name(message: Message, state: FSMContext):
    await state.set_data({'name': message.text})
    await state.set_state(random_user.if_null)

@router.message(F.text == main_commands_bt.back, StateFilter(Back.main_menu))
async def back_main_menu(message: Message, state: FSMContext):
    await menu_chats(message, state, edit=True)