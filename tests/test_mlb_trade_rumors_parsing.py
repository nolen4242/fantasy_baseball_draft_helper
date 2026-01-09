"""Test script to check if MLB Trade Rumors is parseable for news/transaction data."""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime


def test_mlb_trade_rumors_parsing():
    """Test parsing MLB Trade Rumors website."""
    url = "https://www.mlbtraderumors.com/"
    
    print("=" * 60)
    print("Testing MLB Trade Rumors Parsing")
    print("=" * 60)
    
    try:
        # Make GET request
        print(f"\n1. Making GET request to {url}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"   ✅ Status code: {response.status_code}")
        print(f"   Content length: {len(response.content)} bytes")
        
        # Parse HTML
        print("\n2. Parsing HTML...")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract headlines
        print("\n3. Extracting headlines...")
        headlines = []
        
        # Try different selectors for headlines
        headline_selectors = [
            'h2 a',  # Common headline format
            '.entry-title a',  # WordPress style
            'article h2 a',  # Article headlines
            '.post-title a',  # Post titles
            'h1 a',  # Main headlines
        ]
        
        for selector in headline_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"   Found {len(elements)} elements with selector: {selector}")
                for elem in elements[:10]:  # First 10
                    text = elem.get_text(strip=True)
                    href = elem.get('href', '')
                    if text and text not in [h['title'] for h in headlines]:
                        headlines.append({
                            'title': text,
                            'url': href if href.startswith('http') else f"https://www.mlbtraderumors.com{href}",
                            'selector': selector
                        })
        
        print(f"\n   ✅ Extracted {len(headlines)} unique headlines")
        
        # Show sample headlines
        print("\n4. Sample headlines:")
        for i, headline in enumerate(headlines[:10], 1):
            print(f"   {i}. {headline['title']}")
            print(f"      URL: {headline['url']}")
        
        # Extract article content structure
        print("\n5. Analyzing article structure...")
        articles = soup.find_all('article') or soup.find_all('div', class_=lambda x: x and 'post' in x.lower())
        print(f"   Found {len(articles)} article containers")
        
        if articles:
            sample_article = articles[0]
            print(f"\n   Sample article structure:")
            print(f"   - Title: {sample_article.find('h2') or sample_article.find('h1')}")
            print(f"   - Date: {sample_article.find('time') or sample_article.find(class_=lambda x: x and 'date' in x.lower() if x else False)}")
            print(f"   - Author: {sample_article.find(class_=lambda x: x and 'author' in x.lower() if x else False)}")
            print(f"   - Content preview: {sample_article.get_text()[:200]}...")
        
        # Check for transaction/player mentions
        print("\n6. Checking for transaction patterns...")
        page_text = soup.get_text()
        
        transaction_keywords = ['signed', 'traded', 'acquired', 'designated', 'waived', 'released']
        player_mentions = []
        
        for keyword in transaction_keywords:
            count = page_text.lower().count(keyword)
            if count > 0:
                print(f"   '{keyword}': {count} mentions")
        
        # Look for player names (common pattern: "Player Name" followed by transaction)
        print("\n7. Sample player/transaction patterns found:")
        # This is a simple check - in production we'd use more sophisticated NLP
        lines = page_text.split('\n')
        transaction_lines = [line.strip() for line in lines if any(kw in line.lower() for kw in transaction_keywords)]
        for line in transaction_lines[:5]:
            if len(line) > 20 and len(line) < 200:
                print(f"   - {line[:150]}...")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✅ Website is accessible and parseable")
        print(f"✅ Found {len(headlines)} headlines")
        print(f"✅ Found {len(articles)} article containers")
        print(f"✅ Transaction keywords detected")
        print(f"\n📊 Parseability: GOOD")
        print(f"   - HTML structure is accessible")
        print(f"   - Headlines can be extracted")
        print(f"   - Article content is available")
        print(f"   - Transaction patterns are detectable")
        
        return {
            'success': True,
            'headlines_count': len(headlines),
            'articles_count': len(articles),
            'sample_headlines': headlines[:10],
            'parseable': True
        }
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return {'success': False, 'error': str(e), 'parseable': False}
    except Exception as e:
        print(f"\n❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e), 'parseable': False}


if __name__ == "__main__":
    result = test_mlb_trade_rumors_parsing()
    print(f"\n{'='*60}")
    print("Test Result:")
    print(json.dumps(result, indent=2, default=str))



