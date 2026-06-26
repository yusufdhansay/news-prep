import sys
import os

# Adjust path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import news_fetcher
from backend import database

def test_fetch_and_store():
    print("Initializing Database...")
    database.init_db()
    
    print("Testing RSS Feed Parsing...")
    articles = news_fetcher.refresh_all_news()
    print(f"Parsed total of {len(articles)} articles across all categories.")
    
    if not articles:
        print("FAIL: No articles could be fetched.")
        return False
        
    print("\nSample articles fetched:")
    for a in articles[:5]:
        print(f"- [{a['category']}] {a['title']} (Source: {a['source']})")
        
    print("\nSaving articles to SQLite Database...")
    new_count = database.save_articles(articles)
    print(f"Successfully saved {new_count} new unique articles to Database.")
    
    db_articles = database.get_articles(limit=5)
    print(f"\nRetrieved {len(db_articles)} articles from Database:")
    for a in db_articles:
        print(f"- [{a['category']}] {a['title']} (Read: {a['read_status']})")
        
    print("\nSUCCESS: Backend ingestion and database caching verified!")
    return True

if __name__ == "__main__":
    test_fetch_and_store()
