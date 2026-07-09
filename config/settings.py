import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Source channels processing
source_channels_raw = os.getenv("SOURCE_CHANNELS", "")
SOURCE_CHANNELS = []
for ch in source_channels_raw.split(","):
    ch = ch.strip()
    if ch.lstrip('-').isdigit():
        SOURCE_CHANNELS.append(int(ch))
    elif ch:
        SOURCE_CHANNELS.append(ch)

# Target group processing
target_raw = os.getenv("TARGET_GROUP", "").strip()
TARGET_GROUP = int(target_raw) if target_raw.lstrip('-').isdigit() else target_raw