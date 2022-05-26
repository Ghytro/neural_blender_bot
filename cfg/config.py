import json

BOT_CONFIG = None

with open("config.json") as f:
    BOT_CONFIG = json.load(f)
