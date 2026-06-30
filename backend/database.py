import sqlite3
import os
import json
from datetime import datetime

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


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    
    # Create quiz sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            qa_details TEXT NOT NULL, -- JSON string representing chat logs and evaluations
            score INTEGER,            -- Overall evaluation score (0-100)
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migrate to add full_text column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN full_text TEXT")
    except sqlite3.OperationalError:
        pass
        
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

def get_articles(category=None, read_status=None, bookmarked=None, search_query=None, date_filter=None, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM articles WHERE 1=1"
    params = []
    
    if category and category.lower() != "all":
        query += " AND category = ?"
        params.append(category)
        
    if read_status is not None:
        query += " AND read_status = ?"
        params.append(int(read_status))
        
    if bookmarked is not None:
        query += " AND bookmarked = ?"
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

def get_article(article_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
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

def mark_as_read(article_id, read_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE articles SET read_status = ? WHERE id = ?", (int(read_status), article_id))
    
    conn.commit()
    conn.close()

def toggle_bookmark(article_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current bookmarked state
    cursor.execute("SELECT bookmarked FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    new_state = 1 if row["bookmarked"] == 0 else 0
    cursor.execute("UPDATE articles SET bookmarked = ? WHERE id = ?", (new_state, article_id))
    
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

def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Articles read total
    cursor.execute("SELECT COUNT(*) FROM articles WHERE read_status = 1")
    read_count = cursor.fetchone()[0]
    
    # Total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_count = cursor.fetchone()[0]
    
    # Bookmarks count
    cursor.execute("SELECT COUNT(*) FROM articles WHERE bookmarked = 1")
    bookmark_count = cursor.fetchone()[0]
    
    # Quiz stats
    cursor.execute("SELECT COUNT(*), AVG(score) FROM quiz_sessions WHERE completed = 1")
    row = cursor.fetchone()
    quiz_count = row[0]
    avg_score = round(row[1], 1) if row[1] is not None else 0
    
    # Calculate streak (mock/simple logic or actual date logic)
    # For simplicity, let's count distinct days with read articles in the last 7 days
    cursor.execute("""
        SELECT COUNT(DISTINCT date(pub_date)) 
        FROM articles 
        WHERE read_status = 1 
          AND pub_date >= date('now', '-7 days')
    """)
    streak = cursor.fetchone()[0]
    
    conn.close()
    return {
        "read_count": read_count,
        "total_count": total_count,
        "bookmark_count": bookmark_count,
        "quiz_count": quiz_count,
        "avg_score": avg_score,
        "streak": streak
    }

def get_article_by_link(link):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE link = ?", (link,))
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

# Initialize on import to make sure db file is ready
init_db()
