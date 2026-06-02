#!/usr/bin/env python3
"""
Continue Hanime Tag Collection - For GitHub Actions (no ID fetching)
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

class ContinueCollector:
    def __init__(self):
        self.base_url = "https://hanime1.me"
        # Random impersonation to avoid detection
        impersonate = random.choice(["chrome120", "chrome119", "chrome118", "safari15_5", "edge101"])
        self.session = requests.Session(impersonate=impersonate)
        
        # Rotate user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': self.base_url,
        })
        
        self.load_cookies()
        self.load_progress()
        self.existing_keys = self.load_existing_keys()
        self.request_count = 0
        
    def load_cookies(self):
        if os.path.exists("cookies.json"):
            with open("cookies.json", 'r') as f:
                cookies = json.load(f)
            for c in cookies:
                self.session.cookies.set(c['name'], c['value'], domain='.hanime1.me', path='/')
            print(f"✓ Loaded {len(cookies)} cookies")
        else:
            print("✗ No cookies.json found!")
    
    def load_existing_keys(self):
        keys = set()
        if os.path.exists("tags.json"):
            with open("tags.json", 'r') as f:
                data = json.load(f)
                for items in data.values():
                    for item in items:
                        if 'search_key' in item:
                            keys.add(item['search_key'])
                            keys.add(item['search_key'].lower())
            print(f"✓ Loaded {len(keys)} existing tag keys")
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
            print(f"✓ Resumed: {len(self.processed_videos)} videos processed")
            print(f"  Total in queue: {len(self.video_queue)}")
            print(f"  Remaining: {len(self.video_queue) - len(self.processed_videos)}")
        else:
            print("✗ No progress file found!")
            sys.exit(1)
    
    def save_progress(self):
        data = {
            "processed_videos": list(self.processed_videos),
            "all_tags": list(self.all_tags),
            "tag_counter": dict(self.tag_counter),
            "new_tags": list(self.new_tags),
            "video_queue": self.video_queue,
            "timestamp": time.time()
        }
        with open("collector_progress.json", 'w') as f:
            json.dump(data, f, indent=2)
    
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
            if cleaned and len(cleaned) > 1 and cleaned not in tags:
                tags.append(cleaned)
        return tags
    
    def process_video(self, video_id):
        if video_id in self.processed_videos:
            return False
        
        url = f"{self.base_url}/watch?v={video_id}"
        
        try:
            resp = self.session.get(url, timeout=20)
            self.request_count += 1
            
            if resp.status_code != 200:
                self.processed_videos.add(video_id)
                print(f"  ✗ {video_id}: HTTP {resp.status_code}")
                return False
            
            tags = self.extract_tags(resp.text)
            self.processed_videos.add(video_id)
            
            if tags:
                for tag in tags:
                    self.all_tags.add(tag)
                    self.tag_counter[tag] += 1
                    if tag not in self.existing_keys and tag.lower() not in self.existing_keys:
                        self.new_tags.add(tag)
                print(f"  ✓ {video_id}: {len(tags)} tags")
                return True
            else:
                print(f"  ○ {video_id}: no tags")
                return False
                
        except Exception as e:
            self.processed_videos.add(video_id)
            print(f"  ✗ {video_id}: {str(e)[:40]}")
            return False
    
    def run(self, delay=0.3, save_interval=50, max_videos=None):
        print(f"\n{'='*60}")
        print(f"CONTINUE TAG COLLECTION - GitHub Actions")
        print(f"{'='*60}")
        
        # Test connection first
        print("\nTesting connection...")
        try:
            test_resp = self.session.get(self.base_url, timeout=15)
            if test_resp.status_code == 200:
                print("✓ Connected to website")
            else:
                print(f"✗ Connection failed (HTTP {test_resp.status_code})")
                return False
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
        
        remaining = [v for v in self.video_queue if v not in self.processed_videos]
        
        if max_videos:
            remaining = remaining[:max_videos]
        
        if not remaining:
            print("\n✓ All videos already processed!")
            self.create_outputs()
            return True
        
        print(f"\n📊 To process: {len(remaining)} videos")
        print(f"   Already done: {len(self.processed_videos)}")
        print(f"   Total: {len(self.video_queue)}")
        print(f"   Existing tags: {len(self.existing_keys)}")
        
        print(f"\n🏷️ Processing (delay={delay}s)...")
        print("-" * 60)
        
        start_time = time.time()
        processed_this_run = 0
        
        for i, video_id in enumerate(remaining, 1):
            self.process_video(video_id)
            processed_this_run += 1
            
            if i % save_interval == 0:
                self.save_progress()
                elapsed = (time.time() - start_time) / 60
                percent = len(self.processed_videos) / len(self.video_queue) * 100
                rate = processed_this_run / elapsed if elapsed > 0 else 0
                remaining_videos = len(self.video_queue) - len(self.processed_videos)
                eta = remaining_videos / rate if rate > 0 else 0
                
                print(f"\n📊 Progress: {len(self.processed_videos)}/{len(self.video_queue)} ({percent:.1f}%)")
                print(f"   Tags: {len(self.all_tags)} total, {len(self.new_tags)} new")
                print(f"   Speed: {rate:.1f} videos/min")
                print(f"   ETA: {eta:.0f} min ({eta/60:.1f} hours)")
                print(f"   💾 Progress saved")
                print("-" * 60)
            
            time.sleep(delay)
            
            # GitHub Actions has 6 hour limit, stop at 5.5 hours
            if (time.time() - start_time) > 5.5 * 3600:
                print("\n⚠ Approaching 5.5 hour limit. Saving progress...")
                break
        
        self.save_progress()
        self.create_outputs()
        
        elapsed = (time.time() - start_time) / 3600
        print(f"\n{'='*60}")
        print(f"✅ Run complete!")
        print(f"   Processed this run: {processed_this_run} videos")
        print(f"   Total processed: {len(self.processed_videos)}")
        print(f"   Remaining: {len(self.video_queue) - len(self.processed_videos)}")
        print(f"   New tags found: {len(self.new_tags)}")
        print(f"   Runtime: {elapsed:.2f} hours")
        print(f"{'='*60}")
        
        return True
    
    def create_outputs(self):
        # Load existing tags
        existing_tags = {
            "video_attributes": [], "character_relationships": [], "characteristics": [],
            "appearance_and_figure": [], "story_location": [], "story_plot": [],
            "sex_positions": [], "not_sorted": []
        }
        
        if os.path.exists("tags.json"):
            with open("tags.json", 'r') as f:
                data = json.load(f)
                for cat in existing_tags:
                    if cat in data:
                        existing_tags[cat] = data[cat]
        
        # Add new tags
        for tag in sorted(self.new_tags):
            existing_tags["not_sorted"].append({
                "lang": {"zh-rCN": tag, "en": "", "zh-rTW": tag},
                "search_key": tag
            })
        
        with open("tags_updated.json", "w", encoding='utf-8') as f:
            json.dump(existing_tags, f, ensure_ascii=False, indent=2)
        
        with open("new_tags.txt", "w", encoding='utf-8') as f:
            for tag in sorted(self.new_tags):
                f.write(f"{tag}\n")
        
        # Report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_processed": len(self.processed_videos),
            "total_in_queue": len(self.video_queue),
            "total_unique_tags": len(self.all_tags),
            "new_tags_found": len(self.new_tags),
            "request_count": self.request_count
        }
        with open("collection_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("✓ Created tags_updated.json, new_tags.txt, collection_report.json")


if __name__ == "__main__":
    delay = float(os.environ.get('REQUEST_DELAY', '0.3'))
    save_interval = int(os.environ.get('SAVE_INTERVAL', '50'))
    max_videos = int(os.environ.get('MAX_VIDEOS', '0')) or None
    
    print(f"Configuration: delay={delay}s, save_interval={save_interval}")
    
    collector = ContinueCollector()
    success = collector.run(delay=delay, save_interval=save_interval, max_videos=max_videos)
    
    sys.exit(0 if success else 1)