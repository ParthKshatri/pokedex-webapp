import sqlite3
import hashlib
import uuid
import os

DB_NAME = "pokedex.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
        )
    ''')
    
    # Sessions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # User Pokemon Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_pokemon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            pokemon_name TEXT NOT NULL,
            location TEXT NOT NULL, -- 'team' or 'storage'
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    
    # Use PBKDF2 for secure hashing
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def register_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # Check if user exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            return False, "Username already exists"
        
        user_id = str(uuid.uuid4())
        password_hash, salt = hash_password(password)
        
        c.execute("INSERT INTO users (id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
                  (user_id, username, password_hash, salt))
        
        conn.commit()
        return True, "User registered successfully"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            return None, "Invalid username or password"
        
        user_id, stored_hash, salt = user
        
        # Verify password
        check_hash, _ = hash_password(password, salt)
        
        if check_hash != stored_hash:
            return None, "Invalid username or password"
        
        # Create user_id session
        token = str(uuid.uuid4())
        c.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        conn.commit()
        
        return token, None
    finally:
        conn.close()

def get_user_by_token(token):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT u.id, u.username 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        ''', (token,))
        return c.fetchone() # (id, username) or None
    finally:
        conn.close()

def logout_user(token):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

# --- Pokemon Operations ---

def add_pokemon(user_id, pokemon_name, location):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check team limit if location is team
    if location == 'team':
        c.execute("SELECT COUNT(*) FROM user_pokemon WHERE user_id = ? AND location = 'team'", (user_id,))
        count = c.fetchone()[0]
        if count >= 6:
            location = 'storage' # Auto-move to storage if team full, logic is typically handled in frontend but fallback here
    
    c.execute("INSERT INTO user_pokemon (user_id, pokemon_name, location) VALUES (?, ?, ?)",
              (user_id, pokemon_name, location))
    conn.commit()
    conn.close()

def remove_pokemon(user_id, pokemon_name, location):
    # This removes ONE instance of the pokemon from that location
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Find one ID to delete (limit 1)
    c.execute('''
        SELECT id FROM user_pokemon 
        WHERE user_id = ? AND pokemon_name = ? AND location = ?
        LIMIT 1
    ''', (user_id, pokemon_name, location))
    
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM user_pokemon WHERE id = ?", (row[0],))
        conn.commit()
    
    conn.close()

def get_user_pokemon(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT pokemon_name, location FROM user_pokemon WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    
    team = [r[0] for r in rows if r[1] == 'team']
    storage = [r[0] for r in rows if r[1] == 'storage']
    
    conn.close()
    return team, storage
