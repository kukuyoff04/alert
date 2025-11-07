# ตำแหน่งไฟล์: scrape_water.py
# ‼️ นี่คือเวอร์ชันอัปเดต (v6) ‼️

import os
import requests
import datetime
import json
from playwright.sync_api import sync_playwright, Playwright, Error

# --- ⚙️ การตั้งค่า ---
TARGET_URL = "https://www.thaiwater.net/water/wl"
LOCATION_TEXT = "ต.อินทร์บุรี อ.อินทร์บุรี"
CUSTOM_BANK_LEVEL = 13.00
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LAST_LEVEL_FILE = "last_level.txt"
# --------------------

def send_line_oa_broadcast(message_text):
    """ส่งข้อความ Broadcast ผ่าน LINE Messaging API"""
    if not LINE_TOKEN:
        print("Error: ไม่ได้ตั้งค่า LINE_CHANNEL_ACCESS_TOKEN")
        return False
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"messages": [{"type": "text", "text": message_text}]}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status() 
        print("ส่ง LINE OA Broadcast สำเร็จ!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"เกิดข้อผิดพลาดในการส่ง LINE: {e}")
        if e.response:
            print(f"Response body: {e.response.text}")
        return False

def get_bkk_time():
    """ดึงเวลาปัจจุบันของกรุงเทพฯ (GMT+7)"""
    try:
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        bkk_tz = datetime.timezone(datetime.timedelta(hours=7))
        bkk_now = utc_now.astimezone(bkk_tz)
    except Exception:
        bkk_now = datetime.datetime.now()
    return bkk_now.strftime("%d/%m/%Y %H:%M น.")

def get_last_level():
    """อ่านค่าล่าสุดจากไฟล์"""
    try:
        with open(LAST_LEVEL_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("ไม่พบไฟล์ค่าล่าสุด, จะสร้างใหม่")
        return None

def save_last_level(level):
    """บันทึกค่าล่าสุดลงไฟล์"""
    try:
        with open(LAST_LEVEL_FILE, 'w') as f:
            f.write(str(level))
        print(f"บันทึกค่าล่าสุด {level} ลงใน {LAST_LEVEL_FILE} สำเร็จ")
    except Exception as e:
        print(f"ไม่สามารถบันทึกไฟล์ได้: {e}")

def scrape_water_level(playwright: Playwright):
    """สคริปต์หลักในการดึงข้อมูล"""
    print(f"🚀 เริ่มกระบวนการ... (เวลา Server: {datetime.datetime.now()})")
    
    browser = None
    page = None
    
    try:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        print(f"กำลังเปิดหน้าเว็บ... {TARGET_URL}")
        page.goto(TARGET_URL, wait_until='networkidle', timeout=120000) 
        
        print("กำลังรอตารางหลัก (table.MuiTable-root) โหลด...")
        page.wait_for_selector("table.MuiTable-root", state="visible", timeout=120000)
        print("✅ ตารางหลักโหลดแล้ว")

        print(f"กำลังรอที่ตั้ง: {LOCATION_TEXT}")
        location_cell_locator = page.locator(f"td:has-text('{LOCATION_TEXT}')")
        
        # --- ⬇️ เพิ่มเวลารอตรงนี้เป็น 2 นาที ⬇️ ---
        location_cell_locator.wait_for(state="visible", timeout=120000) 
        
        print("✅ พบที่ตั้งแล้ว! กำลังดึงข้อมูลแถว...")
        
        row = location_cell_locator.locator("xpath=./ancestor::tr").first
        
        if not row:
             raise Exception(f"พบที่ตั้ง '{LOCATION_TEXT}' แต่หาแถวแม่ (tr) ไม่เจอ")

        cells = row.locator("td").all_inner_texts()
        current_level_str = cells[2].strip()
        current_level = float(current_level_str)
        
        print(f"ระดับน้ำที่ดึงได้: {current_level_str} ม.รทก.")

        last_level = get_last_level()

        if last_level == current_level_str:
            print(f"ระดับน้ำไม่เปลี่ยนแปลง ({current_level_str}). ไม่ต้องส่งแจ้งเตือน")
            return # ออกจากฟังก์ชันเลย

        print(f"ระดับน้ำมีการเปลี่ยนแปลง! (เก่า: {last_level}, ใหม่: {current_level_str})")
        
        diff_to_bank = CUSTOM_BANK_LEVEL - current_level
        time_str = get_bkk_time()
        message = (
            f"‼️ อัปเดตระดับน้ำ (อินทร์บุรี) ‼️\n"
            f"🗓️ วันที่: {time_str}\n"
            f"🌊 ระดับน้ำปัจจุบัน: {current_level:.2f} ม.รทก.\n"
            f"(เทียบตลิ่ง {CUSTOM_BANK_LEVEL:.2f} ม.: ต่ำกว่า {diff_to_bank:+.2f} ม.)"
        )
        
        print("✅ สร้างข้อความสำเร็จ")
        
        if send_line_oa_broadcast(message):
            save_last_level(current_level_str)
            
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดระหว่างการดึงข้อมูล: {e}")
        
        # --- ⬇️ เพิ่มโค้ดถ่ายรูปกลับมา ⬇️ ---
        if page:
            try:
                print("กำลังบันทึกภาพหน้าจอ debug...")
                page.screenshot(path='debug_screenshot.png', full_page=True)
                print("✅ บันทึกภาพหน้าจอ debug_screenshot.png สำเร็จ")
            except Exception as screenshot_e:
                print(f"❌ ไม่สามารถบันทึกภาพหน้าจอได้: {screenshot_e}")
        
        # ส่งแจ้งเตือน Error ไปที่ LINE
        send_line_oa_broadcast(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลน้ำอินทร์บุรี\nกรุณาตรวจสอบ Artifact 'debug-screenshot'")
        
        # สั่งให้ Step นี้ล้มเหลว
        raise e 
    
    finally:
        if browser:
            browser.close()
            print("Browser ถูกปิดแล้ว")

if __name__ == "__main__":
    try:
        with sync_playwright() as playwright:
            scrape_water_level(playwright)
    except Exception as e:
        # ดักจับ Error ที่เกิดจาก raise e ด้านบน เพื่อไม่ให้ Log แดงทั้งหมด
        print(f"❌ สคริปต์จบการทำงานพร้อม Error (นี่คือการจงใจให้ Step ล้มเหลว)")
