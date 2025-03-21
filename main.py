import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update
import logging
from aiogram import Bot, Dispatcher, Router, F
from fastapi import FastAPI, Request
from fastapi.concurrency import asynccontextmanager
import uvicorn
from config import loadenvr
from aiogram.enums import ParseMode
from commands import router as main_router
from data.middleware.db_middle import WareBase, listclonWare, session_engine, checkerChannelWare
from data.sqlchem import create_tables
from telethon_core.clients import multi
from commands.message_bot import result
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

def get_redis(x: str = None):
    from data.redis_instance import __redis_room__, __redis_users__
    if x == 'room':
        return __redis_room__
    return __redis_users__

# env
l = loadenvr

# bot
bot = Bot(token=l('bot_token'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
webhook = l('WEB_HOOK_URL').join('/webhook')

    
@asynccontextmanager
async def lifespan(app: FastAPI):
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != webhook:
        dp.include_router(main_router)
        await bot.set_webhook(webhook)
        asyncio.run(create_tables())
        logger.info(
            f'Бот запускается...\n'
            f'INFO: {webhook_info}'
            )
    yield
    logger.info('Бот зыкрывается...')
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post('/webhook')
async def bot_setwebhook(request: Request):
    try:
        redis_users = get_redis()
        dp.message.middleware(listclonWare(redis_users.get_cashed().get('users', []), target_handler='reply_command'))
        dp.message.middleware(checkerChannelWare(l('channel_id')))
        dp.update.middleware(WareBase(session_engine))
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
        return {'status': 'ok'}
    
    except Exception as e:    
        logger.error(f'webhook ошибка: {e}')
        return {'status': 'error'}


async def start_with_telethon():
    global result
    result = input('start telethon? [yes/no]:').strip().lower()
    
    if result == 'yes':
        logger.info('Происходит запуск с telethon...')
        await multi.start_clients()
        
    if result == 'no':
        logger.info('Происходит запуск без telethon...')
        await multi.stop_clients()

    uvicorn.run(app, host=l('WEB_HOOK_HOST'), port=int(l('WEB_HOOK_PORT')))
    
if __name__ == "__main__":
    asyncio.run(start_with_telethon())