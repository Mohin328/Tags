#!/usr/bin/env python3
"""
Hanime Tag Collector - GitHub Actions compatible version
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import json
import re
import os
import sys
from collections import Counter
from typing import Set, List, Dict, Optional
from datetime import datetime

class HanimeTagCollector:
    def __init__(self, base_url: str = "https://hanime1.me", cookies_file: str = "cookies.json", 
                 tags_json_file: str = "tags.json", progress_file: str = "collector_progress.json"):
        self.base_url = base_url
        self.progress_file = progress_file
        self.session = requests.Session(impersonate="chrome120")
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': base_url,
        })
        
        # Load cookies from GitHub secret
        if os.path.exists(cookies_file):
            self.load_cookies(cookies_file)
        
        # Load existing tags
        self.existing_tags = self.load_existing_tags(tags_json_file)
        
        # Load or initialize collections
        self.load_progress()
        
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
                "timestamp": time.time()
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
    
    def get_all_video_ids(self, max_pages: int = 50) -> List[str]:
        """Get video IDs from search pages"""
        video_ids = []
        
        print(f"\n📹 Fetching video IDs (max {max_pages} pages)...")
        
        for page in range(1, max_pages + 1):
            try:
                if page == 1:
                    url = f"{self.base_url}/search"
                else:
                    url = f"{self.base_url}/search?page={page}"
                
                resp = self.session.get(url, timeout=15)
                
                if resp.status_code != 200:
                    break
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'watch\?v=\d+'))
                
                if not links:
                    break
                
                for link in links:
                    href = link.get('href')
                    match = re.search(r'v=(\d+)', href)
                    if match and match.group(1) not in video_ids:
                        video_ids.append(match.group(1))
                
                print(f"  Page {page}: Found {len(video_ids)} total videos")
                time.sleep(0.3)
                
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break
        
        print(f"\n✓ Total video IDs found: {len(video_ids)}")
        return video_ids
    
    def collect_tags_from_video(self, video_id: str, existing_keys: Set[str]) -> Optional[List[str]]:
        if video_id in self.processed_videos:
            return None
        
        video_url = f"{self.base_url}/watch?v={video_id}"
        
        try:
            resp = self.session.get(video_url, timeout=15)
            
            if resp.status_code != 200:
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
    
    def create_output_files(self):
        """Create all output files for GitHub Actions"""
        
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
        
        # 2. Create new_tags.json (only new tags, same format as not_sorted)
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
        
        # 3. Create new_tags.txt (only the tag strings, one per line)
        with open("new_tags.txt", "w", encoding='utf-8') as f:
            for tag in sorted(self.new_tags):
                f.write(f"{tag}\n")
        print(f"✓ Created new_tags.txt with {len(self.new_tags)} tags")
        
        # 4. Create collection report
        report = {
            "timestamp": datetime.now().isoformat(),
            "videos_processed": len(self.processed_videos),
            "total_unique_tags": len(self.all_tags),
            "new_tags_found": len(self.new_tags),
            "new_tags_list": sorted(list(self.new_tags))
        }
        
        with open("collection_report.json", "w", encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("✓ Created collection_report.json")
    
    def collect_all_tags(self, max_videos: Optional[int] = 500, max_pages: int = 50, delay: float = 0.3):
        """Main collection method for GitHub Actions (limited runtime)"""
        
        print(f"\n{'='*60}")
        print(f"HANIME TAG COLLECTOR - GITHUB ACTIONS MODE")
        print(f"{'='*60}")
        
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
        
        # Get or load video queue
        if not self.video_queue:
            self.video_queue = self.get_all_video_ids(max_pages=max_pages)
            self.save_progress()
        
        # Filter out processed videos
        remaining_videos = [vid for vid in self.video_queue if vid not in self.processed_videos]
        
        if max_videos:
            remaining_videos = remaining_videos[:max_videos]
        
        if not remaining_videos:
            print("\n✓ All videos already processed!")
            self.create_output_files()
            return True
        
        print(f"\n📊 Processing {len(remaining_videos)} new videos...")
        
        # Get existing keys for deduplication
        existing_keys = self.get_existing_search_keys()
        print(f"  Existing tags: {len(existing_keys)}")
        
        # Process videos
        print("\n🏷️ Collecting tags...")
        print("-" * 60)
        
        processed_count = len(self.processed_videos)
        
        for i, video_id in enumerate(remaining_videos, 1):
            tags = self.collect_tags_from_video(video_id, existing_keys)
            
            if tags is not None:
                processed_count += 1
                
                # Print progress
                if processed_count % 20 == 0 or i == len(remaining_videos):
                    print(f"  Progress: {processed_count}/{len(self.video_queue)} videos")
                    print(f"  Tags: {len(self.all_tags)} total, {len(self.new_tags)} new")
                    print("-" * 60)
            
            # Save progress every 50 videos
            if i % 50 == 0:
                self.save_progress()
            
            time.sleep(delay)
        
        # Save final progress
        self.save_progress()
        
        # Print statistics
        print("\n" + "=" * 60)
        print("📊 COLLECTION STATISTICS")
        print("=" * 60)
        print(f"  Videos processed: {len(self.processed_videos)}")
        print(f"  Total unique tags: {len(self.all_tags)}")
        print(f"  New tags found: {len(self.new_tags)}")
        
        if self.new_tags:
            print(f"\n  Sample new tags:")
            for tag in sorted(list(self.new_tags))[:20]:
                count = self.tag_counter.get(tag, 0)
                print(f"    - {tag} (appears {count} times)")
        
        # Create output files
        print("\n📝 Creating output files...")
        self.create_output_files()
        
        return True


def main():
    # GitHub Actions environment variables
    max_videos = int(os.environ.get('MAX_VIDEOS', 500))
    max_pages = int(os.environ.get('MAX_PAGES', 50))
    delay = float(os.environ.get('REQUEST_DELAY', 0.3))
    
    print(f"\nConfiguration from environment:")
    print(f"  MAX_VIDEOS: {max_videos}")
    print(f"  MAX_PAGES: {max_pages}")
    print(f"  REQUEST_DELAY: {delay}s")
    
    # Check for cookies
    if not os.path.exists("cookies.json"):
        print("✗ cookies.json not found!")
        print("  Please add your cookies as a GitHub secret")
        sys.exit(1)
    
    # Check for tags.json
    if not os.path.exists("tags.json"):
        print("⚠ tags.json not found, starting fresh")
    
    # Run collector
    collector = HanimeTagCollector(
        base_url="https://hanime1.me",
        cookies_file="cookies.json",
        tags_json_file="tags.json"
    )
    
    success = collector.collect_all_tags(
        max_videos=max_videos,
        max_pages=max_pages,
        delay=delay
    )
    
    if success:
        print("\n✅ Collection complete!")
        sys.exit(0)
    else:
        print("\n❌ Collection failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
