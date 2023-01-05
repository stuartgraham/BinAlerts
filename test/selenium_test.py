from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import os 

PROPERTY_ID : str = '10013133164'

SERVICES_URL = f'https://bins.shropshire.gov.uk/property/{PROPERTY_ID}#services'

def scrape_council_site():
    service=Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(SERVICES_URL)
    
    #Service has a likely 60 second stall on it, 20 second buffer
    driver.implicitly_wait(80)
    bin_collections = []

    garden_waste = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-469')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'garden', 'datetime': f'{garden_waste.text} 07:00:00'} )
    recycling = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-467')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'recycling', 'datetime': f'{recycling.text} 07:00:00'})
    rubbish = driver.find_element(By.XPATH, "*//tr[contains(@class,'service-id-465')]/td[contains(@class,'next-service')]")
    bin_collections.append({'type': 'rubbish', 'datetime': f'{rubbish.text} 07:00:00'}) 
    driver.quit()
    return bin_collections

collections = scrape_council_site()
for collection in collections:
    print(collection)