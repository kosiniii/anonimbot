## Stack

aiogram redis postgresql telethon 

## Bot description

This bot works by using Telegram Client API to create a private group for two random anonymous users. If one of the users does not enter the chat after a while, the chat is automatically closed for everyone (deleted).

## Commands

/start /admin /stop /find

## Command description
### /start

When this command is sent, the user is added to the database (user_id, username) and immediately sent to register for entering (gender, nickname) the nickname is needed to display users in the chat, i.e. if the user enters a nickname, then this nickname will be used in the future (anonymity method), gender is needed for advertising integrations if necessary.

### /admin

This command is entered exclusively by the administrator specified in the .env file. This command also has functions for counting the number of rooms, and counting users who will be added to the search.

### /find

When a user enters this command, he starts searching for an interlocutor and is automatically added to redis and the active_users DB, the search for an interlocutor also occurs in this DB (randomly). After two users have found each other, they are sent an invitation to join a private chat. If one of the interlocutors does not enter the chat, the link to the invitation is deleted and the chat is deleted in the same way.

### /stop

Removing a user from the redis active_users database.
