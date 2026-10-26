import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta

def get_yahoo_news_articles(date):
    base_url = "https://news.yahoo.co.jp/topics/kyodotop"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    articles = []
    page = 1
    
    while True:
        url = f"{base_url}?page={page}"
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        article_links = soup.select('a.newsFeed_item_link')
        
        if not article_links:
            break
        
        for link in article_links:
            article_url = link['href']
            article_date_str = link.select_one('.newsFeed_item_date')
            
            if article_date_str:
                article_date = datetime.strptime(article_date_str.text.strip(), '%m月%d日')
                article_date = article_date.replace(year=date.year)
                
                if article_date.date() == date.date():
                    articles.append({
                        'url': article_url,
                        'date': article_date.strftime('%Y-%m-%d')
                    })
                elif article_date.date() < date.date():
                    return articles
        
        page += 1
    
    return articles

def main():
    target_date = datetime(2024, 10, 16)
    articles = get_yahoo_news_articles(target_date)
    
    print(f"Found {len(articles)} articles for {target_date.strftime('%Y-%m-%d')}")
    
    with open('yahoo_news_articles.json', 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()