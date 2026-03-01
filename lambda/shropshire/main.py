"""
BinAlerts Lambda function for scraping Shropshire Council bin collection dates
and sending Telegram notifications.
"""

import datetime
import json
import logging
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import List, Dict, Optional, Set

import boto3
from botocore.exceptions import ClientError
from playwright.sync_api import sync_playwright, Page

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)


@dataclass
class BinCollection:
    """Represents a bin collection"""
    bin_type: str
    date: datetime.datetime


@dataclass  
class Config:
    """Application configuration loaded from SSM Parameter Store (frugal - free tier)"""
    property_id: str
    bot_token: str
    chat_id: str
    services_url: str
    
    @classmethod
    def from_ssm(cls, prefix: Optional[str] = None) -> 'Config':
        """Load configuration from AWS SSM Parameter Store"""
        prefix = prefix or os.environ.get('SSM_PREFIX', '/binalerts/prod')
        
        client = boto3.client('ssm')
        params = {}
        
        try:
            # Load each parameter individually (more frugal than bulk API calls)
            for param_name in ['property-id', 'bot-token', 'chat-id']:
                full_name = f"{prefix}/{param_name}"
                try:
                    response = client.get_parameter(Name=full_name, WithDecryption=True)
                    value = response['Parameter']['Value']
                    if value == 'SET_MANUALLY_AFTER_DEPLOY':
                        raise ValueError(f"Parameter {full_name} not configured yet")
                    params[param_name.replace('-', '_')] = value
                except ClientError as e:
                    logger.error(f"Failed to load parameter {full_name}: {e}")
                    raise
            
            return cls(
                property_id=params['property_id'],
                bot_token=params['bot_token'],
                chat_id=params['chat_id'],
                services_url=f"https://bins.shropshire.gov.uk/property/{params['property_id']}"
            )
        except Exception as e:
            logger.error(f"Failed to load config from SSM: {e}")
            raise
            
            return cls(
                property_id=params['property_id'],
                bot_token=params['bot_token'],
                chat_id=params['chat_id'],
                services_url=f"https://bins.shropshire.gov.uk/property/{params['property_id']}"
            )
        except Exception as e:
            logger.error(f"Failed to load config from SSM: {e}")
            raise


class TelegramNotifier:
    """Handles Telegram notifications"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, message: str) -> bool:
        """Send a message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        params = urllib.parse.urlencode({
            'chat_id': self.chat_id,
            'parse_mode': 'Markdown',
            'text': message
        })
        
        try:
            req = urllib.request.Request(f"{url}?{params}")
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                if result.get('ok'):
                    logger.info(f"Message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False


class BinScraper:
    """Scrapes bin collection data from Shropshire Council website"""
    
    SERVICE_MAP = {
        '469': 'garden',
        '467': 'recycling',
        '465': 'rubbish'
    }
    
    TEXT_MAP = {
        'Recycling Collection': 'recycling',
        'General Waste Collection': 'rubbish',
        'Garden Waste Collection': 'garden'
    }
    
    COLOUR_MAP = {
        'garden': ['green'],
        'recycling': ['blue', 'purple'],
        'rubbish': ['grey']
    }
    
    EMOJI_SQUARES = {
        'blue': '🟦',
        'grey': '⬛',
        'green': '🟩',
        'purple': '🟪'
    }
    
    def __init__(self, config: Config):
        self.config = config
        self.notifier = TelegramNotifier(config.bot_token, config.chat_id)
    
    def scrape_collections(self) -> List[BinCollection]:
        """Scrape bin collection dates from council website"""
        logger.info(f"Scraping {self.config.services_url}")
        collections = []
        
        with sync_playwright() as p:
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
            
            try:
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = context.new_page()
                page.goto(self.config.services_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(3000)
                
                found_types: Set[str] = set()
                
                # Method 1: Service IDs
                for service_id, bin_type in self.SERVICE_MAP.items():
                    if bin_type in found_types:
                        continue
                    
                    try:
                        row = page.locator(f"tr.service-id-{service_id}").first
                        if row.is_visible():
                            next_service = row.locator("td.next-service").first
                            if next_service.is_visible():
                                date_text = next_service.text_content().strip()
                                collection = self._parse_collection(bin_type, date_text)
                                if collection:
                                    collections.append(collection)
                                    found_types.add(bin_type)
                                    logger.info(f"Found {bin_type} via service ID {service_id}: {date_text}")
                    except Exception as e:
                        logger.debug(f"Service ID {service_id} not found: {e}")
                
                # Method 2: Text search fallback
                for text_pattern, bin_type in self.TEXT_MAP.items():
                    if bin_type in found_types:
                        continue
                    
                    try:
                        row = page.locator("tr", has_text=text_pattern).first
                        if row.is_visible():
                            next_service = row.locator("td.next-service").first
                            if next_service.is_visible():
                                date_text = next_service.text_content().strip()
                                collection = self._parse_collection(bin_type, date_text)
                                if collection:
                                    collections.append(collection)
                                    found_types.add(bin_type)
                                    logger.info(f"Found {bin_type} via text search: {date_text}")
                    except Exception as e:
                        logger.debug(f"Text search for {text_pattern} failed: {e}")
                
            finally:
                browser.close()
        
        logger.info(f"Found {len(collections)} collections: {[c.bin_type for c in collections]}")
        return collections
    
    def _parse_collection(self, bin_type: str, date_text: str) -> Optional[BinCollection]:
        """Parse date string into BinCollection"""
        if not date_text or '/' not in date_text:
            return None
        
        try:
            # Parse DD/MM/YYYY format
            date = datetime.datetime.strptime(f"{date_text} 07:00:00", '%d/%m/%Y %H:%M:%S')
            return BinCollection(bin_type=bin_type, date=date)
        except ValueError as e:
            logger.warning(f"Failed to parse date '{date_text}': {e}")
            return None
    
    def check_and_notify(self, collection: BinCollection) -> bool:
        """Check if collection is due tomorrow and send notification"""
        TIME_THRESHOLD = 24  # hours
        now = datetime.datetime.now()
        hours_diff = (collection.date - now).total_seconds() / 3600
        
        logger.info(f"{collection.bin_type}: {hours_diff:.1f} hours until collection")
        
        if 0 < hours_diff < TIME_THRESHOLD:
            colours = self.COLOUR_MAP.get(collection.bin_type, [])
            date_str = collection.date.strftime('%d/%m/%Y')
            
            for colour in colours:
                message = self._build_message(colour, date_str)
                if self.notifier.send_message(message):
                    logger.info(f"Sent notification for {colour} bin")
            return True
        return False
    
    def _build_message(self, colour: str, date: str) -> str:
        """Build notification message"""
        square = self.EMOJI_SQUARES.get(colour.lower(), '⬜')
        return f'🗑️ {square} {colour.upper()} BIN {square} 🗑️ due out for collection tomorrow {date}'
    
    def send_health_check(self, message: str) -> bool:
        """Send a health check message"""
        return self.notifier.send_message(message)


def handler(event: Dict, context) -> Dict:
    """Lambda handler"""
    logger.info(f"Starting bin alerts check, event: {event}")
    
    try:
        # Load configuration from SSM (frugal - free tier)
        config = Config.from_ssm()
        scraper = BinScraper(config)
        
        # Scrape collections
        collections = scraper.scrape_collections()
        
        if not collections:
            logger.warning("No collections found")
            # Still return success - website might be down
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No collections found', 'collections': 0})
            }
        
        # Check each collection and send notifications
        notifications_sent = 0
        for collection in collections:
            if scraper.check_and_notify(collection):
                notifications_sent += 1
        
        # Sunday health check - notify if no alerts sent all week
        today_weekday = datetime.datetime.today().weekday()
        if today_weekday == 6 and notifications_sent == 0:
            scraper.send_health_check(
                'No bin services processed this week, manually check in case I am broken'
            )
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'collections': len(collections),
                'notifications_sent': notifications_sent,
                'collection_types': [c.bin_type for c in collections]
            })
        }
        logger.info(f"Completed: {result}")
        return result
        
    except Exception as e:
        logger.exception("Unhandled error in handler")
        # Try to send error notification if possible
        try:
            config = Config.from_ssm()
            scraper = BinScraper(config)
            scraper.send_health_check(f'BinAlerts error: {str(e)[:100]}')
        except:
            pass
        raise


if __name__ == '__main__':
    handler(None, None)
