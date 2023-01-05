import datetime
import time
from os import environ as osenv
import requests
from tempfile import mkdtemp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select


PROPERTY_ID : str = osenv.get('PROPERTY_ID')
BOT_TOKEN : str = osenv.get('BOT_TOKEN')
CHAT_ID : str = osenv.get('CHAT_ID')

SERVICES_URL = f'https://bins.shropshire.gov.uk/property/{PROPERTY_ID}#services'

# Build Selenium Driver
def selenium_driver():
    options = webdriver.ChromeOptions()
    options.binary_location = '/opt/chrome/chrome'
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280x1696')
    options.add_argument('--single-process')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-dev-tools')
    options.add_argument('--no-zygote')
    options.add_argument(f'--user-data-dir={mkdtemp()}')
    options.add_argument(f'--data-path={mkdtemp()}')
    options.add_argument(f'--disk-cache-dir={mkdtemp()}')
    options.add_argument('--remote-debugging-port=9222')
    driver = webdriver.Chrome('/opt/chromedriver', options=options)
    return driver

# Scrape council site data
def scrape_council_site():
    driver = selenium_driver()
    driver.get(SERVICES_URL)
    
    print('WAIT: Waiting 80 seconds for load')
    #Service has a likely 60 second stall on it, 20 second buffer
    driver.implicitly_wait(80)

    bin_collections = []

    print('COLLECTIONDATA: Trying to load collection content')
    # Find specific elements
    garden_waste = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-469')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'garden', 'datetime': f'{garden_waste.text} 07:00:00'} )
    recycling = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-467')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'recycling', 'datetime': f'{recycling.text} 07:00:00'})
    rubbish = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-465')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'rubbish', 'datetime': f'{rubbish.text} 07:00:00'}) 


    time.sleep(2.3)
    driver.quit()
    return bin_collections


def send_telegram(message):
    url_string = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&parse_mode=Markdown&text={message}'
    response = requests.get(url_string)
    print('SENDTELEGRAM: Message sending')
    print(response.json())


def message_builder(colour, date):
    blue_square = '🟦'
    grey_square = '⬛'
    green_square = '🟩'
    trash_can = '🗑️'
    square = locals()[colour.lower() + '_square']
    return f'{trash_can} {square} {colour.upper()} BIN {square} {trash_can} due out for collection tomorrow {date} '


def lookup_bin_colour(bin_type):
    if bin_type == 'garden':
        return 'green'
    if bin_type == 'recycling':
        return 'blue'
    if bin_type == 'rubbish':
        return 'grey'


def check_alert_collection(collection):
    # collection example
    # {'type': 'recycling', 'datetime': '09/01/2023 07:00:00'}
    TIME_THRESHOLD = 24
    now_time = datetime.datetime.now()
    collection_time = datetime.datetime.strptime(collection['datetime'], '%d/%m/%Y %H:%M:%S')
    time_difference = collection_time - now_time
    time_difference_hours = time_difference.total_seconds()/(60*60)
    print(str(time_difference_hours))
    
    if int(time_difference_hours) < TIME_THRESHOLD and int(time_difference_hours) > 0:
        bin_colour = lookup_bin_colour(collection['type'])
        bin_date =  collection_time.strftime('%d/%m/%Y')
        message = message_builder(bin_colour, bin_date)
        send_telegram(message)
        print(message)
        return True
    return False

def test_request():
    driver = selenium_driver()
    print(f'Retrieving {SERVICES_URL}')
    driver.get(SERVICES_URL)
    driver.implicitly_wait(80)
    html = driver.page_source
    print(html)

def handler(event, context):
    collections = scrape_council_site()
    message_sent = False
    for collection in collections:
        message_sent = check_alert_collection(collection)

    if datetime.datetime.today().weekday() == 6 and not message_sent:
        send_telegram('No bin services processed, manually check incase I am broken')