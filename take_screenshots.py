#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Installing...")
    os.system(f"{sys.executable} -m pip install playwright")
    from playwright.sync_api import sync_playwright

def take_screenshots():
    pages_config = [
        {"name": "01_音乐搜索", "url": "/"},
        {"name": "02_歌词查询", "url": "/lyrics"},
        {"name": "03_文件管理", "url": "/files"},
        {"name": "04_歌单同步", "url": "/sync"},
        {"name": "05_配置", "url": "/config"},
        {"name": "06_消息推送", "url": "/magicpush"},
        {"name": "07_任务管理", "url": "/tasks"},
        {"name": "08_运行日志", "url": "/logs"},
        {"name": "09_API文档", "url": "/api-docs"}
    ]
    
    screenshots_dir = project_root / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # 登录
        print("Logging in...")
        page.goto("http://localhost:3000/login")
        page.wait_for_selector('input[type="text"]')
        page.fill('input[type="text"]', 'admin')
        page.fill('input[type="password"]', 'admin123')
        page.click('button')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        
        # 为每个页面截图
        for config in pages_config:
            print(f"Taking screenshot: {config['name']}")
            page.goto(f"http://localhost:3000{config['url']}")
            page.wait_for_load_state('networkidle')
            time.sleep(1)
            
            screenshot_path = screenshots_dir / f"{config['name']}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"✓ Saved: {screenshot_path}")
        
        browser.close()
    
    print("\n✅ All screenshots saved successfully!")
    return screenshots_dir

if __name__ == "__main__":
    take_screenshots()
