"""
YouTube Space Videos Pattern Analysis Scraper
Goal: Analyze patterns among viral space videos by collecting a stratified sample
"""

import os
import time
import random
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import requests
from typing import Dict, List, Any
import json
import re

# ==================== CONFIGURATION ====================
# Sampling strategy for pattern analysis
# Lowered thresholds to capture more videos
VIRALITY_TIERS = {
    'mega_viral': {'min_views': 100_000, 'target_count': 300},    # Lowered from 500k
    'highly_viral': {'min_views': 50_000, 'max_views': 100_000, 'target_count': 200},
    'moderate': {'min_views': 10_000, 'max_views': 50_000, 'target_count': 200},
    'low': {'min_views': 1_000, 'max_views': 10_000, 'target_count': 200},
    'very_low': {'min_views': 100, 'max_views': 1_000, 'target_count': 100},
}

# API Configuration
QUOTA_DAILY_LIMIT = 10000  # YouTube's daily quota
QUOTA_RESERVE = 200  # Keep some quota in reserve
SEARCH_COST = 100  # Each search costs 100 units
VIDEO_DETAILS_COST = 1  # Each video details call costs 1 unit
MAX_RESULTS_PER_SEARCH = 50

# Search parameters
SPACE_KEYWORDS = [
    "space", "NASA", "ISS", "JWST", "James Webb", "SpaceX", 
    "astronomy", "cosmos", "galaxy", "nebula", "black hole",
    "mars", "moon", "asteroid", "comet", "telescope", "universe", "jupiter",
    "star", "planet", "celestial", "rocket", "space facts", "space 4k", 
    "space edit", "earth from space", "stars", "intergalactic", "astronaut",
    "interstellar", "space shorts", "NASA space", "International Space Station",
    "blackhole", "sun", "solar", "lunar", "cosmos universe", "astrophysics", 
    "Solar system", "space size comparison", "space zoom", "webb telescope new images",
    "space compilation", "space timelapse", "hubble images", 
    "space discoveries 2024", "space discoveries 2025",  "universe size", "how big is space", "space comparison",
    "science facts", "amazing facts", "mind blowing space",
    "space didyouknow", "space mindblowing", "space amazing facts",
    "cosmos facts", "universe facts", "astronomy facts",
    "space documentary", "space education", "learn space",
    "viral space", "space compilation", "best space moments",
    # Popular creators/series keywords:
    "kurzgesagt space", "vsauce space", "veritasium space",
    # Trending formats:
    "space explained", "space in 60 seconds", "quick space facts"
]

# Time windows for better coverage
TIME_WINDOWS = [
    {'days_back': 365, 'weight': 0.5},    # Full year - main focus
    {'days_back': 730, 'weight': 0.3},    # 2 years - catch older viral content
    {'days_back': 30, 'weight': 0.2},     # Recent - for fresh content
]

# Output configuration
OUTPUT_DIR = "space_video_patterns"
CHECKPOINT_FILE = "scraping_progress.json"

# ==================== SETUP ====================
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in .env file")

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== HELPER FUNCTIONS ====================
class QuotaManager:
    def __init__(self, daily_limit=QUOTA_DAILY_LIMIT, reserve=QUOTA_RESERVE):
        self.daily_limit = daily_limit
        self.reserve = reserve
        self.used = 0
        self.checkpoint_file = os.path.join(OUTPUT_DIR, "quota_status.json")
        self.load_checkpoint()
    
    def load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
                if data['date'] == datetime.now().strftime('%Y-%m-%d'):
                    self.used = data['used']
    
    def save_checkpoint(self):
        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'used': self.used
            }, f)
    
    def can_use(self, units):
        remaining = self.daily_limit - self.used
        print(f"Quota status: {self.used}/{self.daily_limit} used ({remaining} remaining)")
        return self.used + units < (self.daily_limit - self.reserve)
    
    def use(self, units):
        if not self.can_use(units):
            raise Exception(f"Quota limit reached. Used: {self.used}, Requested: {units}")
        self.used += units
        self.save_checkpoint()
        print(f"Quota used: {self.used}/{self.daily_limit} ({self.used/self.daily_limit*100:.1f}%)")

def safe_api_call(url: str, params: Dict[str, Any], quota_cost: int) -> Dict:
    """Make API call with safety checks and quota management"""
    # Never log the API key
    safe_params = {k: v for k, v in params.items() if k != 'key'}
    safe_params['key'] = 'REDACTED'
    
    # Check quota
    if not quota_manager.can_use(quota_cost):
        raise Exception("Daily quota would be exceeded")
    
    # Make request with retries
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            quota_manager.use(quota_cost)
            time.sleep(0.5)  # Rate limiting
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API call failed (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise

def parse_duration(duration_str):
    """Parse ISO 8601 duration to seconds"""
    if not duration_str:
        return None
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def get_time_window_dates(days_back):
    """Get date range for search"""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    return start_date.isoformat(), end_date.isoformat()

def search_videos(keyword, published_after, published_before, order='relevance'):
    """Search for videos with specific criteria"""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'id',
        'q': keyword,
        'type': 'video',
        'videoDuration': 'short',
        # REMOVED: 'videoCategory': '28',  # Don't restrict to Science category
        'maxResults': MAX_RESULTS_PER_SEARCH,
        'publishedAfter': published_after,
        'publishedBefore': published_before,
        'order': order,
        # 'regionCode': 'US',  # Commented out for global search
        'relevanceLanguage': 'en',  # Keep English
        'key': API_KEY
    }
    
    results = []
    total_results = 0
    
    # Get first page
    response = safe_api_call(url, params, SEARCH_COST)
    if not response:
        return results
    
    video_ids = [item['id']['videoId'] for item in response.get('items', [])]
    results.extend(video_ids)
    total_results = response.get('pageInfo', {}).get('totalResults', 0)
    
    print(f"Found {len(results)} videos for '{keyword}' ({total_results} total available)")
    
    # For pattern analysis, one page is often enough per keyword/time combination
    # This helps us get diversity rather than depth
    
    return results

def get_video_details(video_ids):
    """Get detailed information for videos"""
    url = "https://www.googleapis.com/youtube/v3/videos"
    
    # Process in batches of 50
    all_details = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(batch),
            'key': API_KEY
        }
        
        response = safe_api_call(url, params, VIDEO_DETAILS_COST)
        if response:
            all_details.extend(response.get('items', []))
    
    return all_details

def process_video_details(video_data):
    """Extract relevant features from video data"""
    processed = []
    
    for video in video_data:
        snippet = video.get('snippet', {})
        stats = video.get('statistics', {})
        content = video.get('contentDetails', {})
        
        # Parse duration
        duration_sec = parse_duration(content.get('duration'))
        if not duration_sec or duration_sec > 60:
            continue  # Skip non-shorts
        
        # Calculate views per hour
        published_at = snippet.get('publishedAt')
        try:
            pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
            views = int(stats.get('viewCount', 0))
            vph = views / max(age_hours, 1)
        except:
            vph = 0
        
        processed.append({
            'video_id': video['id'],
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'channel_title': snippet.get('channelTitle', ''),
            'published_at': published_at,
            'duration_seconds': duration_sec,
            'view_count': int(stats.get('viewCount', 0)),
            'like_count': int(stats.get('likeCount', 0)),
            'comment_count': int(stats.get('commentCount', 0)),
            'views_per_hour': vph,
            'title_length': len(snippet.get('title', '')),
            'title_word_count': len(snippet.get('title', '').split()),
            'has_emoji': bool(re.search(r'[\U0001F300-\U0001F9FF]', snippet.get('title', ''))),
            'has_question': '?' in snippet.get('title', ''),
            'has_exclamation': '!' in snippet.get('title', ''),
            'caps_ratio': sum(1 for c in snippet.get('title', '') if c.isupper()) / max(len(snippet.get('title', '')), 1),
            'tags': '|'.join(snippet.get('tags', [])),
            'tag_count': len(snippet.get('tags', []))
        })
    
    return processed

# ==================== MAIN SCRAPING LOGIC ====================
def scrape_stratified_sample():
    """Scrape videos across different virality tiers"""
    quota_manager = QuotaManager()
    all_videos = []
    
    # Load checkpoint if exists
    checkpoint_path = os.path.join(OUTPUT_DIR, CHECKPOINT_FILE)
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
    else:
        checkpoint = {'collected': {}, 'seen_ids': []}
    
    seen_ids = set(checkpoint['seen_ids'])
    
    print("=== Starting Stratified Sampling ===")
    print(f"Target distribution: {sum(tier['target_count'] for tier in VIRALITY_TIERS.values())} total videos")
    
    # Collect videos for each tier
    for tier_name, tier_config in VIRALITY_TIERS.items():
        print(f"\n--- Collecting {tier_name} tier ---")
        tier_videos = checkpoint['collected'].get(tier_name, [])
        
        if len(tier_videos) >= tier_config['target_count']:
            print(f"Already collected {len(tier_videos)}/{tier_config['target_count']} videos")
            all_videos.extend(tier_videos)
            continue
        
        attempts = 0
        while len(tier_videos) < tier_config['target_count'] and attempts < 30:
            attempts += 1
            
            # Sample keyword
            keyword = random.choice(SPACE_KEYWORDS)
            
            # Rotate through different search strategies based on tier
            if tier_name in ['very_low', 'low']:
                # For low-view videos, prioritize recent uploads
                order = 'date'
                time_window = TIME_WINDOWS[2]  # Use 30-day window
            elif tier_name in ['mega_viral']:
                # For viral videos, use viewCount
                order = 'viewCount'
                time_window = TIME_WINDOWS[0]  # Use full year
            else:
                # For middle tiers, rotate strategies
                strategies = [
                    ('relevance', TIME_WINDOWS[0]),
                    ('viewCount', TIME_WINDOWS[1]),
                    ('rating', TIME_WINDOWS[0]),
                    ('date', TIME_WINDOWS[2])
                ]
                order, time_window = strategies[attempts % len(strategies)]
            
            start_date, end_date = get_time_window_dates(time_window['days_back'])
            
            print(f"\nAttempt {attempts}: Searching '{keyword}' in last {time_window['days_back']} days (order: {order})")
            
            try:
                # Search for videos
                video_ids = search_videos(keyword, start_date, end_date, order)
                new_ids = [vid for vid in video_ids if vid not in seen_ids]
                
                if not new_ids:
                    continue
                
                # Get details
                video_details = get_video_details(new_ids[:20])  # Limit batch size
                processed = process_video_details(video_details)
                
                # Filter by tier requirements
                for video in processed:
                    views = video['view_count']
                    min_views = tier_config.get('min_views', 0)
                    max_views = tier_config.get('max_views', float('inf'))
                    
                    if min_views <= views < max_views:
                        tier_videos.append(video)
                        seen_ids.add(video['video_id'])
                        
                        if len(tier_videos) >= tier_config['target_count']:
                            break
                
                print(f"Collected {len(tier_videos)}/{tier_config['target_count']} for {tier_name}")
                
                # Save checkpoint
                checkpoint['collected'][tier_name] = tier_videos
                checkpoint['seen_ids'] = list(seen_ids)
                with open(checkpoint_path, 'w') as f:
                    json.dump(checkpoint, f)
                
            except Exception as e:
                print(f"Error: {e}")
                if "quota" in str(e).lower():
                    print("Quota limit reached. Run again tomorrow to continue.")
                    break
        
        all_videos.extend(tier_videos)
    
    # Save final dataset
    if all_videos:
        df = pd.DataFrame(all_videos)
        output_path = os.path.join(OUTPUT_DIR, f"space_videos_patterns_{datetime.now().strftime('%Y%m%d')}.csv")
        df.to_csv(output_path, index=False)
        print(f"\n=== Scraping Complete ===")
        print(f"Total videos collected: {len(df)}")
        print(f"Distribution by tier:")
        for tier_name in VIRALITY_TIERS:
            count = len([v for v in all_videos if v in checkpoint['collected'].get(tier_name, [])])
            print(f"  {tier_name}: {count}")
        print(f"Output saved to: {output_path}")
        
        # Quick statistics
        print("\n=== Quick Statistics ===")
        print(f"View count range: {df['view_count'].min():,} - {df['view_count'].max():,}")
        print(f"Average title length: {df['title_word_count'].mean():.1f} words")
        print(f"Videos with questions: {df['has_question'].sum()} ({df['has_question'].mean()*100:.1f}%)")
        print(f"Videos with emojis: {df['has_emoji'].sum()} ({df['has_emoji'].mean()*100:.1f}%)")

if __name__ == "__main__":
    # Initialize quota manager globally
    quota_manager = QuotaManager()
    
    print("YouTube Space Videos Pattern Analysis Scraper")
    print("=" * 50)
    print("This script will collect a stratified sample of space videos")
    print("across different virality tiers for pattern analysis.")
    print(f"Daily quota limit: {QUOTA_DAILY_LIMIT}")
    print(f"Current quota used: {quota_manager.used}")
    print("=" * 50)
    
    scrape_stratified_sample()