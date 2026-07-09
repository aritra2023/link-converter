import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from config.settings import API_ID, API_HASH

# ---------------- CONFIGURATION ----------------
SOURCE_CHANNEL = -1002849937766
TARGET_CHANNEL = -1004427866910
# -----------------------------------------------

client = TelegramClient('user_session', API_ID, API_HASH)

async def main():
    print("🔄 Saari chats load kar raha hu taaki ID mil sake... Please wait.")
    
    # limit=None se teri saari chats load hongi, toh koi channel miss nahi hoga
    await client.get_dialogs(limit=None) 
    print("✅ Chats loaded!\n")

    print("📊 Channel ko scan kar raha hu (Images aur Videos count karne ke liye)...")
    
    # Error handling taaki agar ab bhi ID galat ho toh script crash na ho aur reason bataye
    try:
        entity = await client.get_entity(SOURCE_CHANNEL)
    except Exception as e:
        print(f"\n❌ ERROR: Channel nahi mila! Reason: {e}")
        print("👉 Please check: Kya tu sach mein us ID wale channel ka member hai?")
        return

    # Count karne ka logic
    total_photos = 0
    total_videos = 0
    
    async for msg in client.iter_messages(SOURCE_CHANNEL):
        if msg.photo:
            total_photos += 1
        elif msg.video:
            total_videos += 1

    # Total dikhane ka format
    print("=====================================")
    print(f"📷 Total Images Found : {total_photos}")
    print(f"🎥 Total Videos Found : {total_videos}")
    print(f"📦 Total Files to Send: {total_photos + total_videos}")
    print("=====================================\n")

    if (total_photos + total_videos) == 0:
        print("❌ Is channel mein koi image ya video nahi hai. Script stop ho rahi hai.")
        return

    print(f"🚀 Transfer shuru ho raha hai...\n")
    msg_count = 0 
    
    # Ab file bhejne ka main logic
    async for message in client.iter_messages(SOURCE_CHANNEL, reverse=True):
        if message.photo or message.video:
            try:
                # Sirf media bhej rahe hain (No caption, no forward tag)
                await client.send_message(TARGET_CHANNEL, file=message.media)
                
                msg_count += 1
                print(f"✅ Sent Media ID: {message.id} | Total Sent: {msg_count} out of {total_photos + total_videos}")
                
                # Har 50 message ke baad 5 second ka gap
                if msg_count % 50 == 0:
                    print(f"⏳ 50 files bhej di! 5 second ka break le raha hu taaki account safe rahe...")
                    await asyncio.sleep(5)
                else:
                    # Normal safety gap 
                    await asyncio.sleep(1)
                    
            except FloodWaitError as e:
                print(f"⚠️ Telegram limit reached! Waiting for {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"❌ Error sending message {message.id}: {e}")

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
        print("🎉 Sab kuch successfully transfer ho gaya!")