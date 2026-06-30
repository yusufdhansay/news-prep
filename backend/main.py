import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Load local environment
from dotenv import load_dotenv
load_dotenv()

# Import database and modules
from . import database
from . import news_fetcher
from . import llm_analyzer

app = FastAPI(
    title="MFin Daily News Prep API",
    description="Backend API for JBIMS MFin current affairs ingestion and PI practice",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ArticlePayload(BaseModel):
    title: str
    link: str
    source: str
    category: str
    pub_date: str

class KeyRequest(BaseModel):
    api_key: str

class ReadRequest(BaseModel):
    read_status: bool

class AnswerRequest(BaseModel):
    answer: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-mfin-key-change-in-prod")
JWT_ALGORITHM = "HS256"
security = HTTPBearer()

def hash_password(password: str) -> str:
    import bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=30)
    payload = {
        "sub": str(user_id),
        "exp": expire
    }
    import jwt
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    import jwt
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token or expired session.")

@app.post("/api/auth/register")
async def register_user(payload: UserRegister):
    email = payload.email.strip().lower()
    password = payload.password
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        
    # Check if user already exists
    existing = database.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
        
    hashed = hash_password(password)
    try:
        user_id = database.create_user(email, hashed)
        token = create_access_token(user_id)
        return {
            "token": token,
            "user": {"id": user_id, "email": email}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/auth/login")
async def login_user(payload: UserLogin):
    email = payload.email.strip().lower()
    password = payload.password
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
        
    user = database.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    token = create_access_token(user["id"])
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"]}
    }

@app.get("/api/auth/me")
async def get_me(user_id: int = Depends(get_current_user_id)):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return dict(row)

@app.get("/api/health")
async def health_check():
    """
    Checks the status of the server and Groq API key presence.
    """
    api_key = llm_analyzer.get_groq_api_key()
    has_key = bool(api_key and api_key != "your_key_here")
    
    return {
        "status": "healthy",
        "has_groq_key": has_key,
        "database_connected": True
    }

@app.post("/api/settings/key")
async def set_groq_key(request: KeyRequest):
    """
    Saves a new Groq API key in the environment and persists it to the .env file.
    """
    api_key = request.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
        
    os.environ["GROQ_API_KEY"] = api_key
    
    # Save to local .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        existing_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                existing_lines = f.readlines()
                
        key_found = False
        new_lines = []
        for line in existing_lines:
            if line.strip().startswith("GROQ_API_KEY="):
                new_lines.append(f"GROQ_API_KEY={api_key}\n")
                key_found = True
            else:
                new_lines.append(line)
                
        if not key_found:
            new_lines.append(f"GROQ_API_KEY={api_key}\n")
            
        with open(env_path, "w") as f:
            f.writelines(new_lines)
            
    except Exception as e:
        print(f"Warning: Could not save API key to .env: {e}")
        
    return {"success": True}

@app.get("/api/news")
async def get_news(
    category: Optional[str] = "all",
    read_status: Optional[int] = None,
    bookmarked: Optional[int] = None,
    search: Optional[str] = None,
    date: Optional[str] = None,
    limit: Optional[int] = 50,
    user_id: int = Depends(get_current_user_id)
):
    """
    Retrieves filtered list of news articles.
    """
    return database.get_articles(
        user_id=user_id,
        category=category,
        read_status=read_status,
        bookmarked=bookmarked,
        search_query=search,
        date_filter=date,
        limit=limit
    )

@app.post("/api/news/refresh")
async def refresh_news(date: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    """
    Fetches latest RSS feeds and updates the local SQLite cache.
    Uses a distributed lock to prevent thundering herd scraping.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    # 1. Acquire distributed lock
    lock_acquired = database.acquire_refresh_lock(target_date)
    if not lock_acquired:
        # If lock is already held, skip refresh and return success status
        return {
            "success": True, 
            "new_articles_count": 0, 
            "status": "refresh_in_progress"
        }
        
    try:
        articles = news_fetcher.refresh_all_news(date_str=target_date)
        if not articles:
            database.release_refresh_lock(target_date)
            return {"success": True, "new_articles_count": 0}
            
        new_count = database.save_articles(articles)
        database.release_refresh_lock(target_date)
        return {
            "success": True,
            "new_articles_count": new_count,
            "total_fetched": len(articles)
        }
    except Exception as e:
        database.release_refresh_lock(target_date)
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

@app.post("/api/news/{article_id}/analyze")
async def analyze_news_item(article_id: int, payload: Optional[ArticlePayload] = None, user_id: int = Depends(get_current_user_id)):
    """
    Runs HTML scraping and Groq analysis on a specific news item.
    """
    article = database.get_article(article_id, user_id=user_id)
    
    # Fallback to payload search/ingestion if not found in local DB by ID (stateless container workaround)
    if not article and payload:
        article = database.get_article_by_link(payload.link, user_id=user_id)
        if not article:
            database.save_articles([{
                "title": payload.title,
                "link": payload.link,
                "source": payload.source,
                "category": payload.category,
                "pub_date": payload.pub_date
            }])
            article = database.get_article_by_link(payload.link, user_id=user_id)
        if article:
            article_id = article["id"]

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    # Get or scrape full text
    full_text = article.get("full_text")
    if not full_text:
        try:
            full_text = news_fetcher.scrape_full_text(article["link"])
            database.update_article_full_text(article_id, full_text)
        except Exception as e:
            print(f"Error scraping: {e}")
            full_text = "Could not scrape article body."
            
    # Check if already analyzed
    if article.get("summary") and article.get("financial_implications") and article.get("pi_questions"):
        # Make sure we return the article with the newly scraped full_text
        updated = database.get_article(article_id, user_id=user_id)
        return updated
        
    # Otherwise run LLM analysis
    analysis = llm_analyzer.analyze_article(
        title=article["title"],
        category=article["category"],
        source=article["source"],
        full_text=full_text
    )
    
    if "error" in analysis:
        raise HTTPException(status_code=500, detail=analysis["error"])
        
    # Update DB
    database.update_article_analysis(
        article_id=article_id,
        summary=analysis.get("summary", ""),
        implications=analysis.get("implications", []),
        pi_questions=analysis.get("pi_questions", [])
    )
    
    # Return updated article
    return database.get_article(article_id, user_id=user_id)

@app.post("/api/news/{article_id}/read")
async def toggle_read_status(article_id: int, request: ReadRequest, user_id: int = Depends(get_current_user_id)):
    """
    Marks article as read or unread.
    """
    article = database.get_article(article_id, user_id=user_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    database.mark_as_read(user_id, article_id, request.read_status)
    return {"success": True}

@app.post("/api/news/{article_id}/bookmark")
async def toggle_bookmark_status(article_id: int, user_id: int = Depends(get_current_user_id)):
    """
    Toggles bookmark status of the article.
    """
    new_state = database.toggle_bookmark(user_id, article_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"success": True, "bookmarked": bool(new_state)}

@app.post("/api/news/{article_id}/chat")
async def chat_about_article(article_id: int, request: ChatRequest, user_id: int = Depends(get_current_user_id)):
    """
    Accepts user follow-up questions about a specific article and answers them
    using Groq LLM with context of the news item.
    """
    article = database.get_article(article_id, user_id=user_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    system_prompt = (
        "You are an elite finance professor and a veteran interviewer for the Master in Finance (MFin) course at JBIMS. "
        "The candidate has a query regarding a specific news event.\n\n"
        f"Article Title: {article['title']}\n"
        f"Category: {article['category']}\n"
        f"Source: {article['source']}\n"
        f"Summary: {article.get('summary') or ''}\n"
        f"Economic Implications:\n{article.get('financial_implications') or ''}\n"
        f"JBIMS PI Questions:\n{article.get('pi_questions') or ''}\n\n"
        "Please address the candidate's query with rigorous economic reasoning, financial models, and precise business terminology. "
        "Maintain a highly academic yet helpful tone suitable for preparing top candidates."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in request.history:
        role = "user" if msg.role in ("user", "candidate") else "assistant"
        messages.append({"role": role, "content": msg.content})
        
    messages.append({"role": "user", "content": request.message})
    
    result = llm_analyzer.call_groq_api(messages)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return {"response": result["content"]}

@app.get("/api/daily-briefing")
async def get_daily_briefing(user_id: int = Depends(get_current_user_id)):
    """
    Returns today's cohesive daily digest. Caches persistently in the database.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Check if cached briefing exists in database
    cached_content = database.get_cached_briefing(today_str)
    if cached_content:
        return {"date": today_str, "content": cached_content}
        
    # Otherwise fetch latest headlines to build it
    articles = database.get_articles(user_id=user_id, limit=15)
    if not articles:
        # Refresh first
        try:
            refreshed = news_fetcher.refresh_all_news()
            database.save_articles(refreshed)
            articles = database.get_articles(user_id=user_id, limit=15)
        except Exception:
            pass
            
    if not articles:
        return {"date": today_str, "content": "No news articles available. Refresh the feed first."}
        
    briefing_content = llm_analyzer.generate_daily_briefing(articles)
    
    # Save cache persistently to the database
    database.save_cached_briefing(today_str, briefing_content)
        
    return {"date": today_str, "content": briefing_content}

@app.post("/api/quiz/start")
async def start_quiz():
    """
    Starts a new mock interview session and returns the opening question.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Get today's headlines to seed the interview topics
    articles = database.get_articles(limit=10)
    headlines = [a["title"] for a in articles]
    
    if not headlines:
        raise HTTPException(status_code=400, detail="No news articles found. Please refresh news feed first.")
        
    # Start interview flow
    interview = llm_analyzer.conduct_mock_interview([], headlines)
    
    qa_details = [{"role": "panelist", "content": interview["response"]}]
    
    session_id = database.create_quiz_session(today_str, qa_details)
    
    return {
        "session_id": session_id,
        "message": interview["response"],
        "completed": False
    }

@app.post("/api/quiz/{session_id}/respond")
async def respond_to_quiz(session_id: int, request: AnswerRequest):
    """
    Receives candidate answer, appends it, gets the panelist response, and updates session.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Quiz session not found")
        
    import json
    qa_details = json.loads(row["qa_details"])
    completed = bool(row["completed"])
    
    if completed:
        return {
            "session_id": session_id,
            "message": "This interview session has already concluded.",
            "completed": True,
            "score": row["score"],
            "qa_details": qa_details
        }
        
    # Append candidate response
    qa_details.append({"role": "candidate", "content": request.answer})
    
    # Fetch headlines
    articles = database.get_articles(limit=10)
    headlines = [a["title"] for a in articles]
    
    # Conduct interview step
    interview = llm_analyzer.conduct_mock_interview(qa_details, headlines)
    
    # Append panelist response
    qa_details.append({"role": "panelist", "content": interview["response"]})
    
    # Update SQLite
    database.update_quiz_session(
        session_id=session_id,
        qa_details=qa_details,
        score=interview["score"],
        completed=1 if interview["completed"] else 0
    )
    
    return {
        "session_id": session_id,
        "message": interview["response"],
        "completed": interview["completed"],
        "score": interview["score"],
        "qa_details": qa_details
    }

@app.get("/api/quiz/history")
async def get_quiz_history():
    """
    Retrieves completed quiz history sessions.
    """
    return database.get_quiz_sessions(completed=1)

@app.get("/api/stats")
async def get_stats_endpoint(user_id: int = Depends(get_current_user_id)):
    """
    Retrieves candidate progress stats.
    """
    return database.get_stats(user_id=user_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
