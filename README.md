# YouTube_Scraper

A Python tool for collecting stratified samples of YouTube Shorts videos across different virality tiers to analyze content patterns.

## Overview

This scraper collects YouTube Shorts across different performance tiers (from <1K to 100M+ views) to enable pattern analysis of what makes certain content go viral. It uses YouTube Data API v3 with intelligent quota management and checkpoint systems.

## Features

- **Stratified sampling** across 5 customizable virality tiers
- **Checkpoint system** for resuming interrupted collection
- **Quota management** to stay within YouTube API daily limits (10,000 units)
- **Flexible search parameters** including keywords, time windows, and regions
- **Automatic feature extraction** from video metadata

## Setup

### Prerequisites

- Python 3.7+
- YouTube Data API v3 key ([Get one here](https://developers.google.com/youtube/v3/getting-started))

### Installation

1. Clone the repository:
```bash
git clone https://github.com/GouriDesh/YouTube_Scraper.git
cd YouTube_Scraper
```

2. Install required packages:
```bash
pip install pandas numpy requests python-dotenv
```

3. Create a `.env` file in the root directory:
```bash
YOUTUBE_API_KEY=your_youtube_api_key_here
```

## Usage

### Running the Scraper

```bash
python fixed_youtube_scraper.py
```

The script will:
- Create a `space_video_patterns/` directory
- Collect videos based on configured tiers
- Save progress automatically (resume capability)
- Output results to `space_video_patterns_YYYYMMDD.csv`

### Multi-Day Collection (Important!)

**The scraper is designed to run over multiple days without duplicates:**

- **Checkpoint System**: Progress is saved in `scraping_progress.json` after each tier/batch
- **Resume Capability**: If interrupted or quota exceeded, simply run again the next day
- **No Duplicates**: Already collected video IDs are tracked and skipped
- **Intelligent Quota Usage**: Only searches for videos in incomplete tiers
- **Daily Progress**: Each day's CSV contains ALL videos collected so far (cumulative)

Example multi-day workflow:
```bash
# Day 1: Run until quota limit (~800-900 videos)
python fixed_youtube_scraper.py
# Output: 365 videos collected

# Day 2: Run again - automatically continues
python fixed_youtube_scraper.py  
# Output: 549 videos (includes Day 1 + new)

# Day 3-5: Keep running until target reached
python fixed_youtube_scraper.py
# Final output: 1000 videos
```

### Configuration

Modify these parameters in the script:

#### Virality Tiers
Define view count ranges and target collection sizes:
```python
VIRALITY_TIERS = {
    'mega_viral': {'min_views': 100_000, 'target_count': 300},
    'highly_viral': {'min_views': 50_000, 'max_views': 100_000, 'target_count': 200},
    'moderate': {'min_views': 10_000, 'max_views': 50_000, 'target_count': 200},
    'low': {'min_views': 1_000, 'max_views': 10_000, 'target_count': 200},
    'very_low': {'min_views': 100, 'max_views': 1_000, 'target_count': 100},
}
```

#### Search Keywords
Keywords used to find relevant videos:
```python
SPACE_KEYWORDS = ["space", "NASA", "ISS", "JWST", ...]  # Customize as needed
```

#### Time Windows
Controls the time periods for video collection to ensure diverse temporal sampling:
```python
TIME_WINDOWS = [
    {'days_back': 365, 'weight': 0.5},    # 50% of searches: Past year
    {'days_back': 730, 'weight': 0.3},    # 30% of searches: Past 2 years
    {'days_back': 30, 'weight': 0.2},     # 20% of searches: Past month
]
```

**Why Time Windows matter:**
- **Avoids recency bias** - Captures both recent and established viral content
- **Works around API limits** - YouTube caps results at ~500-600 per query
- **Diverse sampling** - Different time periods may have different viral patterns
- **Captures viral lifecycles** - Some videos gain views slowly over time

## Output

### Files Generated

1. **Main dataset**: `space_video_patterns_YYYYMMDD.csv`
   - Contains all collected video metadata
   - Features: video_id, title, view_count, duration, engagement metrics, etc.

2. **Checkpoint file**: `scraping_progress.json`
   - Tracks collection progress
   - Allows resuming if interrupted

3. **Quota tracker**: `quota_status.json`
   - Monitors API usage

### Data Fields

Each video record includes:
- Basic info: video_id, title, channel_title, published_at
- Metrics: view_count, like_count, comment_count, views_per_hour
- Engineered features: title_length, has_emoji, has_question, caps_ratio
- Video details: duration_seconds, tags

## Downstream Analysis

### Regrouping Data for Analysis

After collection, you may want to regroup the data for better statistical analysis:

```python
import pandas as pd

# Load collected data
df = pd.read_csv('space_video_patterns_YYYYMMDD.csv')

# Regroup into 3 balanced tiers
df['tier'] = pd.cut(df['view_count'], 
                    bins=[0, 10000, 100000, float('inf')],
                    labels=['low_performing', 'moderate_performing', 'high_performing'])
```

### Example Analysis Scripts

*(Coming soon - additional analysis scripts will be added)*

## API Quota Notes

YouTube API daily quota: 10,000 units
- Search request: 100 units
- Video details request: 1 unit per video

The scraper automatically:
- Tracks usage in real-time
- Saves progress between runs
- Stops before exceeding limits

## Troubleshooting

**Common Issues:**

1. **Quota exceeded**: Wait until midnight Pacific Time for quota reset
2. **Few results in middle tiers**: This reflects actual distribution of viral content
3. **Slow collection**: Adjust `MAX_RESULTS_PER_SEARCH` and `TIME_WINDOWS`

## License

MIT License - See LICENSE file for details

## Author

**Gouri Deshpande** - [GouriDesh](https://github.com/GouriDesh)

## Acknowledgments

- YouTube Data API v3 documentation
- Python community for excellent data science libraries
