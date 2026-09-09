import random

from pyrogram import filters

from SWAGGYMUSIC import app

Yumikoo_text = [
    "hey please don't disturb me.",
    "who are you",
    "aap kon ho",
    "aap mere owner to nhi lgte ",
    "hey tum mera name kyu le rhe ho meko sone do",
    "ha bolo kya kaam hai ",
    "dekho abhi mai busy hu ",
    "hey i am busy",
    "aapko smj nhi aata kya ",
    "leave me alone",
    "dude what happend",
]


@app.on_message(filters.command(["waggy"], prefixes=["S"]))
async def swaggy_reply(_, message):
    await message.reply(random.choice(Yumikoo_text))
