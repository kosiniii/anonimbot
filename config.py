import logging
from typing import Union
from environs import Env
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)

def loadenvr(x: str, path: str | None = None) -> str:
    env: Env = Env()
    env.read_env(path=path)

    bot_username = env('BOT_USERNAME')
    ADMIN_ID = env('ADMIN_ID')
    db_url = env('BD_URL_POSTGRES')
    bot_token = env('BOT_TOKEN')
    bot_token_client = env('BOT_TOKEN_CLIENT')
    webhook_url = env('WEB_HOOK_URL')
    port = env("WEB_HOOK_PORT")
    host = env('WEB_HOOK_HOST')
    channel_id = env('CHANNEL_ID')
    
    list_env = {
        'bot_username': bot_username,
        'ADMIN_ID': ADMIN_ID,
        'bot_token': bot_token,
        'webhook_url': webhook_url,
        'port': port,
        'host': host,
        'db_url': db_url,
        'channel_id': channel_id,
        'bot_token_client': bot_token_client
    }
    if list_env:
        for keys in list_env.keys():
            if x == keys:
                return list_env.get(x)

        raise ValueError('Такого элемента нет в списке!')
    return ''



