import time
import requests
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PINCODE = "500090"
MAX_PRICE = 200
# RAW SEARCH (No filters in URL, we will click them manually)
SEARCH_URL = "https://www.firstcry.com/search?q=hot%20wheels" 

# --- PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, "seen_cars.txt")

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send alert: {e}")

def load_seen_products():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f: f.write("") 
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_seen_product(product_link):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{product_link}\n")

def check_firstcry():
    print(f"[{time.strftime('%H:%M')}] Launching Scan...")
    seen_products = load_seen_products()

    options = webdriver.ChromeOptions()
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(SEARCH_URL)
        wait = WebDriverWait(driver, 15)

        # --- 1. SET LOCATION ---
        try:
            print(f"📍 Setting location to {PINCODE}...")
            wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[5]/div/div[2]/ul/li[1]"))).click()
            time.sleep(1)
            wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div/div[1]/div/div[2]/div/span"))).click()
            time.sleep(1)
            box = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div/div[1]/div/div[4]/input")))
            box.click(); box.clear(); box.send_keys(PINCODE)
            time.sleep(0.5)
            wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div/div[1]/div/div[4]/div"))).click()
            print("✅ Location set. Waiting for reload...")
            time.sleep(5) 
        except Exception as e:
            print(f"⚠️ Location Warning: {e}")

        # --- 2. MANUAL SORT (Your XPaths) ---
        try:
            print("📉 Clicking Sort: Price Low to High...")
            
            # Click the Sort Dropdown Box
            sort_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[1]/div/div")))
            sort_dropdown.click()
            time.sleep(1)
            
            # Click the 'Price' Option from the list
            price_option = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/div[2]/div/div[2]/div[1]/div[2]/div[1]/ul/li[4]/a")))
            price_option.click()
            
            print("✅ Sort applied. Waiting for grid refresh...")
            time.sleep(5) # Crucial wait for cars to re-order
            
        except Exception as e:
            print(f"⚠️ Sorting Failed: {e}")

        # --- 3. SCRAPING ---
        print("🔍 Scanning sorted grid...")
        products_xpath = "/html/body/div[5]/div[2]/div/div[2]/div[3]/div[1]/div[4]/div"
        wait.until(EC.presence_of_element_located((By.XPATH, products_xpath)))
        products = driver.find_elements(By.XPATH, products_xpath)
        
        print(f"📦 Found {len(products)} items. checking prices...")
        
        for p in products:
            try:
                # Get Title & Link
                link_el = p.find_element(By.TAG_NAME, "a")
                link = link_el.get_attribute("href")
                title = link_el.get_attribute("title")
                if not title:
                    try: title = p.find_element(By.TAG_NAME, "img").get_attribute("title")
                    except: title = "Unknown Title"

                # Get Price (Parsing "₹ 167.00")
                try:
                    price_text = p.find_element(By.CLASS_NAME, "r1").text
                except:
                    # Fallback regex if class name changes
                    import re
                    price_text = re.search(r'₹\s?(\d+[\d,]*)', p.text).group(0)

                clean_price = float(price_text.replace('₹', '').replace(',', '').strip())

                # --- CHECK ---
                if clean_price <= MAX_PRICE:
                    if "hot wheels" in title.lower():
                        if "Out Of Stock" not in p.text:
                            
                            if link not in seen_products:
                                print(f"   ✅ MATCH FOUND: ₹{clean_price} - {title}")
                                
                                # Alert!
                                msg = (f"🚨 *HOT WHEELS FOUND!* 🚨\n"
                                       f"🏎 {title}\n"
                                       f"💰 ₹{clean_price}\n"
                                       f"[Buy Now]({link})")
                                send_telegram_alert(msg)
                                
                                save_seen_product(link)
                                seen_products.add(link)
                            else:
                                print(f"   ℹ️ Already in DB: ₹{clean_price}")
                else:
                    # Optional: Print skipped items to confirm sorting worked
                    # print(f"   Skip: ₹{clean_price}")
                    pass

            except Exception:
                continue 

        print(f"✅ Scan Complete.")
            
    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print("Running scheduled scan...")
    check_firstcry()