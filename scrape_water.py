# ตำแหน่งไฟล์: scrape_water.py
# ‼️ นี่คือเวอร์ชันอัปเดต (v3) ‼️

import os
import requests
import datetime
import json
from playwright.sync_api import sync_playwright, Playwright, Error

# --- ⚙️ การตั้งค่า ---
TARGET_URL = "https://www.thaiwater.net/water/wl"
STATION_NAME = "สถานีอินทร์บุรี"
CUSTOM_BANK_LEVEL = 13.00  # ⬅️ ตั้งค่าตลิ่งของคุณที่ 13 เมตร
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
# --------------------

def send_line_oa_broadcast(message_text):
    """
    ส่งข้อความ Broadcast ผ่าน LINE Messaging API
    (ส่งหาผู้ติดตาม OA ทุกคน)
    """
    if not LINE_TOKEN:
        print("Error: ไม่ได้ตั้งค่า LINE_CHANNEL_ACCESS_TOKEN ใน GitHub Secrets")
        return

    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status() 
        
        if response.status_code == 200:
            print("ส่ง LINE OA Broadcast สำเร็จ!")
        else:
            print(f"ส่ง LINE OA Broadcast ไม่สำเร็จ: {response.status_code}, {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"เกิดข้อผิดพลาดในการส่ง LINE: {e}")
        if e.response:
            print(f"Response body: {e.response.text}")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดไม่คาดคิด: {e}")


def get_bkk_time():
    """ดึงเวลาปัจจุบันของกรุงเทพฯ (GMT+7) สำหรับใช้บน Server"""
    try:
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        bkk_tz = datetime.timezone(datetime.timedelta(hours=7))
        bkk_now = utc_now.astimezone(bkk_tz)
    except Exception:
        bkk_now = datetime.datetime.now()
        
    return bkk_now.strftime("%d/%m/%Y %H:%M น.")

def scrape_water_level(playwright: Playwright):
    """
    สคริปต์หลักในการดึงข้อมูล
    (ย้ายโค้ดเข้ามาในฟังก์ชันนี้เพื่อจัดการ Playwright context)
    """
    print(f"🚀 เริ่มกระบวนการ... (เวลา Server: {datetime.datetime.now()})")
    print(f"กำลังเริ่มดึงข้อมูลจาก: {TARGET_URL}")
    
    message_to_send = ""
    browser = None
    page = None
    
    try:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        
        print(f"กำลังเปิดหน้าเว็บ... {TARGET_URL}")
        # ⬇️ ขยายเวลารอเป็น 120 วินาที (2 นาที) ⬇️
        page.goto(TARGET_URL, wait_until='networkidle', timeout=120000) 
        
        print(f"กำลังรอสถานี: {STATION_NAME}")
        # ⬇️ ขยายเวลารอเป็น 120 วินาที (2 นาที) ⬇️
        page.wait_for_selector(f"button:has-text('{STATION_NAME}')", timeout=120000) 
        
        print("✅ พบสถานีแล้ว! กำลังดึงข้อมูล...")

        row = page.locator(f"//button[span[contains(text(), '{STATION_NAME}')]]/ancestor::tr").first
        
        if not row:
            raise Exception(f"ไม่พบแถว (tr) ของสถานี '{STATION_NAME}'")

        cells = row.locator("td").all_inner_texts()
        current_level_str = cells[2]
        current_level = float(current_level_str)
        
        print(f"ระดับน้ำที่ดึงได้: {current_level} ม.รทก.")

        diff_to_bank = CUSTOM_BANK_LEVEL - current_level
        
        time_str = get_bkk_time()
        message_to_send = (
            f"‼️ ประกาศเตือนภัยระดับน้ำสูงสุด ‼️\n"
            f"📍รายงานสถานการณ์น้ำเจ้าพระยา\nจ.อ.อินทร์บุรี\n"
            f"🗓️ วันที่: {time_str}\n"
            f"🌊 ระดับน้ำ + ระดับตลิ่ง\n"
            f"• อินทร์บุรี: {current_level:.2f} ม.รทก.\n"
            f"• ตลิ่ง: {CUSTOM_BANK_LEVEL:.2f} ม.รทก. (ต่ำกว่า {diff_to_bank:+.2f} ม.)"
        )
        
        print("✅ สร้างข้อความสำเร็จ")
            
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดระหว่างการดึงข้อมูล: {e}")
        
        if page:
            try:
                print("กำลังบันทึกภาพหน้าจอ debug...")
                page.screenshot(path='debug_screenshot.png', full_page=True)
                print("✅ บันทึกภาพหน้าจอ debug_screenshot.png สำเร็จ")
            except Exception as screenshot_e:
                print(f"❌ ไม่สามารถบันทึกภาพหน้าจอได้: {screenshot_e}")
        
        message_to_send = f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลน้ำอินทร์บุรี (Timeout)\nกรุณาตรวจสอบ Artifact 'debug-screenshot'"
    
    finally:
        if browser:
            browser.close()
            print("Browser ถูกปิดแล้ว")

        if message_to_send:
            print("📡 กำลังส่งข้อความ (Broadcast)...")
            print("--- ข้อความ ---")
            print(message_to_send)
            print("---------------")
            send_line_oa_broadcast(message_to_send)
        else:
            print("🚫 ไม่ได้สร้างข้อความ (อาจเกิดข้อผิดพลาดก่อนกำหนดค่า)")

# --- ⬇️ เปลี่ยนวิธีเรียกใช้ Playwright ⬇️ ---
if __name__ == "__main__":
    try:
        with sync_playwright() as playwright:
            scrape_water_level(playwright)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดร้ายแรงในการรัน Playwright: {e}")
        send_line_oa_broadcast(f"❌ เกิดข้อผิดพลาดร้ายแรงกับ Playwright: {e}")
