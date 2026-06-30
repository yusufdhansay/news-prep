import requests
import xml.etree.ElementTree as ET
import urllib.parse
import email.utils
from datetime import datetime

# Reputable sources filter (Moneycontrol, Economic Times, Livemint, Dailyhunt, Business Standard, Reuters)
SOURCES_FILTER = "(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:dailyhunt.in OR site:business-standard.com OR site:reuters.com)"

CATEGORY_QUERIES = {
    "Finance & Banking": f"(RBI OR banking sector OR monetary policy OR inflation OR public sector banks) {SOURCES_FILTER} when:7d",
    "Markets": f"(Nifty OR Sensex OR stock market OR stock market earnings OR commodity markets OR bond yields) {SOURCES_FILTER} when:7d",
    "Geopolitics": f"(geopolitics OR international trade OR global trade OR US Federal Reserve OR OPEC OR foreign policy India) {SOURCES_FILTER} when:7d",
    "Corporate & Economy": f"(India GDP OR startup funding OR mergers acquisitions OR fiscal deficit OR Union budget) {SOURCES_FILTER} when:7d"
}

def parse_rss_date(date_str):
    try:
        # Convert RFC 2822 date to YYYY-MM-DD HH:MM:SS format
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # Fallback to current time
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_category_news(category, date_str=None):
    query = CATEGORY_QUERIES.get(category)
    if not query:
        print(f"No query found for category: {category}")
        return []
        
    if date_str:
        try:
            from datetime import timedelta
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            after_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
            before_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            time_filter = f"after:{after_date} before:{before_date}"
            if "when:7d" in query:
                query = query.replace("when:7d", time_filter)
            else:
                query = f"{query} {time_filter}"
        except Exception as e:
            print(f"Error parsing date_str {date_str}: {e}")
            
    encoded_query = urllib.parse.quote_plus(query)
    # Target Indian business context with hl=en-IN, gl=IN, ceid=IN:en
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            print(f"Error fetching Google News for {category}: Status code {response.status_code}")
            return []
            
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            return []
            
        items = channel.findall("item")
        articles = []
        
        # Limit to top 25 items per category for comprehensive coverage
        for item in items[:25]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date_raw = item.findtext("pubDate", "")
            
            # Extract source name
            source_elem = item.find("source")
            source = source_elem.text if source_elem is not None else "Google News"
            
            # Clean title: Google News appends source at the end (e.g. "Title - Source")
            clean_title = title
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                clean_title = parts[0]
                if source == "Google News":
                    source = parts[1]
                    
            parsed_pub_date = parse_rss_date(pub_date_raw)
            if date_str:
                try:
                    time_part = parsed_pub_date.split(" ")[1]
                    parsed_pub_date = f"{date_str} {time_part}"
                except Exception:
                    parsed_pub_date = f"{date_str} 12:00:00"
                    
            articles.append({
                "title": clean_title,
                "link": link,
                "source": source,
                "pub_date": parsed_pub_date,
                "category": category
            })
            
        return articles
    except Exception as e:
        print(f"Exception fetching news for {category}: {str(e)}")
        return []

def refresh_all_news(date_str=None):
    """
    Fetches latest articles for all categories.
    """
    all_articles = []
    for category in CATEGORY_QUERIES.keys():
        print(f"Refreshing RSS feed for: {category} (Date: {date_str})...")
        articles = fetch_category_news(category, date_str=date_str)
        print(f"Fetched {len(articles)} items for {category}.")
        all_articles.extend(articles)
    return all_articles

def scrape_full_text(google_news_url):
    """
    Follows google news redirects to get the original article URL,
    fetches the HTML, and parses the main body paragraphs using BeautifulSoup.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    try:
        import json
        import urllib3
        from bs4 import BeautifulSoup
        
        # Suppress insecure request warnings from verify=False requests
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        original_url = None
        print(f"Resolving Google News URL: {google_news_url[:100]}...")

        # 1. Try to decode Google News URL via batchExecute RPC
        try:
            resp = requests.get(google_news_url, headers=headers, timeout=8, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                element = soup.select_one('c-wiz[data-p]')
                if element:
                    data_p = element.get('data-p')
                    obj = json.loads(data_p.replace('%.@.', '["garturlreq",'))
                    payload = {
                        'f.req': json.dumps([[['Fbv4je', json.dumps(obj[:-6] + obj[-2:]), 'null', 'generic']]])
                    }
                    post_headers = {
                        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        'user-agent': headers['User-Agent']
                    }
                    response = requests.post(
                        "https://news.google.com/_/DotsSplashUi/data/batchexecute", 
                        headers=post_headers, 
                        data=payload,
                        timeout=8,
                        verify=False
                    )
                    if response.status_code == 200:
                        array_string = json.loads(response.text.replace(")]}'", ""))[0][2]
                        original_url = json.loads(array_string)[1]
        except Exception as e:
            print(f"Error decoding Google News URL via RPC: {e}")

        # 2. Fallback to standard request redirect URL tracking
        if not original_url:
            try:
                redirect_res = requests.get(google_news_url, headers=headers, timeout=8, allow_redirects=True, verify=False)
                original_url = redirect_res.url
            except Exception as e:
                print(f"Fallback redirect URL resolution failed: {e}")

        if not original_url:
            return "Could not resolve original publisher URL. Please click 'Read Source' to visit the site."

        print(f"Original Article URL resolved: {original_url}")
        
        # Now fetch the original article content (disabling SSL verification in case the cert chain is incomplete)
        res = requests.get(original_url, headers=headers, timeout=8, verify=False)
        if res.status_code != 200:
            return f"Failed to fetch content from the original publisher (Status Code: {res.status_code}). Please click 'Read Source' to visit the site."
            
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Remove noisy tags
        for tag in soup(["script", "style", "aside", "nav", "footer", "header", "form", "iframe"]):
            tag.decompose()
            
        # Extract main text paragraphs
        paragraphs = soup.find_all('p')
        body_paragraphs = []
        
        for p in paragraphs:
            text = p.get_text().strip()
            # Simple heuristics to filter out typical webpage boilerplate
            if len(text) < 50:
                continue
            if any(term in text.lower() for term in [
                "follow us on", "subscribe to", "copyright ©", 
                "all rights reserved", "also read:", "click here to",
                "download the app", "sign in", "privacy policy"
            ]):
                continue
                
            body_paragraphs.append(text)
            
        if not body_paragraphs:
            # Fallback: get text from p tags with fewer filters
            body_paragraphs = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
            
        if not body_paragraphs:
            return "Could not automatically scrape the full article body. Please click 'Read Source' to view the content on the original website."
            
        return "\n\n".join(body_paragraphs)
    except Exception as e:
        print(f"Error scraping original article: {str(e)}")
        return f"Could not retrieve full article text due to a scraping error ({type(e).__name__}: {str(e)}). Please click 'Read Source' to read the story."
