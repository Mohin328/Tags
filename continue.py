#!/usr/bin/env python3
"""
Continue Tag Collection - With Free Proxy Rotation for GitHub Actions
No Tor needed - uses free proxy lists
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import json
import re
import os
import sys
import random
from collections import Counter
from datetime import datetime

class ProxyRotator:
    def __init__(self):
        self.proxies = []
        self.current = 0
        self.load_free_proxies()
    
    def load_free_proxies(self):
        """Load free proxies from multiple sources"""
        # Free proxy sources (HTTP/HTTPS)
        proxy_sources = [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        ]
        
        print("📡 Fetching free proxies...")
        
        for url in proxy_sources[:2]:  # Just try first few to save time
            try:
                import urllib.request
                resp = urllib.request.urlopen(url, timeout=10)
                content = resp.read().decode('utf-8')
                for line in content.split('\n'):
                    line = line.strip()
                    if line and ':' in line and not line.startswith('#'):
                        proxy = f"http://{line}"
                        if proxy not in self.proxies:
                            self.proxies.append(proxy)
                print(f"  ✓ Got {len(self.proxies)} proxies so far")
            except:
                pass
        
        # Fallback proxies (hardcoded working ones)
        fallback = [
            "http://51.158.183.170:8811",
            "http://51.159.187.44:8811",
            "http://51.159.106.162:8811",
            "http://51.159.106.162:8811",
            "http://51.158.105.95:8811",
        ]
        self.proxies.extend(fallback)
        
        self.proxies = list(set(self.proxies))
        print(f"✓ Total proxies available: {len(self.proxies)}")
    
    def get(self):
        if not self.proxies:
            return None
        proxy = self.proxies[self.current % len(self.proxies)]
        self.current += 1
        return {"http": proxy, "https": proxy}
    
    def rotate(self):
        self.current += 1
        print(f"  🔄 Rotating to proxy #{self.current % len(self.proxies) + 1}")


class ContinueCollector:
    def __init__(self):
        self.base_url = "https://hanime1.me"
        self.proxy_rotator = ProxyRotator()
        self.session = self.create_session()
        
        self.session.headers.update({
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36',
            ]),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': self.base_url,
        })
        
        self.load_cookies()
        self.load_progress()
        self.existing_keys = self.load_existing_keys()
        self.consecutive_failures = 0
    
    def create_session(self):
        impersonate = random.choice(["chrome120", "chrome119", "safari15_5", "edge101"])
        session = requests.Session(impersonate=impersonate)
        proxy = self.proxy_rotator.get()
        if proxy:
            session.proxies.update(proxy)
        return session
    
    def rotate_proxy(self):
        print("  🔄 Rotating proxy...")
        self.proxy_rotator.rotate()
        old = self.session
        self.session = self.create_session()
        self.load_cookies_into_session()
        try:
            old.close()
        except:
            pass
        time.sleep(1)
    
    def load_cookies_into_session(self):
        if hasattr(self, 'saved_cookies'):
            for name, value in self.saved_cookies.items():
                self.session.cookies.set(name, value, domain='.hanime1.me', path='/')
    
    def load_cookies(self):
        self.saved_cookies = {}
        if os.path.exists("cookies.json"):
            with open("cookies.json", 'r') as f:
                cookies = json.load(f)
            for c in cookies:
                self.session.cookies.set(c['name'], c['value'], domain='.hanime1.me', path='/')
                self.saved_cookies[c['name']] = c['value']
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
    
    def extract_tags(self, html: str):
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
        
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=20)
                
                if resp.status_code == 200:
                    tags = self.extract_tags(resp.text)
                    self.processed_videos.add(video_id)
                    
                    if tags:
                        for tag in tags:
                            self.all_tags.add(tag)
                            self.tag_counter[tag] += 1
                            if tag not in self.existing_keys:
                                self.new_tags.add(tag)
                        print(f"  ✓ {video_id}: {len(tags)} tags")
                    else:
                        print(f"  ○ {video_id}: no tags")
                    self.consecutive_failures = 0
                    return True
                    
                elif resp.status_code == 403:
                    print(f"  ⚠ 403 on {video_id}")
                    self.rotate_proxy()
                    continue
                    
            except Exception as e:
                print(f"  ⚠ Error: {str(e)[:30]}")
                self.rotate_proxy()
                continue
        
        self.processed_videos.add(video_id)
        print(f"  ✗ {video_id}: failed after retries")
        return False
    
    def run(self, delay=0.5, save_interval=50):
        print(f"\n{'='*60}")
        print(f"CONTINUE WITH PROXY ROTATION")
        print(f"{'='*60}")
        
        remaining = [v for v in self.video_queue if v not in self.processed_videos]
        
        if not remaining:
            print("\n✓ All videos done!")
            self.create_outputs()
            return True
        
        print(f"\n📊 Remaining: {len(remaining)} videos")
        print(f"   Total: {len(self.video_queue)}")
        print(f"   Proxies available: {len(self.proxy_rotator.proxies)}")
        
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
    collector = ContinueCollector()
    collector.run(delay=0.5, save_interval=50)