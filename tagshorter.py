#!/usr/bin/env python3
"""
Hanime Tag Collector - Full collection mode with anti-blocking
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
from typing import Set, List, Dict, Optional
from datetime import datetime

class HanimeTagCollector:
    def __init__(self, base_url: str = "https://hanime1.me", cookies_file: str = "cookies.json", 
                 tags_json_file: str = "tags.json", progress_file: str = "collector_progress.json"):
        self.base_url = base_url
        self.progress_file = progress_file
        
        # Random impersonation to avoid detection
        impersonates = ["chrome120", "chrome119", "chrome118", "safari15_5", "edge101"]
        self.session = requests.Session(impersonate=random.choice(impersonates))
        
        # Rotate user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': base_url,
        })
        
        # Load cookies
        if os.path.exists(cookies_file):
            self.load_cookies(cookies_file)
        else:
            print("⚠ No cookies file found")
        
        # Load existing tags
        self.existing_tags = self.load_existing_tags(tags_json_file)
        
        # Load or initialize collections
        self.load_progress()
        
        # Statistics
        self.start_time = None
        self.request_count = 0
        
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
        """Load previously collected data for resume capability"""
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
    
    def save_progress(self):
        """Save current progress"""
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
        """Get all search_keys from existing tags.json"""
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
    
    def get_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Make request with retry logic"""
        for attempt in range(max_retries):
            try:
                # Add random delay between retries
                if attempt > 0:
                    time.sleep(2 ** attempt)  # Exponential backoff
                
                resp = self.session.get(url, timeout=20)
                self.request_count += 1
                
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 403:
                    # Rotate impersonation on 403
                    impersonates = ["chrome120", "chrome119", "safari15_5"]
                    self.session = requests.Session(impersonate=random.choice(impersonates))
                    print(f"  Rotated impersonation due to 403")
                    continue
                else:
                    return None
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"  Failed after {max_retries} attempts: {e}")
                continue
        
        return None
    
    def get_all_video_ids_unlimited(self) -> List[str]:
        """Get ALL video IDs from ALL search pages (unlimited)"""
        video_ids = []
        page = 1
        consecutive_empty = 0
        
        print(f"\n📹 Fetching ALL video IDs from ALL pages...")
        print("   This may take a while...")
        
        while consecutive_empty < 3:  # Stop after 3 consecutive empty pages
            try:
                if page == 1:
                    url = f"{self.base_url}/search"
                else:
                    url = f"{self.base_url}/search?page={page}"
                
                print(f"  Fetching page {page}...", end=" ")
                resp = self.get_with_retry(url)
                
                if not resp or resp.status_code != 200:
                    print(f"Failed (status {resp.status_code if resp else 'None'})")
                    consecutive_empty += 1
                    page += 1
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'watch\?v=\d+'))
                
                if not links:
                    print("No videos found")
                    consecutive_empty += 1
                    page += 1
                    continue
                
                consecutive_empty = 0
                new_count = 0
                
                for link in links:
                    href = link.get('href')
                    match = re.search(r'v=(\d+)', href)
                    if match and match.group(1) not in video_ids:
                        video_ids.append(match.group(1))
                        new_count += 1
                
                print(f"Found {new_count} new videos (Total: {len(video_ids)})")
                
                # If we got less than a full page, we might be near the end
                if len(links) < 24:
                    print(f"  Less than full page ({len(links)} videos), checking next page...")
                
                page += 1
                time.sleep(random.uniform(0.5, 1.0))  # Random delay
                
                # Safety limit - prevent infinite loop (max 500 pages ~ 12,000 videos)
                if page > 500:
                    print(f"\n  Reached page limit (500 pages). Stopping.")
                    break
                
            except Exception as e:
                print(f"Error: {e}")
                consecutive_empty += 1
                page += 1
                time.sleep(2)
        
        print(f"\n✓ TOTAL video IDs collected: {len(video_ids)}")
        return video_ids
    
    def collect_tags_from_video(self, video_id: str, existing_keys: Set[str]) -> Optional[List[str]]:
        if video_id in self.processed_videos:
            return None
        
        video_url = f"{self.base_url}/watch?v={video_id}"
        
        try:
            resp = self.get_with_retry(video_url)
            
            if not resp or resp.status_code != 200:
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
            return None
    
    def print_progress(self, processed: int, total: int, elapsed_minutes: float):
        """Print progress statistics"""
        if processed == 0:
            return
        
        percent = (processed / total * 100) if total > 0 else 0
        tags_per_video = len(self.all_tags) / processed
        new_per_video = len(self.new_tags) / processed
        videos_per_minute = processed / elapsed_minutes if elapsed_minutes > 0 else 0
        remaining = total - processed
        eta_minutes = remaining / videos_per_minute if videos_per_minute > 0 else 0
        
        print(f"\n📊 Progress: {processed}/{total} videos ({percent:.1f}%)")
        print(f"   Tags: {len(self.all_tags)} total, {len(self.new_tags)} new")
        print(f"   Speed: {videos_per_minute:.1f} videos/min")
        print(f"   ETA: {eta_minutes:.0f} min ({eta_minutes/60:.1f} hours)")
    
    def create_output_files(self):
        """Create all output files"""
        
        # 1. Create tags_updated.json (complete merged file)
        final_tags = {category: list(items) for category, items in self.existing_tags.items()}
        
        # Add new tags to not_sorted
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
        
        # 2. Create new_tags.json (only new tags)
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
        
        # 3. Create new_tags.txt (tag strings only)
        with open("new_tags.txt", "w", encoding='utf-8') as f:
            for tag in sorted(self.new_tags):
                f.write(f"{tag}\n")
        print(f"✓ Created new_tags.txt with {len(self.new_tags)} tags")
        
        # 4. Create video_ids.txt (all video IDs collected)
        if self.video_queue:
            with open("video_ids.txt", "w", encoding='utf-8') as f:
                for vid in self.video_queue:
                    f.write(f"{vid}\n")
            print(f"✓ Created video_ids.txt with {len(self.video_queue)} video IDs")
        
        # 5. Create collection report
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
    
    def collect_all_tags_unlimited(self, delay: float = 0.3, save_interval: int = 50):
        """Collect tags from ALL videos (unlimited)"""
        
        print(f"\n{'='*60}")
        print(f"HANIME TAG COLLECTOR - FULL COLLECTION MODE")
        print(f"{'='*60}")
        print(f"Target: {self.base_url}")
        print(f"Request delay: {delay}s")
        print(f"Save progress every: {save_interval} videos")
        
        # Test connection with retry
        print("Testing connection...")
        resp = self.get_with_retry(self.base_url, max_retries=5)
        if not resp or resp.status_code != 200:
            print(f"✗ Cannot access website after retries")
            return False
        print("✓ Connected to website")
        
        # Get ALL video IDs (unlimited)
        if not self.video_queue:
            self.video_queue = self.get_all_video_ids_unlimited()
            self.save_progress()
        
        if not self.video_queue:
            print("✗ No video IDs found!")
            return False
        
        # Filter out already processed videos
        remaining_videos = [vid for vid in self.video_queue if vid not in self.processed_videos]
        
        if not remaining_videos:
            print("\n✓ All videos already processed!")
            self.create_output_files()
            return True
        
        print(f"\n📊 Processing Summary:")
        print(f"  Total videos in queue: {len(self.video_queue)}")
        print(f"  Already processed: {len(self.processed_videos)}")
        print(f"  Remaining to process: {len(remaining_videos)}")
        
        # Get existing keys for deduplication
        existing_keys = self.get_existing_search_keys()
        print(f"  Existing tags in database: {len(existing_keys)}")
        
        # Start collection
        print("\n🏷️ Collecting tags from videos...")
        print("   This will take several hours...")
        print("-" * 60)
        
        self.start_time = time.time()
        processed_count = len(self.processed_videos)
        last_progress_print = 0
        
        for i, video_id in enumerate(remaining_videos, 1):
            tags = self.collect_tags_from_video(video_id, existing_keys)
            
            if tags is not None:
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
            
            # Random delay to avoid detection
            time.sleep(delay + random.uniform(0, 0.2))
            
            # Check runtime - GitHub Actions has 6 hour limit, stop at 5.5 hours
            if self.start_time and (time.time() - self.start_time) > 5.5 * 3600:
                print("\n⚠ Approaching 5.5 hour limit. Saving progress and stopping...")
                break
        
        # Save final progress
        self.save_progress()
        
        # Print final statistics
        elapsed_hours = (time.time() - self.start_time) / 3600
        print("\n" + "=" * 60)
        print("📊 FINAL COLLECTION STATISTICS")
        print("=" * 60)
        print(f"  Runtime: {elapsed_hours:.2f} hours")
        print(f"  Videos processed: {len(self.processed_videos)}")
        print(f"  Videos remaining: {len(self.video_queue) - len(self.processed_videos)}")
        print(f"  Total unique tags: {len(self.all_tags)}")
        print(f"  New tags found: {len(self.new_tags)}")
        print(f"  Total requests made: {self.request_count}")
        
        if self.new_tags:
            print(f"\n  Top 30 new tags (by frequency):")
            sorted_new_tags = sorted([(tag, self.tag_counter.get(tag, 0)) for tag in self.new_tags], 
                                    key=lambda x: x[1], reverse=True)
            for tag, count in sorted_new_tags[:30]:
                print(f"    - {tag} (appears {count} times)")
        
        # Create output files
        print("\n📝 Creating output files...")
        self.create_output_files()
        
        return True


def main():
    # Configuration from environment variables (for GitHub Actions)
    delay = float(os.environ.get('REQUEST_DELAY', '0.5'))  # Increased default delay
    save_interval = int(os.environ.get('SAVE_INTERVAL', '50'))
    
    print(f"\nConfiguration:")
    print(f"  REQUEST_DELAY: {delay}s")
    print(f"  SAVE_INTERVAL: {save_interval} videos")
    
    # Check for cookies
    if not os.path.exists("cookies.json"):
        print("✗ cookies.json not found!")
        print("  Please add your cookies as a GitHub secret")
        sys.exit(1)
    
    # Check for tags.json
    if not os.path.exists("tags.json"):
        print("⚠ tags.json not found, starting fresh")
        # Create empty tags.json
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
    
    # Run collector
    collector = HanimeTagCollector(
        base_url="https://hanime1.me",
        cookies_file="cookies.json",
        tags_json_file="tags.json"
    )
    
    success = collector.collect_all_tags_unlimited(
        delay=delay,
        save_interval=save_interval
    )
    
    if success:
        print("\n✅ Collection complete!")
        sys.exit(0)
    else:
        print("\n❌ Collection failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()