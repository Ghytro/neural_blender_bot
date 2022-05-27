import json

BOT_CONFIG = None

with open("cfg/config.json") as f:
    BOT_CONFIG = json.load(f)
