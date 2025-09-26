"""
Database module for ShadowX Bot
Handles all database operations
"""

import sqlite3
import logging
from datetime import datetime
from config import DATABASE_NAME, UNIVERSITIES
from utils.db_pool import get_db_connection

# Note: All DB access goes through utils.db_pool.get_db_connection()

# Initialize database
def init_db():
    """Initialize the database and create required tables"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            # Performance-oriented pragmas (safe defaults for many-read, some-write bots)
            try:
                cursor.execute('PRAGMA journal_mode=WAL')
                cursor.execute('PRAGMA synchronous=NORMAL')
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.execute('PRAGMA temp_store=MEMORY')
                # Negative value means KB; here ~64MB cache
                cursor.execute('PRAGMA cache_size=-65536')
            except sqlite3.Error:
                pass
            
            # Users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                university TEXT,
                language TEXT DEFAULT 'ru',
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Migration: ensure 'language' column exists (for older DB versions)
            try:
                cursor.execute("PRAGMA table_info(users)")
                user_columns = [row[1] for row in cursor.fetchall()]
                if 'language' not in user_columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            except sqlite3.Error as e:
                logging.warning(f"Users table migration check failed: {e}")
            
            # Messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                university TEXT,
                message_type TEXT,
                content TEXT,
                filtered_content TEXT,
                media_type TEXT,
                file_id TEXT,
                status TEXT DEFAULT 'pending',
                moderation_reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')
            
            # Migration: ensure all expected columns exist in messages table
            try:
                cursor.execute('PRAGMA table_info(messages)')
                msg_columns = [row[1] for row in cursor.fetchall()]
                required_columns = {
                    'filtered_content': "TEXT",
                    'media_type': "TEXT",
                    'file_id': "TEXT",
                    'status': "TEXT DEFAULT 'pending'",
                    'moderation_reason': "TEXT",
                    'timestamp': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                }
                for col_name, col_def in required_columns.items():
                    if col_name not in msg_columns:
                        cursor.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_def}")
            except sqlite3.Error as e:
                logging.warning(f"Messages table migration check failed: {e}")
            
            # University change requests table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS university_changes (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                old_university TEXT,
                new_university TEXT,
                status TEXT DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')

            # Ideas table (for suggestions sent to admin)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ideas (
                idea_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                media_type TEXT,
                file_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')
            
            # Message counter table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_counters (
                university TEXT PRIMARY KEY,
                counter INTEGER DEFAULT 1
            )''')

            # Banned users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                until TIMESTAMP NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Message queue table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                scheduled_time TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            )''')

            # Moderators table (+migration for name column)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            # Migration: ensure 'name' column exists
            try:
                cursor.execute('PRAGMA table_info(moderators)')
                mod_columns = [row[1] for row in cursor.fetchall()]
                if 'name' not in mod_columns:
                    cursor.execute("ALTER TABLE moderators ADD COLUMN name TEXT")
            except sqlite3.Error as e:
                logging.warning(f"Moderators table migration check failed: {e}")
            
            # Indexes to speed up common queries
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_university ON messages(university)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_status_time ON message_queue(status, scheduled_time)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_message ON message_queue(message_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_unichanges_status ON university_changes(status)')
            except sqlite3.Error as e:
                logging.warning(f"Index creation warning: {e}")

            # Insert universities into message_counters
            for uni in UNIVERSITIES:
                cursor.execute('INSERT OR IGNORE INTO message_counters (university) VALUES (?)', (uni,))
            
            conn.commit()
            logging.info("Database initialized successfully!")
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
            conn.rollback()

# User operations
def get_user(user_id):
    """Get user information by user ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Explicit column order to keep indexes stable across migrations
            cursor.execute('SELECT user_id, username, university, language, registration_date FROM users WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
    except sqlite3.Error as e:
        logging.error(f"Error getting user {user_id}: {e}")
        return None

def add_user(user_id, username, university, language='ru'):
    """Add or update a user in the database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO users (user_id, username, university, language) VALUES (?, ?, ?, ?)', 
                (user_id, username, university, language)
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error adding user {user_id}: {e}")

def update_user_university(user_id, new_university):
    """Update a user's university"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET university = ? WHERE user_id = ?', (new_university, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error updating university for {user_id}: {e}")

def update_user_language(user_id, language):
    """Update a user's language preference"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error updating language for {user_id}: {e}")

# Message operations
def add_message_to_db(user_id, university, message_type, content, filtered_content=None, 
                      media_type=None, file_id=None, status='pending', reason=None):
    """Add a message to the database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO messages (user_id, university, message_type, content, filtered_content, 
                                 media_type, file_id, status, moderation_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, university, message_type, content, filtered_content, 
                  media_type, file_id, status, reason))
            message_id = cursor.lastrowid
            conn.commit()
            return message_id
    except sqlite3.Error as e:
        logging.error(f"Error adding message: {e}")
        return None

def update_message_status(message_id, status):
    """Update a message's moderation status"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET status = ? WHERE message_id = ?', (status, message_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error updating message status: {e}")

def get_message_counter(university):
    """Get and increment the message counter for a university"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Ensure atomicity. Prefer RETURNING (SQLite >= 3.35). Fallback to explicit transaction.
            try:
                cursor.execute('BEGIN IMMEDIATE')
                try:
                    # Return previous value atomically via expression
                    cursor.execute(
                        'UPDATE message_counters SET counter = counter + 1 WHERE university = ? RETURNING counter - 1',
                        (university,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        # If row missing, create and try again
                        cursor.execute('INSERT OR IGNORE INTO message_counters (university, counter) VALUES (?, 1)', (university,))
                        cursor.execute(
                            'UPDATE message_counters SET counter = counter + 1 WHERE university = ? RETURNING counter - 1',
                            (university,)
                        )
                        row = cursor.fetchone()
                    prev_value = int(row[0]) if row and row[0] is not None else 1
                    conn.commit()
                    return prev_value if prev_value >= 1 else 1
                except sqlite3.OperationalError:
                    # Likely older SQLite without RETURNING support; do safe fallback under lock
                    cursor.execute('UPDATE message_counters SET counter = counter + 1 WHERE university = ?', (university,))
                    # Read post-increment value and derive previous
                    cursor.execute('SELECT counter FROM message_counters WHERE university = ?', (university,))
                    row = cursor.fetchone()
                    post_value = int(row[0]) if row and row[0] is not None else 1
                    prev_value = post_value - 1 if post_value > 1 else 1
                    conn.commit()
                    return prev_value
            except Exception:
                # If BEGIN failed or any other issue, attempt minimal safe path (non-atomic)
                logging.debug('Falling back to non-atomic counter update', exc_info=True)
                cursor.execute('SELECT counter FROM message_counters WHERE university = ?', (university,))
                result = cursor.fetchone()
                counter = int(result[0]) if result and result[0] is not None else 1
                try:
                    cursor.execute('UPDATE message_counters SET counter = counter + 1 WHERE university = ?', (university,))
                    conn.commit()
                except Exception:
                    logging.debug('Non-atomic counter update failed', exc_info=True)
                return counter
    except sqlite3.Error as e:
        logging.error(f"Error with message counter: {e}")
        return 1

def get_message(message_id):
    """Get message information by message ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM messages WHERE message_id = ?', (message_id,))
            return cursor.fetchone()
    except sqlite3.Error as e:
        logging.error(f"Error getting message {message_id}: {e}")
        return None

def get_pending_messages():
    """Get all pending messages for moderation (explicit columns)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    message_id, user_id, university, message_type, content,
                    filtered_content, media_type, file_id, status, moderation_reason, timestamp
                FROM messages
                WHERE status = 'pending'
                ORDER BY message_id DESC
            ''')
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Error getting pending messages: {e}")
        return []

# University change operations
def add_university_change_request(user_id, old_university, new_university=None):
    """Add a university change request to the database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO university_changes (user_id, old_university, new_university)
            VALUES (?, ?, ?)
            ''', (user_id, old_university, new_university))
            request_id = cursor.lastrowid
            conn.commit()
            return request_id
    except sqlite3.Error as e:
        logging.error(f"Error adding university change request: {e}")
        return None

def update_university_change_status(request_id, status):
    """Update the status of a university change request"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE university_changes SET status = ? WHERE request_id = ?', (status, request_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error updating change request status: {e}")

def get_pending_university_changes():
    """Get all pending university change requests"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM university_changes WHERE status = "pending" ORDER BY request_id DESC')
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Error getting pending university changes: {e}")
        return []

# Message queue operations
def add_message_to_queue(message_id, scheduled_time):
    """Add a message to the sending queue"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO message_queue (message_id, scheduled_time, status)
            VALUES (?, ?, 'pending')
            ''', (message_id, scheduled_time))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error adding message to queue: {e}")

def get_last_scheduled_time():
    """Return the latest scheduled_time among pending queue items as datetime, or None"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(scheduled_time)
                FROM message_queue
                WHERE status = 'pending'
            ''')
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                except Exception:
                    return None
            return None
    except sqlite3.Error as e:
        logging.error(f"Error getting last scheduled time: {e}")
        return None

# Moderators operations
def get_moderators():
    """Return list of moderator user_ids"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM moderators')
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Error getting moderators: {e}")
        return []

def get_moderators_with_names():
    """Return list of (user_id, name, added_at) for moderators"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, COALESCE(name, ""), added_at FROM moderators ORDER BY added_at DESC')
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Error getting moderators with names: {e}")
        return []

# Banlist operations
def ban_user(user_id: int, reason: str | None = None, until: str | None = None) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO banned_users (user_id, reason, until) VALUES (?, ?, ?)', (user_id, reason, until))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Error banning user {user_id}: {e}")
        return False

def unban_user(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Error unbanning user {user_id}: {e}")
        return False

def is_banned(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Expire timed bans: delete rows where until < now
            try:
                cursor.execute('DELETE FROM banned_users WHERE until IS NOT NULL AND until < CURRENT_TIMESTAMP')
            except sqlite3.Error:
                pass
            cursor.execute('SELECT 1 FROM banned_users WHERE user_id = ? LIMIT 1', (user_id,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Error checking ban for {user_id}: {e}")
        return False

def ban_user_for(user_id: int, seconds: int, reason: str | None = None) -> bool:
    """Ban user for N seconds from now (stores absolute until timestamp)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Compute until as CURRENT_TIMESTAMP + seconds
            cursor.execute('INSERT OR REPLACE INTO banned_users (user_id, reason, until) VALUES (?, ?, datetime(CURRENT_TIMESTAMP, ?))',
                           (user_id, reason, f'+{int(seconds)} seconds'))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Error banning user for duration {user_id}: {e}")
        return False

def is_moderator(user_id: int) -> bool:
    """Check if user is in moderators table"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM moderators WHERE user_id = ? LIMIT 1', (user_id,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Error checking moderator: {e}")
        return False

def add_moderator(user_id: int, name: str | None = None) -> bool:
    """Add a user to moderators; returns True if inserted/exists. Optionally set name."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO moderators (user_id) VALUES (?)', (user_id,))
            if name is not None:
                cursor.execute('UPDATE moderators SET name = ? WHERE user_id = ?', (name, user_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Error adding moderator: {e}")
        return False

def set_moderator_name(user_id: int, name: str) -> bool:
    """Update moderator's display name. Returns True if updated."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE moderators SET name = ? WHERE user_id = ?', (name, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Error updating moderator name: {e}")
        return False

def get_moderator_name(user_id: int) -> str:
    """Get moderator's display name. Returns name or None if not found."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM moderators WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Error getting moderator name: {e}")
        return None

def remove_moderator(user_id: int) -> bool:
    """Remove a user from moderators; returns True if removed."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM moderators WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Error removing moderator: {e}")
        return False

def get_messages_to_send():
    """Get messages that are ready to be sent (scheduled_time <= current time) with explicit columns"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                SELECT 
                    mq.queue_id,
                    m.message_id, m.user_id, m.university, m.message_type, m.content,
                    m.filtered_content, m.media_type, m.file_id, m.status, m.moderation_reason, m.timestamp
                FROM message_queue mq
                JOIN messages m ON mq.message_id = m.message_id
                WHERE mq.scheduled_time <= ? AND mq.status = 'pending'
                ORDER BY mq.scheduled_time ASC
            ''', (current_time,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Error getting messages to send: {e}")
        return []

def get_recent_message_texts(limit: int = 200) -> list[str]:
    """Return recent message texts (filtered_content preferred) ordered by newest first.
    Includes messages with status 'approved' or 'pending'.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT COALESCE(filtered_content, content) AS text
                FROM messages
                WHERE text IS NOT NULL AND TRIM(text) <> ''
                  AND status IN ('approved', 'pending')
                ORDER BY message_id DESC
                LIMIT ?
                ''', (int(limit),)
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows if row and row[0]]
    except sqlite3.Error as e:
        logging.error(f"Error fetching recent message texts: {e}")
        return []

def mark_message_as_sent(queue_id):
    """Mark a queued message as sent"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE message_queue SET status = "sent" WHERE queue_id = ?', (queue_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error marking message as sent: {e}")

def clear_pending_queue():
    """Delete all pending items from message_queue table"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM message_queue WHERE status = "pending"')
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error(f"Error clearing pending queue: {e}")
        return 0

def clear_pending_messages():
    """Mark all pending messages as rejected"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET status = "rejected" WHERE status = "pending"')
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error(f"Error clearing pending messages: {e}")
        return 0

# Ideas operations
def add_idea(user_id: int, content: str | None = None, media_type: str | None = None, file_id: str | None = None) -> int | None:
    """Store a user's idea/suggestion (text and optional media). Returns idea_id."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ideas (user_id, content, media_type, file_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, content, media_type, file_id))
            idea_id = cursor.lastrowid
            conn.commit()
            return idea_id
    except sqlite3.Error as e:
        logging.error(f"Error adding idea: {e}")
        return None

# ---- Ideas history (admin) ----
def get_ideas_count() -> int:
    """Return total number of ideas stored."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ideas')
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.Error as e:
        logging.error(f"Error counting ideas: {e}")
        return 0

def get_ideas_page(offset: int, limit: int) -> list[tuple]:
    """Return a page of ideas ordered by newest first.
    Columns: idea_id, user_id, content, media_type, file_id, timestamp
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT idea_id, user_id, content, media_type, file_id, timestamp
                FROM ideas
                ORDER BY idea_id DESC
                LIMIT ? OFFSET ?
                ''', (int(limit), int(offset))
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Error fetching ideas page: {e}")
        return []

def get_idea_by_id(idea_id: int):
    """Return a single idea row or None."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT idea_id, user_id, content, media_type, file_id, timestamp FROM ideas WHERE idea_id = ?',
                (idea_id,)
            )
            return cursor.fetchone()
    except sqlite3.Error as e:
        logging.error(f"Error fetching idea {idea_id}: {e}")
        return None