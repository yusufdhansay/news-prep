import sqlite3
import os
import json
from datetime import datetime

# Check if we should connect to Postgres
DB_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
IS_POSTGRES = DB_URL is not None

_CONN_POOL = None

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    import urllib.parse
    
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
        
    # Sanitize database URI: filter out unrecognized custom query parameters (like ?supa=) to prevent psycopg2 ProgrammingError
    try:
        parsed = urllib.parse.urlparse(DB_URL)
        query_params = urllib.parse.parse_qs(parsed.query)
        allowed_params = {'sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'options', 'application_name'}
        filtered_query_params = {k: v for k, v in query_params.items() if k in allowed_params}
        new_query = urllib.parse.urlencode(filtered_query_params, doseq=True)
        parsed = parsed._replace(query=new_query)
        DB_URL = urllib.parse.urlunparse(parsed)
    except Exception as e:
        print(f"Error sanitizing database URL: {e}")
else:
    if os.environ.get("VERCEL") == "1":
        # Serverless environment: Copy bundled database to /tmp/ if not already present
        VERCEL_DB_PATH = "/tmp/mfin_news.db"
        BUNDLED_DB_PATH = os.path.join(os.path.dirname(__file__), "mfin_news.db")
        if not os.path.exists(VERCEL_DB_PATH):
            import shutil
            print(f"Copying database from {BUNDLED_DB_PATH} to {VERCEL_DB_PATH}")
            try:
                shutil.copy2(BUNDLED_DB_PATH, VERCEL_DB_PATH)
            except Exception as e:
                print(f"Error copying database to /tmp: {e}")
        DB_PATH = VERCEL_DB_PATH
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "mfin_news.db")


class DynamicRow:
    def __init__(self, data):
        self.data = dict(data)
        self.keys_list = list(self.data.keys())
        self.values_list = list(self.data.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.values_list[key]
        return self.data[key]

    def keys(self):
        return self.keys_list

    def values(self):
        return self.values_list

    def __iter__(self):
        return iter(self.data.items())

    def __repr__(self):
        return repr(self.data)


class DynamicCursor:
    def __init__(self, cursor, is_postgres=False):
        self.cursor = cursor
        self.is_postgres = is_postgres
        self._lastrowid = None

    def execute(self, query, params=None):
        if params is None:
            params = ()
            
        if self.is_postgres:
            # 1. Translate placeholders
            query = query.replace('?', '%s')
            
            # 2. Translate SQLite INSERT OR IGNORE to PostgreSQL ON CONFLICT DO NOTHING
            if 'INSERT OR IGNORE INTO' in query:
                query = query.replace('INSERT OR IGNORE INTO', 'INSERT INTO')
                if 'articles' in query:
                    query += ' ON CONFLICT (link) DO NOTHING'
                elif 'user_bookmarks' in query or 'user_read_status' in query:
                    query += ' ON CONFLICT (user_id, article_id) DO NOTHING'
                elif 'daily_briefings' in query:
                    query += ' ON CONFLICT (date) DO NOTHING'
            
            # 3. Translate schema creation variables
            if 'INTEGER PRIMARY KEY AUTOINCREMENT' in query:
                query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
                
            # 4. Translate date functions
            if "date(pub_date) = date(%s)" in query:
                query = query.replace("date(pub_date) = date(%s)", "pub_date::date = %s::date")
            elif "date(pub_date)" in query:
                query = query.replace("date(pub_date)", "pub_date::date")
            elif "date('now', '-7 days')" in query:
                query = query.replace("date('now', '-7 days')", "(CURRENT_DATE - INTERVAL '7 days')::date")
            elif "date('now')" in query:
                query = query.replace("date('now')", "CURRENT_DATE")

            # 5. Handle lastrowid emulation
            is_insert = query.strip().upper().startswith('INSERT')
            if is_insert and 'RETURNING' not in query.upper():
                query += ' RETURNING id'
                self.cursor.execute(query, params)
                try:
                    row = self.cursor.fetchone()
                    if row:
                        self._lastrowid = row[0]
                except Exception:
                    pass
                return
            
        self.cursor.execute(query, params)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return DynamicRow(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [DynamicRow(r) for r in rows]

    @property
    def lastrowid(self):
        if self.is_postgres:
            return self._lastrowid
        else:
            return self.cursor.lastrowid

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class DynamicConnection:
    def __init__(self, conn, is_postgres=False, pool=None):
        self.conn = conn
        self.is_postgres = is_postgres
        self.pool = pool

    def cursor(self):
        if self.is_postgres:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cursor = self.conn.cursor()
        return DynamicCursor(cursor, is_postgres=self.is_postgres)

    def commit(self):
        self.conn.commit()

    def close(self):
        if self.is_postgres and self.pool:
            self.pool.putconn(self.conn)
        else:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self.conn.rollback()
            except Exception:
                pass
        self.close()


def get_db_connection():
    global _CONN_POOL
    if IS_POSTGRES:
        if _CONN_POOL is None:
            # Min 1 connection, max 12 connections
            _CONN_POOL = psycopg2.pool.ThreadedConnectionPool(1, 12, DB_URL)
        conn = _CONN_POOL.getconn()
        return DynamicConnection(conn, is_postgres=True, pool=_CONN_POOL)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return DynamicConnection(conn, is_postgres=False)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            pub_date TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT,
            financial_implications TEXT,
            pi_questions TEXT,
            read_status INTEGER DEFAULT 0,
            bookmarked INTEGER DEFAULT 0,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create user_bookmarks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_bookmarks (
            user_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, article_id)
        )
    """)
    
    # Create user_read_status table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_read_status (
            user_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, article_id)
        )
    """)
    
    # Create daily_briefings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_briefings (
            date TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create refresh_locks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refresh_locks (
            date TEXT PRIMARY KEY,
            locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create quiz sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            qa_details TEXT NOT NULL,
            score INTEGER,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migrate to add full_text column if it doesn't exist
    if IS_POSTGRES:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='articles' AND column_name='full_text'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE articles ADD COLUMN full_text TEXT")
    else:
        cursor.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'full_text' not in columns:
            cursor.execute("ALTER TABLE articles ADD COLUMN full_text TEXT")
        
    conn.commit()
    conn.close()

def save_articles(articles):
    """
    Saves a list of article dictionaries.
    Each article should have: title, link, source, pub_date, category.
    Duplicates are ignored based on the unique link constraint.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted_count = 0
    for article in articles:
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO articles (title, link, source, pub_date, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    article["title"],
                    article["link"],
                    article["source"],
                    article["pub_date"],
                    article["category"]
                )
            )
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception as e:
            print(f"Error saving article {article.get('title')}: {e}")
            
    conn.commit()
    conn.close()
    return inserted_count

def get_articles(user_id=None, category=None, read_status=None, bookmarked=None, search_query=None, date_filter=None, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT a.*,
               CASE WHEN b.article_id IS NOT NULL THEN 1 ELSE 0 END as bookmarked,
               CASE WHEN r.article_id IS NOT NULL THEN 1 ELSE 0 END as read_status
        FROM articles a
        LEFT JOIN user_bookmarks b ON a.id = b.article_id AND b.user_id = ?
        LEFT JOIN user_read_status r ON a.id = r.article_id AND r.user_id = ?
        WHERE 1=1
    """
    params = [user_id or 0, user_id or 0]
    
    if category and category.lower() != "all":
        query += " AND category = ?"
        params.append(category)
        
    if read_status is not None:
        query += " AND (CASE WHEN r.article_id IS NOT NULL THEN 1 ELSE 0 END) = ?"
        params.append(int(read_status))
        
    if bookmarked is not None:
        query += " AND (CASE WHEN b.article_id IS NOT NULL THEN 1 ELSE 0 END) = ?"
        params.append(int(bookmarked))
        
    if date_filter:
        query += " AND date(pub_date) = date(?)"
        params.append(date_filter)
        
    if search_query:
        query += " AND (title LIKE ? OR source LIKE ?)"
        search_param = f"%{search_query}%"
        params.append(search_param)
        params.append(search_param)
        
    # Order by publication date (or ID fallback to keep recent articles first)
    query += " ORDER BY pub_date DESC, id DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    articles = []
    for row in rows:
        article = dict(row)
        # Parse JSON columns if they exist
        if article["financial_implications"]:
            try:
                article["financial_implications"] = json.loads(article["financial_implications"])
            except Exception:
                pass
        if article["pi_questions"]:
            try:
                article["pi_questions"] = json.loads(article["pi_questions"])
            except Exception:
                pass
        articles.append(article)
        
    conn.close()
    return articles

def get_article(article_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT a.*,
               CASE WHEN b.article_id IS NOT NULL THEN 1 ELSE 0 END as bookmarked,
               CASE WHEN r.article_id IS NOT NULL THEN 1 ELSE 0 END as read_status
        FROM articles a
        LEFT JOIN user_bookmarks b ON a.id = b.article_id AND b.user_id = ?
        LEFT JOIN user_read_status r ON a.id = r.article_id AND r.user_id = ?
        WHERE a.id = ?
    """
    cursor.execute(query, (user_id or 0, user_id or 0, article_id))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
        
    article = dict(row)
    if article["financial_implications"]:
        try:
            article["financial_implications"] = json.loads(article["financial_implications"])
        except Exception:
            pass
    if article["pi_questions"]:
        try:
            article["pi_questions"] = json.loads(article["pi_questions"])
        except Exception:
            pass
            
    conn.close()
    return article

def update_article_analysis(article_id, summary, implications, pi_questions):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE articles
        SET summary = ?, financial_implications = ?, pi_questions = ?
        WHERE id = ?
        """,
        (
            summary,
            json.dumps(implications) if isinstance(implications, (list, dict)) else implications,
            json.dumps(pi_questions) if isinstance(pi_questions, (list, dict)) else pi_questions,
            article_id
        )
    )
    
    conn.commit()
    conn.close()

def update_article_full_text(article_id, full_text):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE articles SET full_text = ? WHERE id = ?", (full_text, article_id))
    conn.commit()
    conn.close()

def mark_as_read(user_id, article_id, read_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if read_status:
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_read_status (user_id, article_id)
            VALUES (?, ?)
            """,
            (user_id, article_id)
        )
    else:
        cursor.execute(
            """
            DELETE FROM user_read_status
            WHERE user_id = ? AND article_id = ?
            """,
            (user_id, article_id)
        )
    
    conn.commit()
    conn.close()

def toggle_bookmark(user_id, article_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current bookmarked state
    cursor.execute(
        "SELECT 1 FROM user_bookmarks WHERE user_id = ? AND article_id = ?",
        (user_id, article_id)
    )
    row = cursor.fetchone()
    
    if row:
        cursor.execute(
            "DELETE FROM user_bookmarks WHERE user_id = ? AND article_id = ?",
            (user_id, article_id)
        )
        new_state = 0
    else:
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_bookmarks (user_id, article_id)
            VALUES (?, ?)
            """,
            (user_id, article_id)
        )
        new_state = 1
    
    conn.commit()
    conn.close()
    return new_state

def create_quiz_session(date, qa_details):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO quiz_sessions (date, qa_details, completed)
        VALUES (?, ?, 0)
        """,
        (date, json.dumps(qa_details) if isinstance(qa_details, list) else qa_details)
    )
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def update_quiz_session(session_id, qa_details, score=None, completed=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE quiz_sessions
        SET qa_details = ?, score = ?, completed = ?
        WHERE id = ?
        """,
        (
            json.dumps(qa_details) if isinstance(qa_details, list) else qa_details,
            score,
            completed,
            session_id
        )
    )
    
    conn.commit()
    conn.close()

def get_quiz_sessions(completed=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM quiz_sessions"
    params = []
    
    if completed is not None:
        query += " WHERE completed = ?"
        params.append(int(completed))
        
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    sessions = []
    for row in rows:
        session = dict(row)
        try:
            session["qa_details"] = json.loads(session["qa_details"])
        except Exception:
            pass
        sessions.append(session)
        
    conn.close()
    return sessions

def get_stats(user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    uid = user_id or 0
    
    # Articles read total for this user
    cursor.execute("SELECT COUNT(*) FROM user_read_status WHERE user_id = ?", (uid,))
    read_count = cursor.fetchone()[0]
    
    # Total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_count = cursor.fetchone()[0]
    
    # Bookmarks count for this user
    cursor.execute("SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?", (uid,))
    bookmark_count = cursor.fetchone()[0]
    
    # Calculate streak (distinct days with read articles in the last 7 days for this user)
    cursor.execute("""
        SELECT COUNT(DISTINCT date(pub_date)) 
        FROM articles a
        JOIN user_read_status r ON a.id = r.article_id
        WHERE r.user_id = ?
          AND pub_date >= date('now', '-7 days')
    """, (uid,))
    streak = cursor.fetchone()[0]
    
    conn.close()
    return {
        "read_count": read_count,
        "total_count": total_count,
        "bookmark_count": bookmark_count,
        "quiz_count": 0,
        "avg_score": 0,
        "streak": streak
    }

def get_article_by_link(link, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT a.*,
               CASE WHEN b.article_id IS NOT NULL THEN 1 ELSE 0 END as bookmarked,
               CASE WHEN r.article_id IS NOT NULL THEN 1 ELSE 0 END as read_status
        FROM articles a
        LEFT JOIN user_bookmarks b ON a.id = b.article_id AND b.user_id = ?
        LEFT JOIN user_read_status r ON a.id = r.article_id AND r.user_id = ?
        WHERE a.link = ?
    """
    cursor.execute(query, (user_id or 0, user_id or 0, link))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    article = dict(row)
    if article["financial_implications"]:
        try:
            article["financial_implications"] = json.loads(article["financial_implications"])
        except Exception:
            pass
    if article["pi_questions"]:
        try:
            article["pi_questions"] = json.loads(article["pi_questions"])
        except Exception:
            pass
            
    conn.close()
    return article

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(email, hashed_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (email, hashed_password)
            VALUES (?, ?)
            """,
            (email.strip().lower(), hashed_password)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except Exception as e:
        conn.close()
        raise e

def get_cached_briefing(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM daily_briefings WHERE date = ?", (date_str,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_cached_briefing(date_str, content):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO daily_briefings (date, content)
            VALUES (?, ?)
            """,
            (date_str, content)
        )
        conn.commit()
    except Exception as e:
        print(f"Error caching daily briefing: {e}")
    conn.close()

def acquire_refresh_lock(date_str):
    """
    Tries to acquire a lock for refreshing news for a specific date.
    Returns True if acquired successfully, False if already locked.
    Locks older than 2 minutes are automatically cleared/overwritten.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Clean up stale locks (older than 2 minutes)
    if IS_POSTGRES:
        cursor.execute("DELETE FROM refresh_locks WHERE locked_at < NOW() - INTERVAL '2 minutes'")
    else:
        # SQLite uses datetime()
        cursor.execute("DELETE FROM refresh_locks WHERE datetime(locked_at) < datetime('now', '-2 minutes')")
    
    # 2. Check if a valid lock exists
    cursor.execute("SELECT 1 FROM refresh_locks WHERE date = ?", (date_str,))
    if cursor.fetchone():
        conn.close()
        return False
        
    # 3. Try to acquire the lock
    try:
        cursor.execute("INSERT INTO refresh_locks (date) VALUES (?)", (date_str,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def release_refresh_lock(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM refresh_locks WHERE date = ?", (date_str,))
        conn.commit()
    except Exception as e:
        print(f"Error releasing refresh lock: {e}")
    conn.close()

# Initialize on import to make sure db file is ready
init_db()
