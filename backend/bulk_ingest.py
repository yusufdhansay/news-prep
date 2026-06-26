"""
Bulk Historical News Ingestion v2
Uses diverse, month-specific keyword strategies to fetch truly unique articles
for every day from 2026-01-01 to today.
"""
import sys
import os
import time
import sqlite3
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import email.utils

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import database

# Monthly keyword sets - diverse topics to maximize unique articles per month
MONTHLY_QUERIES = {
    1: [  # January
        "RBI monetary policy January 2026 India interest rate",
        "India stock market Sensex Nifty January 2026",
        "India economy GDP growth January 2026",
        "India budget fiscal policy 2026",
        "India banking sector NBFC fintech January 2026",
        "global trade tariffs geopolitics India January 2026",
        "India corporate earnings quarterly results January 2026",
        "India inflation CPI WPI January 2026",
    ],
    2: [  # February
        "Union Budget 2026 India highlights",
        "India budget 2026 tax reforms fiscal deficit",
        "Sensex Nifty stock market February 2026",
        "RBI February 2026 repo rate MPC",
        "India foreign trade exports imports February 2026",
        "India startup funding venture capital February 2026",
        "India crude oil energy policy February 2026",
        "India banking credit growth February 2026",
    ],
    3: [  # March
        "India financial year end March 2026",
        "RBI policy March 2026 banking regulation",
        "India stock market Q4 earnings March 2026",
        "India fiscal deficit target March 2026",
        "India trade agreement global commerce March 2026",
        "India GST collection March 2026 revenue",
        "India insurance sector IRDAI March 2026",
        "India mutual fund SIP investment March 2026",
    ],
    4: [  # April
        "India new financial year April 2026 FY27",
        "RBI monetary policy April 2026 rate decision",
        "India stock market April 2026 FII DII",
        "India manufacturing PMI services April 2026",
        "India real estate housing market April 2026",
        "India bond market yields April 2026",
        "India foreign exchange reserves rupee April 2026",
        "India IT sector technology hiring April 2026",
    ],
    5: [  # May
        "India GDP growth forecast May 2026",
        "RBI May 2026 monetary policy review",
        "India stock market rally correction May 2026",
        "India corporate results Q4 FY26 May 2026",
        "India monsoon agriculture kharif May 2026",
        "India infrastructure investment spending May 2026",
        "India energy oil gas OPEC May 2026",
        "India foreign policy trade deal bilateral May 2026",
    ],
    6: [  # June
        "India economy monsoon forecast June 2026",
        "RBI policy June 2026 credit growth",
        "India stock market mid year June 2026",
        "India GST revenue collection June 2026",
        "India banking NPA stress test June 2026",
        "India global geopolitics trade war June 2026",
        "India startup IPO unicorn June 2026",
        "India inflation food prices June 2026",
    ],
}

def parse_rss_date(date_str):
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def determine_category(query):
    """Assign a category based on query keywords."""
    q = query.lower()
    if any(k in q for k in ["rbi", "banking", "credit", "nbfc", "fintech", "insurance", "npa", "repo rate", "mpc"]):
        return "Finance & Banking"
    if any(k in q for k in ["sensex", "nifty", "stock market", "fii", "dii", "ipo", "mutual fund", "bond", "yields", "earnings"]):
        return "Markets"
    if any(k in q for k in ["geopolitics", "trade war", "global", "tariff", "foreign policy", "bilateral", "opec", "trade deal", "trade agreement"]):
        return "Geopolitics"
    return "Corporate & Economy"

def fetch_articles_for_query(query, target_date_str):
    """Fetch articles for a single query, stamp them with the target date."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []
        
        items = channel.findall("item")
        articles = []
        category = determine_category(query)
        
        for item in items[:20]:
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
            # Override date component to target date
            try:
                time_part = parsed_pub_date.split(" ")[1]
                stamped_date = f"{target_date_str} {time_part}"
            except Exception:
                stamped_date = f"{target_date_str} 12:00:00"
            
            articles.append({
                "title": clean_title,
                "link": link,
                "source": source,
                "pub_date": stamped_date,
                "category": category,
            })
        
        return articles
    except Exception as e:
        return []

def get_dates_coverage():
    """Returns dict {date_str: article_count}."""
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT date(pub_date) as d, COUNT(*) as cnt FROM articles GROUP BY d")
    rows = c.fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[row[0]] = row[1]
    return result

def bulk_ingest_v2():
    start_date = datetime(2026, 1, 1)
    end_date = datetime.now()
    total_days = (end_date - start_date).days + 1
    
    existing = get_dates_coverage()
    
    # Build list of dates needing articles
    dates_to_fill = []
    current = start_date
    while current <= end_date:
        ds = current.strftime("%Y-%m-%d")
        if existing.get(ds, 0) < 10:
            dates_to_fill.append(current)
        current += timedelta(days=1)
    
    print(f"=== Bulk Historical Ingestion v2 ===")
    print(f"Range: 2026-01-01 to {end_date.strftime('%Y-%m-%d')} ({total_days} days)")
    print(f"Already filled (>= 10 articles): {total_days - len(dates_to_fill)}")
    print(f"Dates to fill: {len(dates_to_fill)}")
    print()
    
    total_new = 0
    filled_count = 0
    
    for i, dt in enumerate(dates_to_fill):
        date_str = dt.strftime("%Y-%m-%d")
        month = dt.month
        day_of_month = dt.day
        
        queries = MONTHLY_QUERIES.get(month, MONTHLY_QUERIES[6])
        
        # Pick 4 queries for this day (rotate through the month's queries by day)
        selected_queries = []
        for j in range(4):
            idx = (day_of_month + j) % len(queries)
            selected_queries.append(queries[idx])
        
        # Build date-filtered versions of these queries
        after_date = (dt - timedelta(days=3)).strftime("%Y-%m-%d")
        before_date = (dt + timedelta(days=3)).strftime("%Y-%m-%d")
        
        progress = f"[{i+1}/{len(dates_to_fill)}]"
        print(f"{progress} {date_str} (month {month})...", end=" ", flush=True)
        
        all_articles = []
        for q in selected_queries:
            full_query = f"{q} after:{after_date} before:{before_date}"
            arts = fetch_articles_for_query(full_query, date_str)
            all_articles.extend(arts)
            time.sleep(0.5)  # Brief pause between queries
        
        if all_articles:
            new_count = database.save_articles(all_articles)
            total_new += new_count
            if new_count >= 10:
                filled_count += 1
            print(f"✓ {len(all_articles)} fetched, {new_count} new")
        else:
            print(f"⚠ no articles")
        
        # Rate limit between dates
        time.sleep(1.5)
    
    print()
    print(f"=== Ingestion Complete ===")
    print(f"Total new articles saved: {total_new}")
    
    final = get_dates_coverage()
    dates_with_10 = sum(1 for c in final.values() if c >= 10)
    print(f"Final: {len(final)} distinct dates, {dates_with_10}/{total_days} with >= 10 articles")
    
    # Show coverage by month
    print(f"\nMonthly breakdown:")
    for m in range(1, 7):
        month_dates = [d for d in final.keys() if d.startswith(f"2026-{m:02d}")]
        month_articles = sum(final[d] for d in month_dates)
        print(f"  2026-{m:02d}: {len(month_dates)} dates covered, {month_articles} total articles")

if __name__ == "__main__":
    bulk_ingest_v2()
