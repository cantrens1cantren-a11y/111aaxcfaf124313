from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import uuid
from datetime import datetime
import logging
import os  # ДОБАВИЛ ЭТУ СТРОЧКУ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TarMAR")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRegister(BaseModel):
    username: str
    password: str

class LoginData(BaseModel):
    username: str
    password: str

class MessageData(BaseModel):
    sender: str
    receiver: str
    text: str

def init_db():
    try:
        conn = sqlite3.connect('tarmar.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id TEXT PRIMARY KEY, 
                      username TEXT UNIQUE, 
                      password TEXT, 
                      created_at TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                     (id TEXT PRIMARY KEY,
                      sender TEXT,
                      receiver TEXT,
                      text TEXT,
                      timestamp TEXT)''')
        
        # Создаем тестовых пользователей если их нет
        test_users = ['alexey', 'maria', 'ivan']
        for username in test_users:
            c.execute("SELECT username FROM users WHERE username = ?", (username,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (id, username, password, created_at) 
                          VALUES (?, ?, ?, ?)''',
                         (str(uuid.uuid4()), username, '123456', datetime.now().isoformat()))
                logger.info(f"✅ Создан пользователь: {username}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")

init_db()

def get_db_connection():
    return sqlite3.connect('tarmar.db', check_same_thread=False)

@app.get("/")
async def root():
    return {"status": "success", "message": "TarMAR Messenger API"}

@app.post("/register")
async def register(user: UserRegister):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        user_id = str(uuid.uuid4())
        c.execute('''INSERT INTO users (id, username, password, created_at) 
                    VALUES (?, ?, ?, ?)''',
                 (user_id, user.username, user.password, datetime.now().isoformat()))
        conn.commit()
        
        return {
            "status": "success",
            "user_id": user_id,
            "username": user.username
        }
        
    except sqlite3.IntegrityError:
        return {"status": "error", "message": "Имя пользователя уже занято"}
    except Exception as e:
        return {"status": "error", "message": "Ошибка сервера"}
    finally:
        conn.close()

@app.post("/login")
async def login(login_data: LoginData):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''SELECT id, username FROM users 
                     WHERE username = ? AND password = ?''', 
                 (login_data.username, login_data.password))
        
        user = c.fetchone()
        
        if user:
            user_id, username = user
            return {
                "status": "success",
                "user_id": user_id,
                "username": username
            }
        else:
            return {"status": "error", "message": "Неверные данные"}
            
    except Exception as e:
        return {"status": "error", "message": "Ошибка сервера"}
    finally:
        conn.close()

@app.get("/users")
async def get_users():
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''SELECT id, username FROM users''')
        users = []
        for row in c.fetchall():
            user_id, username = row
            users.append({
                "id": user_id,
                "username": username,
                "avatar": "👤"
            })
        
        return {"status": "success", "users": users}
        
    except Exception as e:
        return {"status": "error", "message": "Ошибка сервера"}
    finally:
        conn.close()

@app.get("/search/{username}")
async def search_user(username: str):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        search_pattern = f"%{username}%"
        c.execute('''SELECT id, username FROM users 
                     WHERE username LIKE ?''', (search_pattern,))
        
        users = []
        for row in c.fetchall():
            user_id, username = row
            users.append({
                "id": user_id,
                "username": username,
                "avatar": "👤"
            })
        
        return {"status": "success", "users": users}
        
    except Exception as e:
        return {"status": "error", "message": "Ошибка поиска"}
    finally:
        conn.close()

@app.get("/messages/{user1}/{user2}")
async def get_messages(user1: str, user2: str):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''SELECT sender, receiver, text, timestamp 
                     FROM messages 
                     WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
                     ORDER BY timestamp''', 
                  (user1, user2, user2, user1))
        
        messages = []
        for row in c.fetchall():
            sender, receiver, text, timestamp = row
            messages.append({
                "sender": sender,
                "receiver": receiver,
                "text": text,
                "time": timestamp[11:16]  # Берем только время
            })
        
        return {"status": "success", "messages": messages}
        
    except Exception as e:
        return {"status": "error", "message": "Ошибка загрузки сообщений"}
    finally:
        conn.close()

@app.post("/send_message")
async def send_message(message: MessageData):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        c.execute('''INSERT INTO messages (id, sender, receiver, text, timestamp) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (message_id, message.sender, message.receiver, message.text, timestamp))
        
        conn.commit()
        
        return {"status": "success", "message_id": message_id}
        
    except Exception as e:
        return {"status": "error", "message": "Ошибка отправки"}
    finally:
        conn.close()

@app.get("/chats/{username}")
async def get_user_chats(username: str):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Находим всех пользователей, с которыми есть переписка
        c.execute('''SELECT DISTINCT 
                    CASE WHEN sender = ? THEN receiver ELSE sender END as partner
                    FROM messages 
                    WHERE sender = ? OR receiver = ?''',
                  (username, username, username))
        
        partners = [row[0] for row in c.fetchall()]
        
        chats = []
        for partner in partners:
            # Получаем информацию о пользователе
            c.execute('''SELECT id, username FROM users WHERE username = ?''', (partner,))
            user_data = c.fetchone()
            
            if user_data:
                user_id, partner_username = user_data
                
                # Получаем последнее сообщение
                c.execute('''SELECT text FROM messages 
                           WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
                           ORDER BY timestamp DESC LIMIT 1''',
                          (username, partner, partner, username))
                last_msg = c.fetchone()
                
                last_message = last_msg[0] if last_msg else "Нет сообщений"
                
                chats.append({
                    "user": {
                        "id": user_id,
                        "username": partner_username,
                        "avatar": "👤"
                    },
                    "last_message": last_message
                })
        
        return {"status": "success", "chats": chats}
        
    except Exception as e:
        return {"status": "error", "message": "Ошибка загрузки чатов"}
    finally:
        conn.close()

# ИЗМЕНИЛ ЭТУ ЧАСТЬ ДЛЯ RAILWAY
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 TarMAR Server запущен на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)