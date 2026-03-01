import datetime
import os
import json
import re
from playwright.sync_api import sync_playwright

PROPERTY_ID = os.environ.get('PROPERTY_ID')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

SERVICES_URL = f'https://bins.shropshire.gov.uk/property/{PROPERTY_ID}'


def scrape_council_site():
    """Scrape using Playwright with headless Chromium"""
    bin_collections = []
    
    with sync_playwright() as p:
        # Use the chromium from Lambda layer
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--single-process'
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        page.goto(SERVICES_URL, wait_until='networkidle', timeout=30000)
        
        # Wait for content to load (the site has dynamic content)
        page.wait_for_timeout(3000)
        
        # Try service IDs first, fallback to text search
        service_map = {
            '469': 'garden',
            '467': 'recycling',
            '465': 'rubbish'
        }

        text_map = {
            'Recycling Collection': 'recycling',
            'General Waste Collection': 'rubbish',
            'Garden Waste Collection': 'garden'
        }

        found_types = set()

        # Method 1: Service IDs
        for service_id, bin_type in service_map.items():
            try:
                row = page.locator(f"tr.service-id-{service_id}").first
                if row.is_visible():
                    next_service = row.locator("td.next-service").first
                    if next_service.is_visible():
                        date_text = next_service.text_content().strip()
                        if date_text:
                            bin_collections.append({
                                'type': bin_type,
                                'datetime': f'{date_text} 07:00:00'
                            })
                            found_types.add(bin_type)
                            print(f"Found {bin_type} via service ID {service_id}: {date_text}")
            except Exception as e:
                print(f"Service ID {service_id} not found: {e}")

        # Method 2: Fallback to text search for any missing types
        for text_pattern, bin_type in text_map.items():
            if bin_type not in found_types:
                try:
                    # Find row containing this text
                    row = page.locator("tr", has_text=text_pattern).first
                    if row.is_visible():
                        # Look for next collection in this row or nearby
                        next_service = row.locator("td.next-service").first
                        if next_service.is_visible():
                            date_text = next_service.text_content().strip()
                            if date_text and '/' in date_text:
                                bin_collections.append({
                                    'type': bin_type,
                                    'datetime': f'{date_text} 07:00:00'
                                })
                                print(f"Found {bin_type} via text search: {date_text}")
                except Exception as e:
                    print(f"Text search for {text_pattern} failed: {e}")
        
        browser.close()
    
    return bin_collections


def send_telegram(message):
    import urllib.request
    import urllib.parse
    
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    params = urllib.parse.urlencode({
        'chat_id': CHAT_ID,
        'parse_mode': 'Markdown',
        'text': message
    })
    
    req = urllib.request.Request(f"{url}?{params}")
    with urllib.request.urlopen(req, timeout=10) as response:
        print(f'SENDTELEGRAM: {response.read().decode()}')


def message_builder(colour, date):
    squares = {
        'blue': '🟦',
        'grey': '⬛',
        'green': '🟩',
        'purple': '🟪'
    }
    square = squares.get(colour.lower(), '⬜')
    return f'🗑️ {square} {colour.upper()} BIN {square} 🗑️ due out for collection tomorrow {date}'


def lookup_bin_colour(bin_type):
    colours = {
        'garden': ['green'],
        'recycling': ['blue', 'purple'],
        'rubbish': ['grey']
    }
    return colours.get(bin_type, [])


def check_alert_collection(collection):
    TIME_THRESHOLD = 24  # hours
    now = datetime.datetime.now()
    collection_time = datetime.datetime.strptime(
        collection['datetime'], 
        '%d/%m/%Y %H:%M:%S'
    )
    hours_diff = (collection_time - now).total_seconds() / 3600
    
    print(f"{collection['type']}: {hours_diff:.1f} hours until collection")
    
    if 0 < hours_diff < TIME_THRESHOLD:
        bin_colours = lookup_bin_colour(collection['type'])
        bin_date = collection_time.strftime('%d/%m/%Y')
        for colour in bin_colours:
            message = message_builder(colour, bin_date)
            send_telegram(message)
            print(f"Sent: {message}")
        return True
    return False


def handler(event, context):
    try:
        collections = scrape_council_site()
        print(f"Found {len(collections)} collections")
        
        message_sent = []
        for collection in collections:
            message_sent.append(check_alert_collection(collection))
        
        # Sunday (weekday 6) check - send alert if no messages sent
        if datetime.datetime.today().weekday() == 6 and not any(message_sent):
            send_telegram('No bin services processed, manually check in case I am broken')
        
        return {'statusCode': 200, 'body': json.dumps({'collections': len(collections), 'messages_sent': sum(message_sent)})}
    
    except Exception as e:
        print(f"Error: {str(e)}")
        # Send error notification
        send_telegram(f'BinAlerts error: {str(e)[:100]}')
        raise


if __name__ == '__main__':
    handler(None, None)
