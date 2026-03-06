#!/usr/bin/env python3
"""
CVSE Web Server - Enhanced Version
Supports recording, preview, API debugging, offline changes

Copyright (c) 2026 milkboy, yhtq
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from waitress import serve

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["100 per minute"],
)

current_script_path = os.path.abspath(__file__)

import capnp
from rpc_tools.api_client import (
    CVSE_Client,
    ModifyEntry,
    RPCTime,
    Rank,
    RankProtocol,
    capnp_to_Rank,
    Rank_to_capnp,
    ModifyEntry_to_capnp,
    Index_to_capnp,
    av_to_index,
    bv_to_index
)

CVSE_HOST = "47.104.152.246"
CVSE_PORT = "8663"


def format_video_entry(entry):
    """Format video data for frontend"""
    "这里的逻辑一定要重写"
    
    def Rank2str(rank: Rank):
        match rank:
            case Rank.DOMESTIC:
                return "domestic"
            case Rank.SV:
                return "sv"
            case Rank.UTAU:
                return "utau"
            case _:
                return "unknown"
    ranks = list(map(capnp_to_Rank, entry.ranks))
    ranks = list(map(Rank2str, ranks))
    pub_time = datetime.fromtimestamp(
        entry.pubdate.seconds + entry.pubdate.nanoseconds / 1_000_000_000
    )

    return {
        "avid": entry.avid,
        "bvid": entry.bvid,
        "title": entry.title,
        "uploader": entry.uploader,
        "up_face": entry.upFace,
        "cover": entry.cover,
        "pubdate": pub_time.strftime("%Y-%m-%d %H:%M:%S"),
        "pub_timestamp": entry.pubdate.seconds,
        "duration": entry.duration,
        "tags": list(entry.tags),
        "desc": entry.desc,
        "ranks": ranks,
        "is_examined": entry.isExamined,
        "is_republish": entry.isRepublish,
        "staff_info": entry.staffInfo,
    }


async def get_videos_async(
        keyword: str | None, 
        rank_filter: str | None, 
        examined: str, 
        bvid: str | None, 
        avid: str | None, 
        page: int, 
        page_size: int, 
        date_str: str | None = None):
    """Get videos from CVSE server"""
    now = datetime.now()
    
    if date_str:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d")
        start_week = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_week = start_week + timedelta(days=1)
    else:
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = today
        end_week = today + timedelta(days=1)

    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)

    get_unexamined = examined == "unexamined" or examined == ""
    get_unincluded = True

    indices = await client.getAll(
        get_unexamined,
        get_unincluded,
        RPCTime.from_datetime(start_week),
        RPCTime.from_datetime(end_week),
    )

    if not indices:
        return {
            "data": [],
            "total": 0,
            "date_range": {
                "date": start_week.strftime("%Y年%m月%d日"),
            },
        }

    videos = await client.lookupMetaInfo(list(indices))
    formatted_videos = [format_video_entry(video) for video in videos]

    filtered = formatted_videos

    if keyword:
        filtered = [
            v
            for v in filtered
            if keyword.lower() in v["title"].lower()
            or keyword.lower() in v["uploader"].lower()
        ]

    if bvid:
        filtered = [v for v in filtered if bvid.lower() in v["bvid"].lower()]

    if avid:
        filtered = [v for v in filtered if avid in v["avid"]]

    if rank_filter != "all":
        if rank_filter == "unrecorded":
            filtered = [v for v in filtered if len(v["ranks"]) == 0]
        else:
            filtered = [v for v in filtered if rank_filter in v["ranks"]]

    if examined == "yes":
        filtered = [v for v in filtered if v["is_examined"]]
    elif examined == "no":
        filtered = [v for v in filtered if not v["is_examined"]]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered[start:end]
    
    stats = {
        "total": len(formatted_videos),
        "domestic": len([v for v in formatted_videos if "domestic" in v["ranks"]]),
        "sv": len([v for v in formatted_videos if "sv" in v["ranks"]]),
        "utau": len([v for v in formatted_videos if "utau" in v["ranks"]]),
        "uncheck": len([v for v in formatted_videos if not v["is_examined"]])
    }

    return {
        "data": paginated,
        "total": total,
        "stats": stats,
        "date_range": {
            "date": start_week.strftime("%Y年%m月%d日"),
        },
    }


async def get_video_async(bvid: str):
    """Get single video by bvid"""
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)

    indices = [Index_to_capnp(bv_to_index(bvid))]
    videos = await client.lookupMetaInfo(indices)

    if not videos:
        return None

    return format_video_entry(videos[0])


async def submit_changes_async(changes: list[dict]):
    """Submit batch changes to CVSE server"""
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)

    modify_entries = []
    for change in changes:
        ranks_input = change.get("ranks")
        if ranks_input:
            ranks_list = []
            for r in ranks_input:
                if isinstance(r, int):
                    r = str(r)
                if isinstance(r, str):
                    ranks_list.append(Rank[r.upper()])
            ranks = ranks_list if ranks_list else None
        else:
            ranks = None
        
        assert "avid" in change, "Each change must include 'avid'"
        assert "bvid" in change, "Each change must include 'bvid'"
        
        entry: ModifyEntry = {
            "avid": change["avid"],
            "bvid": change["bvid"],
            "ranks": ranks,
            "is_republish": change.get("is_republish"),
            "staff": change.get("staff_info"),
            "is_examined": change.get("is_examined"),
        }
        modify_entries.append(ModifyEntry_to_capnp(entry))

    await client.updateModifyEntry(modify_entries)
    return len(changes)


async def reCalculate_rankings_async(rank_name: str, index: int, contain_unexamined: bool, lock: bool):
    """recalculate rankings"""
    rank = Rank[rank_name.upper()]
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)
    await client.reCalculateRankings(rank, index, contain_unexamined, lock)
    return f"Recalculated rankings for {rank_name}"

async def check_if_calculated(rank_name: str, index: int, contain_unexamined: bool):
    """check if rankings are calculated"""
    rank = Rank[rank_name.upper()]
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)
    try:
        await client.lookupRankingMetaInfo(rank, index, contain_unexamined)
        return True
    except Exception:
        return False


@app.route("/")
def index():
    """Return frontend page"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.route("/api/health")
@limiter.limit("120 per minute")
def health():
    """API: Health check"""
    return jsonify(
        {
            "status": "healthy",
            "server": "CVSE Backend",
            "time": datetime.now().isoformat(),
        }
    )


@app.route("/api/videos", methods=["GET"])
@limiter.limit("30 per minute")
def get_videos():
    """API: Get videos with filters"""
    try:
        keyword = request.args.get("keyword", "")
        rank_filter = request.args.get("rank", "all")
        examined = request.args.get("examined", "")
        bvid = request.args.get("bvid", "")
        avid = request.args.get("avid", "")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 100))
        date_str = request.args.get("date", "")

        result = asyncio.run(
            capnp.run(
                get_videos_async(
                    keyword, rank_filter, examined, bvid, avid, page, page_size, date_str
                )
            )
        )

        return jsonify(
            {
                "success": True,
                "data": result.get("data", []),
                "total": result.get("total", 0),
                "stats": result.get("stats", {}),
                "page": page,
                "page_size": page_size,
                "date_range": result.get("date_range", {}),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/video/<bvid>", methods=["GET"])
@limiter.limit("60 per minute")
def get_video(bvid):
    """API: Get single video by bvid"""
    try:
        video = asyncio.run(capnp.run(get_video_async(bvid)))

        if not video:
            return jsonify({"success": False, "error": "Video not found"}), 404

        return jsonify({"success": True, "data": video})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/submit-changes", methods=["POST"])
@limiter.limit("10 per minute")
def submit_changes():
    """API: Submit batch changes to CVSE server"""
    try:
        data = request.get_json()
        changes = data.get("changes", [])

        if not changes:
            return jsonify({"success": False, "error": "No changes to submit"})

        count = asyncio.run(capnp.run(submit_changes_async(changes)))

        return jsonify({"success": True, "message": f"Submitted {count} changes"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calculate-rankings", methods=["POST"])
@limiter.limit("1 per minute")
def calculate_rankings():
    """
        API: Calculate rankings for a specific rank
        Costly operation, should be used with caution.
    """
    try:
        data = request.get_json()
        rank_name = data.get("rank", "domestic")
        index = int(data.get("index", 0))
        contain_unexamined = data.get("contain_unexamined", False)
        lock = data.get("lock", False)

        message = asyncio.run(
            capnp.run(
                reCalculate_rankings_async(rank_name, index, contain_unexamined, lock)
            )
        )

        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/debug", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def api_debug():
    """API: Debug endpoint to test raw CVSE API calls"""
    try:
        if request.method == "GET":
            return jsonify(
                {
                    "success": True,
                    "available_endpoints": [
                        "/api/videos - Get videos with filters",
                        "/api/video/<bvid> - Get single video",
                        "/api/submit-changes - Submit batch changes",
                        "/api/calculate-rankings - Calculate rankings",
                        "/api/debug - This debug endpoint",
                    ],
                    "filters": {
                        "keyword": "Search in title/uploader",
                        "rank": "domestic/sv/utau/unrecorded/all",
                        "examined": "yes/no/unexamined",
                        "bvid": "Filter by BV id",
                        "avid": "Filter by AV id",
                    },
                }
            )

        return jsonify({"success": True, "message": "Debug endpoint working"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def main():
    host = os.getenv("CVSE_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("CVSE_SERVER_PORT", "25123"))
    print("Starting CVSE server (Enhanced Version)...")
    print(f"Visit: http://{host}:{port}")
    serve(app, host=host, port=port)
