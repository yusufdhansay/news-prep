"""
Backfill News Articles starting from June 1st, 2026 for Current Affairs and MHRD
"""
import os
import sys
import time
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import email.utils
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load production env variables to target Vercel Postgres directly
load_dotenv('.env.production.local')

# Setup path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import database

SOURCES_FILTER = "(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:dailyhunt.in OR site:business-standard.com OR site:reuters.com)"

QUERIES = {
    "Current Affairs": f"(current affairs OR national news India OR policy reforms OR government schemes OR Supreme Court India OR elections India) {SOURCES_FILTER}",
    "MHRD": f"(labor laws India OR labor reforms OR trade unions OR human resource management OR employee relations OR gig economy OR talent management OR skill development OR EPFO) {SOURCES_FILTER}"
}

def parse_rss_date(date_str):
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_day_category(category, query, dt):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    date_str = dt.strftime("%Y-%m-%d")
    after_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    before_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    time_filter = f"after:{after_date} before:{before_date}"
    
    full_query = f"{query} {time_filter}"
    encoded = urllib.parse.quote_plus(full_query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  [ERROR] Status code {resp.status_code} for {category} on {date_str}")
            return []
            
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []
            
        items = channel.findall("item")
        articles = []
        
        # Limit to top 15 items per category to ensure coverage
        for item in items[:15]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date_raw = item.findtext("pubDate", "")
            
            source_elem = item.find("source")
            source = source_elem.text if source_elem is not None else "Google News"
            
            clean_title = title
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                clean_title = parts[0]
                if source == "Google News":
                    source = parts[1]
                    
            parsed_pub_date = parse_rss_date(pub_date_raw)
            try:
                time_part = parsed_pub_date.split(" ")[1]
                stamped_date = f"{date_str} {time_part}"
            except Exception:
                stamped_date = f"{date_str} 12:00:00"
                
            articles.append({
                "title": clean_title,
                "link": link,
                "source": source,
                "pub_date": stamped_date,
                "category": category
            })
        return articles
    except Exception as e:
        print(f"  [EXCEPTION] for {category} on {date_str}: {e}")
        return []

def main():
    start_date = datetime(2026, 6, 1)
    # End date is June 30th (since current local date in metadata is July 1st, 2026)
    end_date = datetime(2026, 6, 30)
    
    current = start_date
    print(f"Starting backfill from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    print(f"Connecting to database (Postgres: {database.IS_POSTGRES})...")
    
    total_saved = 0
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\nProcessing {date_str}...", flush=True)
        
        day_articles = []
        for cat, query in QUERIES.items():
            print(f"  Fetching {cat}...", flush=True)
            arts = fetch_day_category(cat, query, current)
            print(f"    Fetched {len(arts)} articles.", flush=True)
            day_articles.extend(arts)
            time.sleep(1)
            
        if day_articles:
            saved = database.save_articles(day_articles)
            total_saved += saved
            print(f"  Saved {saved} new articles for {date_str}.", flush=True)
        else:
            print(f"  No articles fetched for {date_str}.", flush=True)
            
        current += timedelta(days=1)
        time.sleep(1.5)
        
    print(f"\nBackfill complete! Total saved new articles: {total_saved}", flush=True)

if __name__ == "__main__":
    main()
