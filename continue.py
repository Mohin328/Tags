#!/usr/bin/env python3
"""
Hanime Tag Collector - Uses existing video_ids.txt (no new ID fetching)
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import json
import re
import os
import sys
import signal
from collections import Counter
from typing import Set, List, Dict, Optional
from datetime import datetime

class HanimeTagCollector:
    def __init__(self, base_url: str = "https://hanime1.me", cookies_file: str = "cookies.json", 
                 tags_json_file: str = "tags.json", progress_file: str = "collector_progress.json"):
        self.base_url = base_url
        self.progress_file = progress_file
        self.session = requests.Session(impersonate="chrome120")
        self.running = True
        self.paused = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': base_url,
        })
        
        # Load cookies
        if os.path.exists(cookies_file):
            self.load_cookies(cookies_file)
        
        # Load existing tags
        self.existing_tags = self.load_existing_tags(tags_json_file)
        
        # Load or initialize collections
        self.load_progress()
        
        self.start_time = None
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⚠ Received interrupt signal...")
        if self.paused:
            print("  Exiting...")
            self.running = False
        else:
            print("  Pausing... Press Ctrl+C again to exit.")
            self.paused = True
            self.save_progress()
    
    def load_cookies(self, cookies_file: str):
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
            
            for cookie_data in cookies_data:
                self.session.cookies.set(
                    cookie_data['name'],
                    cookie_data['value'],
                    domain=cookie_data.get('domain', '.hanime1.me'),
                    path=cookie_data.get('path', '/'),
                )
            print(f"✓ Loaded {len(cookies_data)} cookies")
        except Exception as e:
            print(f"✗ Error loading cookies: {e}")
    
    def load_existing_tags(self, tags_json_file: str) -> Dict:
        existing = {
            "video_attributes": [],
            "character_relationships": [],
            "characteristics": [],
            "appearance_and_figure": [],
            "story_location": [],
            "story_plot": [],
            "sex_positions": [],
            "not_sorted": []
        }
        
        if os.path.exists(tags_json_file):
            try:
                with open(tags_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for category in existing.keys():
                        if category in data:
                            existing[category] = data[category]
                print(f"✓ Loaded existing tags from {tags_json_file}")
            except Exception as e:
                print(f"✗ Error loading {tags_json_file}: {e}")
        
        return existing
    
    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_videos = set(data.get("processed_videos", []))
                    self.all_tags = set(data.get("all_tags", []))
                    self.tag_counter = Counter(data.get("tag_counter", {}))
                    self.new_tags = set(data.get("new_tags", []))
                    self.video_queue = data.get("video_queue", [])
                print(f"✓ Resumed: {len(self.processed_videos)} videos already processed")
            except Exception as e:
                print(f"⚠ Could not load progress: {e}")
                self.init_new_collection()
        else:
            self.init_new_collection()
    
    def init_new_collection(self):
        self.processed_videos = set()
        self.all_tags = set()
        self.tag_counter = Counter()
        self.new_tags = set()
        self.video_queue = []
    
    def load_video_ids_from_file(self, video_ids_file: str = "video_ids.txt") -> List[str]:
        """Load video IDs from existing video_ids.txt file"""
        if not os.path.exists(video_ids_file):
            print(f"✗ {video_ids_file} not found!")
            print("  Please make sure video_ids.txt exists in the current directory")
            return []
        
        video_ids = []
        with open(video_ids_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and line.isdigit():  # Only numeric IDs
                    video_ids.append(line)
        
        print(f"✓ Loaded {len(video_ids)} video IDs from {video_ids_file}")
        return video_ids
    
    def save_progress(self):
        try:
            data = {
                "processed_videos": list(self.processed_videos),
                "all_tags": list(self.all_tags),
                "tag_counter": dict(self.tag_counter),
                "new_tags": list(self.new_tags),
                "video_queue": self.video_queue,
                "timestamp": time.time(),
                "last_update": datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ Could not save progress: {e}")
    
    def clean_tag(self, raw_tag: str) -> str:
        cleaned = raw_tag.lstrip('#')
        if ' (' in cleaned:
            cleaned = cleaned.split(' (')[0]
        cleaned = re.sub(r'\(\d+[KMB]?\)', '', cleaned).strip()
        cleaned = re.sub(r'（.+?）', '', cleaned).strip()
        return cleaned
    
    def get_existing_search_keys(self) -> Set[str]:
        keys = set()
        for category, items in self.existing_tags.items():
            for item in items:
                if 'search_key' in item:
                    search_key = item['search_key']
                    keys.add(search_key)
                    keys.add(search_key.lower())
                    keys.add(search_key.upper())
        return keys
    
    def is_new_tag(self, tag: str, existing_keys: Set[str]) -> bool:
        if tag in existing_keys:
            return False
        if tag.lower() in existing_keys:
            return False
        if tag.upper() in existing_keys:
            return False
        return True
    
    def extract_tags_from_video(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, 'html.parser')
        tags = []
        
        tag_elements = soup.select('.single-video-tag a')
        
        for element in tag_elements:
            raw_text = element.get_text(strip=True)
            cleaned = self.clean_tag(raw_text)
            if cleaned and len(cleaned) > 1 and cleaned not in tags:
                tags.append(cleaned)
        
        return tags
    
    def collect_tags_from_video(self, video_id: str, existing_keys: Set[str]) -> Optional[List[str]]:
        if video_id in self.processed_videos:
            return None
        
        while self.paused and self.running:
            print("\n⏸ Paused. Press Ctrl+C to exit...")
            time.sleep(2)
        
        if not self.running:
            return None
        
        video_url = f"{self.base_url}/watch?v={video_id}"
        
        try:
            resp = self.session.get(video_url, timeout=15)
            
            if resp.status_code != 200:
                # Mark as processed even on error to avoid infinite retry
                self.processed_videos.add(video_id)
                return None
            
            tags = self.extract_tags_from_video(resp.text)
            
            if tags:
                self.processed_videos.add(video_id)
                for tag in tags:
                    self.all_tags.add(tag)
                    self.tag_counter[tag] += 1
                    
                    if self.is_new_tag(tag, existing_keys):
                        self.new_tags.add(tag)
                
                return tags
            else:
                self.processed_videos.add(video_id)
                return []
            
        except Exception as e:
            # Mark as processed even on exception to avoid infinite retry
            self.processed_videos.add(video_id)
            return None
    
    def print_progress(self, processed: int, total: int, elapsed_minutes: float):
        if processed == 0:
            return
        
        percent = (processed / total * 100) if total > 0 else 0
        videos_per_minute = processed / elapsed_minutes if elapsed_minutes > 0 else 0
        remaining = total - processed
        eta_minutes = remaining / videos_per_minute if videos_per_minute > 0 else 0
        
        print(f"\n📊 Progress: {processed}/{total} videos ({percent:.1f}%)")
        print(f"   Tags: {len(self.all_tags)} total, {len(self.new_tags)} new")
        print(f"   Speed: {videos_per_minute:.1f} videos/min")
        print(f"   ETA: {eta_minutes:.0f} min ({eta_minutes/60:.1f} hours)")
    
    def create_output_files(self):
        # Create tags_updated.json
        final_tags = {category: list(items) for category, items in self.existing_tags.items()}
        
        if self.new_tags:
            for tag in sorted(self.new_tags):
                tag_entry = {
                    "lang": {
                        "zh-rCN": tag,
                        "en": "",
                        "zh-rTW": tag
                    },
                    "search_key": tag
                }
                final_tags["not_sorted"].append(tag_entry)
        
        with open("tags_updated.json", "w", encoding='utf-8') as f:
            json.dump(final_tags, f, ensure_ascii=False, indent=2)
        print("✓ Created tags_updated.json")
        
        # Create new_tags.json
        new_tags_list = []
        for tag in sorted(self.new_tags):
            new_tags_list.append({
                "lang": {
                    "zh-rCN": tag,
                    "en": "",
                    "zh-rTW": tag
                },
                "search_key": tag
            })
        
        with open("new_tags.json", "w", encoding='utf-8') as f:
            json.dump(new_tags_list, f, ensure_ascii=False, indent=2)
        print(f"✓ Created new_tags.json with {len(new_tags_list)} new tags")
        
        # Create new_tags.txt
        with open("new_tags.txt", "w", encoding='utf-8') as f:
            for tag in sorted(self.new_tags):
                f.write(f"{tag}\n")
        print(f"✓ Created new_tags.txt with {len(self.new_tags)} tags")
        
        # Create collection report
        elapsed_hours = (time.time() - self.start_time) / 3600 if self.start_time else 0
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "runtime_hours": elapsed_hours,
            "total_videos_in_queue": len(self.video_queue),
            "videos_processed": len(self.processed_videos),
            "videos_remaining": len(self.video_queue) - len(self.processed_videos),
            "total_unique_tags": len(self.all_tags),
            "new_tags_found": len(self.new_tags),
            "new_tags_list": sorted(list(self.new_tags)),
            "tag_frequency_top50": dict(self.tag_counter.most_common(50))
        }
        
        with open("collection_report.json", "w", encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("✓ Created collection_report.json")
    
    def collect_all_tags_from_file(self, delay: float = 0.3, save_interval: int = 50):
        print(f"\n{'='*60}")
        print(f"HANIME TAG COLLECTOR - USING EXISTING VIDEO IDS")
        print(f"{'='*60}")
        print(f"Target: {self.base_url}")
        print(f"Request delay: {delay}s")
        print(f"Save progress every: {save_interval} videos")
        print("\n⚠ Press Ctrl+C to pause (progress will be saved)")
        
        # Test connection
        try:
            resp = self.session.get(self.base_url, timeout=15)
            if resp.status_code != 200:
                print(f"✗ Cannot access website (status: {resp.status_code})")
                return False
            print("✓ Connected to website")
        except Exception as e:
            print(f"✗ Cannot connect: {e}")
            return False
        
        # Load video IDs from file (NO FETCHING!)
        if not self.video_queue:
            self.video_queue = self.load_video_ids_from_file("video_ids.txt")
            if not self.video_queue:
                print("✗ No video IDs loaded!")
                return False
            self.save_progress()
        
        # Filter out already processed videos
        remaining_videos = [vid for vid in self.video_queue if vid not in self.processed_videos]
        
        if not remaining_videos:
            print("\n✓ All videos already processed!")
            self.create_output_files()
            return True
        
        print(f"\n📊 Processing Summary:")
        print(f"  Total videos in queue: {len(self.video_queue)}")
        print(f"  Already processed: {len(self.processed_videos)}")
        print(f"  Remaining: {len(remaining_videos)}")
        print(f"  Completion: {len(self.processed_videos)/len(self.video_queue)*100:.1f}%")
        
        existing_keys = self.get_existing_search_keys()
        print(f"  Existing tags in database: {len(existing_keys)}")
        
        print("\n🏷️ Collecting tags from remaining videos...")
        print("-" * 60)
        
        self.start_time = time.time()
        processed_count = len(self.processed_videos)
        last_progress_print = 0
        
        for i, video_id in enumerate(remaining_videos, 1):
            if not self.running:
                break
            
            self.collect_tags_from_video(video_id, existing_keys)
            processed_count += 1
            
            # Print progress every 50 videos
            if processed_count - last_progress_print >= 50:
                elapsed_minutes = (time.time() - self.start_time) / 60
                self.print_progress(processed_count, len(self.video_queue), elapsed_minutes)
                last_progress_print = processed_count
                print("-" * 60)
            
            # Save progress at intervals
            if i % save_interval == 0:
                self.save_progress()
                print(f"  💾 Progress saved at {processed_count}/{len(self.video_queue)}")
            
            time.sleep(delay)
        
        self.save_progress()
        
        elapsed_hours = (time.time() - self.start_time) / 3600
        print("\n" + "=" * 60)
        print("📊 FINAL COLLECTION STATISTICS")
        print("=" * 60)
        print(f"  Runtime this session: {elapsed_hours:.2f} hours")
        print(f"  Videos processed total: {len(self.processed_videos)}")
        print(f"  Videos remaining: {len(self.video_queue) - len(self.processed_videos)}")
        print(f"  Total unique tags: {len(self.all_tags)}")
        print(f"  New tags found: {len(self.new_tags)}")
        
        if self.new_tags:
            print(f"\n  Top 20 new tags:")
            sorted_new_tags = sorted([(tag, self.tag_counter.get(tag, 0)) for tag in self.new_tags], 
                                    key=lambda x: x[1], reverse=True)
            for tag, count in sorted_new_tags[:20]:
                print(f"    - {tag} (appears {count} times)")
        
        print("\n📝 Creating output files...")
        self.create_output_files()
        
        return True


def main():
    delay = float(os.environ.get('REQUEST_DELAY', '0.3'))
    save_interval = int(os.environ.get('SAVE_INTERVAL', '50'))
    
    print(f"\nConfiguration:")
    print(f"  REQUEST_DELAY: {delay}s")
    print(f"  SAVE_INTERVAL: {save_interval} videos")
    
    if not os.path.exists("cookies.json"):
        print("✗ cookies.json not found!")
        sys.exit(1)
    
    if not os.path.exists("video_ids.txt"):
        print("✗ video_ids.txt not found!")
        print("  Please make sure video_ids.txt exists in the current directory")
        sys.exit(1)
    
    if not os.path.exists("tags.json"):
        print("⚠ tags.json not found, creating empty...")
        empty_tags = {
            "video_attributes": [],
            "character_relationships": [],
            "characteristics": [],
            "appearance_and_figure": [],
            "story_location": [],
            "story_plot": [],
            "sex_positions": [],
            "not_sorted": []
        }
        with open("tags.json", "w", encoding='utf-8') as f:
            json.dump(empty_tags, f, ensure_ascii=False, indent=2)
    
    collector = HanimeTagCollector(
        base_url="https://hanime1.me",
        cookies_file="cookies.json",
        tags_json_file="tags.json"
    )
    
    success = collector.collect_all_tags_from_file(
        delay=delay,
        save_interval=save_interval
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()