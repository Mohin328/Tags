#!/usr/bin/env python3
"""
Continue Tag Collection - Using Selenium with Chrome (Harder to block)
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
import re
import os
import sys
import random
from collections import Counter
from datetime import datetime

class SeleniumCollector:
    def __init__(self):
        self.base_url = "https://hanime1.me"
        self.driver = None
        self.init_driver()
        
        self.load_cookies()
        self.load_progress()
        self.existing_keys = self.load_existing_keys()
        
    def init_driver(self):
        """Initialize Chrome driver with anti-detection options"""
        chrome_options = Options()
        
        # Anti-detection arguments
        chrome_options.add_argument('--headless=new')  # Headless mode for GitHub Actions
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional anti-detection
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✓ Chrome driver initialized")
    
    def load_cookies(self):
        """Load cookies into browser"""
        if os.path.exists("cookies.json"):
            # First navigate to domain to set cookies
            self.driver.get(self.base_url)
            time.sleep(2)
            
            with open("cookies.json", 'r') as f:
                cookies = json.load(f)
            
            for cookie in cookies:
                try:
                    # Convert cookie format for selenium
                    cookie_dict = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', '.hanime1.me'),
                        'path': cookie.get('path', '/'),
                    }
                    if cookie.get('expirationDate'):
                        cookie_dict['expiry'] = int(cookie['expirationDate'])
                    self.driver.add_cookie(cookie_dict)
                except Exception as e:
                    pass
            
            self.driver.refresh()
            time.sleep(2)
            print(f"✓ Loaded {len(cookies)} cookies")
    
    def load_existing_keys(self):
        keys = set()
        if os.path.exists("tags.json"):
            with open("tags.json", 'r') as f:
                data = json.load(f)
                for items in data.values():
                    for item in items:
                        if 'search_key' in item:
                            keys.add(item['search_key'])
            print(f"✓ Loaded {len(keys)} existing tags")
        return keys
    
    def load_progress(self):
        if os.path.exists("collector_progress.json"):
            with open("collector_progress.json", 'r') as f:
                data = json.load(f)
                self.processed_videos = set(data.get("processed_videos", []))
                self.all_tags = set(data.get("all_tags", []))
                self.tag_counter = Counter(data.get("tag_counter", {}))
                self.new_tags = set(data.get("new_tags", []))
                self.video_queue = data.get("video_queue", [])
            print(f"✓ Resumed: {len(self.processed_videos)} / {len(self.video_queue)} videos")
        else:
            print("✗ No progress file!")
            sys.exit(1)
    
    def save_progress(self):
        data = {
            "processed_videos": list(self.processed_videos),
            "all_tags": list(self.all_tags),
            "tag_counter": dict(self.tag_counter),
            "new_tags": list(self.new_tags),
            "video_queue": self.video_queue,
        }
        with open("collector_progress.json", 'w') as f:
            json.dump(data, f)
    
    def clean_tag(self, tag: str) -> str:
        tag = tag.lstrip('#')
        if ' (' in tag:
            tag = tag.split(' (')[0]
        tag = re.sub(r'[（(].+?[）)]', '', tag).strip()
        return tag
    
    def extract_tags_from_page(self):
        """Extract tags from current page using BeautifulSoup"""
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tags = []
        
        for el in soup.select('.single-video-tag a'):
            cleaned = self.clean_tag(el.get_text(strip=True))
            if cleaned and len(cleaned) > 1:
                tags.append(cleaned)
        
        return tags
    
    def process_video(self, video_id):
        if video_id in self.processed_videos:
            return False
        
        url = f"{self.base_url}/watch?v={video_id}"
        
        try:
            # Navigate to video page
            self.driver.get(url)
            time.sleep(random.uniform(1, 2))  # Random delay
            
            # Wait for tags to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".single-video-tag"))
                )
            except:
                pass
            
            # Extract tags
            tags = self.extract_tags_from_page()
            
            self.processed_videos.add(video_id)
            
            if tags:
                for tag in tags:
                    self.all_tags.add(tag)
                    self.tag_counter[tag] += 1
                    if tag not in self.existing_keys:
                        self.new_tags.add(tag)
                print(f"  ✓ {video_id}: {len(tags)} tags")
                return True
            else:
                print(f"  ○ {video_id}: no tags")
                return False
                
        except Exception as e:
            self.processed_videos.add(video_id)
            print(f"  ✗ {video_id}: {str(e)[:50]}")
            return False
    
    def run(self, delay=1.0, save_interval=50):
        print(f"\n{'='*60}")
        print(f"CONTINUE WITH SELENIUM (Real Browser)")
        print(f"{'='*60}")
        
        remaining = [v for v in self.video_queue if v not in self.processed_videos]
        
        if not remaining:
            print("\n✓ All videos done!")
            self.create_outputs()
            return True
        
        print(f"\n📊 Remaining: {len(remaining)} videos")
        print(f"   Total: {len(self.video_queue)}")
        
        print(f"\n🏷️ Processing...")
        print("-" * 60)
        
        start = time.time()
        
        for i, vid in enumerate(remaining, 1):
            self.process_video(vid)
            
            if i % save_interval == 0:
                self.save_progress()
                elapsed = (time.time() - start) / 60
                rate = i / elapsed if elapsed > 0 else 0
                remaining_count = len(self.video_queue) - len(self.processed_videos)
                eta = remaining_count / rate if rate > 0 else 0
                percent = len(self.processed_videos) / len(self.video_queue) * 100
                print(f"\n📊 {len(self.processed_videos)}/{len(self.video_queue)} ({percent:.1f}%)")
                print(f"   Speed: {rate:.1f} v/min, ETA: {eta:.0f} min")
                print(f"   New tags: {len(self.new_tags)}")
                print("-" * 60)
            
            time.sleep(delay)
            
            # Stop at 5.5 hours
            if (time.time() - start) > 5.5 * 3600:
                print("\n⚠ Time limit reached, saving...")
                break
        
        self.save_progress()
        self.create_outputs()
        self.driver.quit()
        return True
    
    def create_outputs(self):
        existing = {}
        if os.path.exists("tags.json"):
            with open("tags.json", 'r') as f:
                existing = json.load(f)
        
        for cat in ["video_attributes", "character_relationships", "characteristics", 
                    "appearance_and_figure", "story_location", "story_plot", 
                    "sex_positions", "not_sorted"]:
            if cat not in existing:
                existing[cat] = []
        
        for tag in sorted(self.new_tags):
            existing["not_sorted"].append({
                "lang": {"zh-rCN": tag, "en": "", "zh-rTW": tag},
                "search_key": tag
            })
        
        with open("tags_updated.json", "w", encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        with open("new_tags.txt", "w", encoding='utf-8') as f:
            for tag in sorted(self.new_tags):
                f.write(f"{tag}\n")
        
        print(f"✓ Created tags_updated.json with {len(self.new_tags)} new tags")


if __name__ == "__main__":
    collector = SeleniumCollector()
    collector.run(delay=1.0, save_interval=50)