#!/usr/bin/env python3
"""
CVSE Web Server - Simplified Version
Core functionality only, fetches real data
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Setup paths
current_script_path = os.path.abspath(__file__)
sys.path.append(os.path.join(os.path.dirname(current_script_path), "CVSE-GatheringTools"))
sys.path.append(os.path.join(os.path.dirname(current_script_path), "CVSE-GatheringTools/CVSE-API"))

# Import CVSE related modules
import capnp
import CVSE_capnp
from api_client import CVSE_Client, RPCTime, Rank, capnp_to_Rank

def format_video_entry(entry):
    """Format video data for frontend"""
    ranks = list(map(capnp_to_Rank, entry.ranks))
    pub_time = datetime.fromtimestamp(entry.pubdate.seconds + entry.pubdate.nanoseconds / 1_000_000_000)
    
    return {
        "avid": entry.avid,
        "bvid": entry.bvid,
        "title": entry.title,
        "uploader": entry.uploader,
        "pubdate": pub_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": entry.duration,
        "tags": list(entry.tags),
        "ranks": [rank.value for rank in ranks],
        "is_examined": entry.isExamined,
        "is_republish": entry.isRepublish
    }

async def get_weekly_data():
    """Fetch weekly video data from CVSE server"""
    # Calculate this week's time range
    now = datetime.now()
    end_week = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday() - 5)
    start_week = end_week - timedelta(days=7)
    
    # Connect to CVSE server
    client = await CVSE_Client.create("47.104.152.246", "8663")
    
    # Get video indices
    entries = await client.getAll(True, True, RPCTime.from_datetime(start_week), RPCTime.from_datetime(end_week))
    
    if not entries:
        return {"success": True, "data": [], "stats": {"total": 0, "domestic": 0, "sv": 0, "utau": 0}}
    
    # Get detailed information
    videos = await client.lookupMetaInfo(entries)
    formatted_videos = [format_video_entry(video) for video in videos]
    
    # Calculate statistics
    stats = {
        "total": len(formatted_videos),
        "domestic": len([v for v in formatted_videos if "domestic" in v["ranks"]]),
        "sv": len([v for v in formatted_videos if "sv" in v["ranks"]]),
        "utau": len([v for v in formatted_videos if "utau" in v["ranks"]])
    }
    
    return {
        "success": True,
        "data": formatted_videos,
        "stats": stats,
        "week_range": {
            "start": start_week.strftime("%Y年%m月%d日"),
            "end": end_week.strftime("%Y年%m月%d日")
        }
    }

@app.route('/')
def index():
    """Return frontend page"""
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/weekly-data')
def weekly_data():
    """API: Get weekly data"""
    try:
        result = asyncio.run(capnp.run(get_weekly_data()))
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/health')
def health():
    """API: Health check"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("Starting CVSE server...")
    print("Visit: http://localhost:5123")
    app.run(host='0.0.0.0', port=5123, debug=False)