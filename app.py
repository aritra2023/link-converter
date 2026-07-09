import asyncio
import os
import time
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import uvicorn
from config.settings import API_ID, API_HASH

# Restricted content ke liye temporary folder
if not os.path.exists("temp_downloads"):
    os.makedirs("temp_downloads")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global client object
client = TelegramClient('user_session', API_ID, API_HASH)

state = {
    "logged_in": False, "user": "", "phone": "", "phone_code_hash": "",
    "is_running": False, "sent": 0, "total": 0, "status": "Ready to launch...",
    "wait_until": 0
}

def parse_chat_id(val):
    val = val.strip()
    if "t.me/c/" in val: return int("-100" + val.split("t.me/c/")[1].split("/")[0])
    if "t.me/" in val: return val.split("t.me/")[1].split("/")[0]
    if val.startswith("@"): return val
    if val.lstrip("-").isdigit(): return int(val)
    return val

@app.on_event("startup")
async def startup_event():
    global client
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        state["logged_in"] = True
        state["user"] = f"{me.first_name} (@{me.username if me.username else me.id})"

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return JSONResponse(state)

@app.post("/api/send_otp")
async def send_otp(phone: str = Form(...)):
    global client
    try:
        if not client.is_connected():
            await client.connect()
            
        state["phone"] = phone
        res = await client.send_code_request(phone)
        state["phone_code_hash"] = res.phone_code_hash
        return {"message": "OTP Sent"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.post("/api/verify_otp")
async def verify_otp(code: str = Form(...), password: str = Form(None)):
    global client
    try:
        if not client.is_connected():
            await client.connect()
            
        await client.sign_in(state["phone"], code, phone_code_hash=state["phone_code_hash"])
    except SessionPasswordNeededError:
        if not password: return JSONResponse({"error": "2FA Required"}, status_code=400)
        await client.sign_in(password=password)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    
    me = await client.get_me()
    state["logged_in"] = True
    state["user"] = f"{me.first_name}"
    return {"message": "Success"}

@app.post("/api/logout")
async def logout_account():
    global client
    try:
        await client.log_out() 
    except Exception:
        pass 
    
    client = TelegramClient('user_session', API_ID, API_HASH)
    await client.connect()
    
    state["logged_in"] = False
    state["user"] = ""
    state["phone"] = ""
    state["phone_code_hash"] = ""
    return {"message": "Logged out successfully"}

@app.post("/api/clone_channel")
async def clone_channel(source_id: str = Form(...), clone_type: str = Form(...)):
    global client
    try:
        await client.get_dialogs() 
        src = parse_chat_id(source_id)
        
        try:
            entity = await client.get_entity(src)
            new_name = f"{getattr(entity, 'title', 'New Entity')} copy"
        except Exception:
            new_name = "Cloned Entity"
        
        new_chat_ids = []
        msg_text = ""
        
        # 🚀 FIX: Ab dono IDs collect hongi list mein
        if clone_type in ["channel", "both"]:
            res_ch = await client(functions.channels.CreateChannelRequest(
                title=f"{new_name}", 
                about="Cloned Auto Channel", 
                megagroup=False 
            ))
            new_chat_ids.append(f"-100{res_ch.chats[0].id}")
            msg_text = "Channel Cloned!"
            
        if clone_type in ["group", "both"]:
            res_gr = await client(functions.channels.CreateChannelRequest(
                title=f"{new_name}", 
                about="Cloned Auto Group", 
                megagroup=True 
            ))
            new_chat_ids.append(f"-100{res_gr.chats[0].id}")
            if clone_type == "group":
                msg_text = "Group Cloned!"
            else:
                msg_text = "Channel & Group Cloned!"
            
        # Comma se jod kar return karenge
        return {"success": True, "new_id": ",".join(new_chat_ids), "message": msg_text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

async def background_transfer(src_id, tgt_id, filters, keep_cap, keep_fwd, delay, batch_size, batch_gap):
    global client
    state["is_running"] = True
    state["status"] = "Checking Permissions..."
    state["wait_until"] = 0 
    state["sent"] = 0
    state["total"] = 0
    
    try:
        await client.get_dialogs()
        src = parse_chat_id(src_id)
        
        # 🚀 FIX: Multiple targets ko handle karne ka logic
        targets = [parse_chat_id(t) for t in tgt_id.split(",") if t.strip()]
        
        try:
            src_entity = await client.get_entity(src)
            is_restricted = getattr(src_entity, 'noforwards', False)
        except Exception:
            is_restricted = False
            
        state["status"] = "Scanning Channel Data..."
        
        async for msg in client.iter_messages(src):
            if not state["is_running"]: break
            if ("img" in filters and msg.photo) or ("vid" in filters and msg.video) or ("aud" in filters and msg.audio) or ("doc" in filters and msg.document) or ("txt" in filters and msg.text and not msg.media):
                state["total"] += 1
                
        state["status"] = f"Forwarding {state['total']} files..."
        
        count = 0
        async for message in client.iter_messages(src, reverse=True):
            if not state["is_running"]: break
                
            send_this = False
            if "img" in filters and message.photo: send_this = True
            elif "vid" in filters and message.video: send_this = True
            elif "aud" in filters and message.audio: send_this = True
            elif "doc" in filters and message.document: send_this = True
            elif "txt" in filters and message.text and not message.media: send_this = True
            
            if send_this:
                try:
                    if keep_fwd and not is_restricted:
                        for tgt in targets:
                            await client.forward_messages(tgt, message.id, src)
                    else:
                        cap = message.text if keep_cap else None
                        
                        if is_restricted and message.media:
                            state["status"] = f"Downloading (Restricted) {count+1}/{state['total']}..."
                            temp_file = await client.download_media(message, file="temp_downloads/")
                            
                            state["status"] = f"Uploading {count+1}/{state['total']}..."
                            for tgt in targets:
                                await client.send_message(tgt, message=cap, file=temp_file)
                            
                            if temp_file and os.path.exists(temp_file):
                                os.remove(temp_file)
                        else:
                            for tgt in targets:
                                await client.send_message(tgt, message=cap, file=message.media)
                        
                    count += 1
                    state["sent"] = count
                    
                    if count % batch_size == 0:
                        state["wait_until"] = int(time.time()) + batch_gap
                        state["status"] = "Batch Rest..."
                        await asyncio.sleep(batch_gap)
                        state["wait_until"] = 0 
                    else:
                        state["status"] = f"Sent {count} of {state['total']}"
                        await asyncio.sleep(delay)
                        
                except FloodWaitError as e:
                    state["wait_until"] = int(time.time()) + e.seconds
                    state["status"] = "Telegram Limit Reached!"
                    await asyncio.sleep(e.seconds)
                    state["wait_until"] = 0 
                except Exception as e: pass
                    
        state["status"] = "Transfer Completed Successfully!"
    except Exception as e:
        state["status"] = f"Error: {str(e)}"
    finally:
        state["is_running"] = False
        state["wait_until"] = 0

@app.post("/api/start")
async def start_transfer(
    source_id: str = Form(...), target_id: str = Form(...),
    filter_type: str = Form(...), 
    keep_caption: bool = Form(False), keep_forward_tag: bool = Form(False),
    delay: float = Form(...), batch_size: int = Form(...), batch_gap: int = Form(...)
):
    if state["is_running"]: 
        return JSONResponse({"error": "Already running!"}, status_code=400)
        
    asyncio.create_task(background_transfer(
        source_id, target_id, filter_type.split(','), 
        keep_caption, keep_forward_tag, delay, batch_size, batch_gap
    ))
    return {"message": "Started!"}

@app.post("/api/stop")
async def stop_transfer():
    state["is_running"] = False
    state["status"] = "Stopped by User"
    state["wait_until"] = 0
    return {"message": "Stopped!"}

if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, access_log=False)
