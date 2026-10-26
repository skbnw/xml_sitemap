import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def get_yahoo_news_urls(target_date):
    base_url = "https://news.yahoo.co.jp/media/kyodonews"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    urls = []
    page = 1
    
    while True:
        url = f"{base_url}?page={page}"
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        news_items = soup.select('.newsFeed_item')
        
        if not news_items:
            break
        
        for item in news_items:
            date_time = item.find('time').text.strip()
            match = re.match(r'(\d+)/(\d+)\(.\) (\d+):(\d+)', date_time)
            if match:
                month, day, hour, minute = map(int, match.groups())
                article_date = datetime(2024, month, day, hour, minute)
                
                if article_date.date() == target_date.date():
                    article_url = item.find('a')['href']
                    urls.append(article_url)
                elif article_date.date() < target_date.date():
                    return urls
        
        page += 1
    
    return urls

def main():
    target_date = datetime(2024, 10, 16)
    urls = get_yahoo_news_urls(target_date)
    
    print(f"Found {len(urls)} articles for {target_date.strftime('%Y-%m-%d')}")
    
    for url in urls:
        print(url)

if __name__ == "__main__":
    main()