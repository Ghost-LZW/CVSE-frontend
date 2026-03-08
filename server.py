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
        date_str: str | None = None,
        auth_key: str | None = None):
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

    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)

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


async def get_video_async(bvid: str, auth_key: str | None = None):
    """Get single video by bvid"""
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)

    indices = [Index_to_capnp(bv_to_index(bvid))]
    videos = await client.lookupMetaInfo(indices)

    if not videos:
        return None

    return format_video_entry(videos[0])


async def submit_changes_async(changes: list[dict], auth_key: str | None = None):
    """Submit batch changes to CVSE server"""
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)

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


async def reCalculate_rankings_async(rank_name: str, index: int, contain_unexamined: bool, lock: bool, auth_key: str | None = None):
    """recalculate rankings"""
    rank = Rank[rank_name.upper()]
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)
    await client.reCalculateRankings(rank, index, contain_unexamined, lock)
    return f"Recalculated rankings for {rank_name}"

async def check_if_calculated(rank_name: str, index: int, contain_unexamined: bool, auth_key: str | None = None):
    """check if rankings are calculated"""
    rank = Rank[rank_name.upper()]
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)
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


def get_auth_key_from_request():
    """Get auth key from request header or args"""
    auth_key = request.headers.get("X-Auth-Key") or request.args.get("auth_key")
    if auth_key:
        return auth_key
    return None


@app.route("/api/auth/validate", methods=["POST"])
@limiter.limit("30 per minute")
def validate_auth():
    """API: Validate auth key by testing a simple CVSE connection"""
    try:
        data = request.get_json()
        auth_key = data.get("auth_key")
        
        if not auth_key:
            return jsonify({"success": False, "error": "No auth key provided"}), 400
        
        async def test_auth():
            client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)
            try:
                await client.lookupRankingMetaInfo(Rank.DOMESTIC, 0, False)
                return True
            except Exception:
                return False
        
        is_valid = asyncio.run(capnp.run(test_auth()))
        
        if is_valid:
            return jsonify({"success": True, "valid": True, "message": "Auth key is valid"})
        else:
            return jsonify({"success": True, "valid": False, "message": "Auth key may be invalid"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
        auth_key = get_auth_key_from_request()

        result = asyncio.run(
            capnp.run(
                get_videos_async(
                    keyword, rank_filter, examined, bvid, avid, page, page_size, date_str, auth_key
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
        auth_key = get_auth_key_from_request()
        video = asyncio.run(capnp.run(get_video_async(bvid, auth_key)))

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
        auth_key = get_auth_key_from_request()

        if not changes:
            return jsonify({"success": False, "error": "No changes to submit"})

        count = asyncio.run(capnp.run(submit_changes_async(changes, auth_key)))

        return jsonify({"success": True, "message": f"Submitted {count} changes"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calculate-rankings", methods=["POST"])
@limiter.limit("5 per minute")
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
        auth_key = get_auth_key_from_request()

        message = asyncio.run(
            capnp.run(
                reCalculate_rankings_async(rank_name, index, contain_unexamined, lock, auth_key)
            )
        )

        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


async def get_ranking_preview_async(rank_name: str, index: int, contain_unexamined: bool, auth_key: str | None = None):
    """Get ranking preview data"""
    import aiohttp
    
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT, auth_key)
    
    try:
        stat = await client.lookupRankingMetaInfo(Rank[rank_name.upper()], index, contain_unexamined)
    except Exception:
        return {
            "stat": {
                "count": 0,
                "totalView": 0,
                "totalLike": 0,
                "totalCoin": 0,
                "totalFavorite": 0,
                "totalNew": 0,
            },
            "entries": [],
        }
    
    if stat.count == 0:
        return {
            "stat": {
                "count": 0,
                "totalView": 0,
                "totalLike": 0,
                "totalCoin": 0,
                "totalFavorite": 0,
                "totalNew": 0,
            },
            "entries": [],
        }
    
    indices = await client.getAllRankingInfo(Rank[rank_name.upper()], index, contain_unexamined, 1, min(stat.count + 1, 51))
    
    entries = await client.lookupRankingInfo(Rank[rank_name.upper()], index, contain_unexamined, list(indices))
    
    bvids = [e.bvid for e in entries]
    
    video_info_map = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for bvid in bvids[:50]:
            try:
                async with session.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0:
                            video_info_map[bvid] = {
                                "title": data["data"].get("title", ""),
                                "uploader": data["data"].get("owner", {}).get("name", ""),
                                "cover": data["data"].get("pic", ""),
                                "desc": data["data"].get("desc", ""),
                            }
            except Exception:
                pass
    
    formatted_entries = []
    for entry in entries:
        video_info = video_info_map.get(entry.bvid, {})
        formatted_entries.append({
            "rank": entry.rank,
            "bvid": entry.bvid,
            "avid": entry.avid,
            "title": video_info.get("title", ""),
            "uploader": video_info.get("uploader", ""),
            "cover": video_info.get("cover", ""),
            "view": entry.view,
            "like": entry.like,
            "coin": entry.coin,
            "favorite": entry.favorite,
            "share": entry.share,
            "totalScore": entry.totalScore,
            "isNew": entry.isNew,
        })
    
    formatted_entries.sort(key=lambda x: x["rank"])
    
    return {
        "stat": {
            "count": stat.count,
            "totalView": stat.totalView,
            "totalLike": stat.totalLike,
            "totalCoin": stat.totalCoin,
            "totalFavorite": stat.totalFavorite,
            "totalNew": stat.totalNew,
        },
        "entries": formatted_entries,
    }


@app.route("/api/ranking-preview", methods=["GET"])
@limiter.limit("30 per minute")
def get_ranking_preview():
    """API: Get ranking preview data"""
    try:
        rank_name = request.args.get("rank", "domestic")
        index = int(request.args.get("index", 0))
        contain_unexamined = request.args.get("contain_unexamined", "false").lower() == "true"
        auth_key = get_auth_key_from_request()

        result = asyncio.run(
            capnp.run(
                get_ranking_preview_async(rank_name, index, contain_unexamined, auth_key)
            )
        )

        return jsonify({"success": True, "data": result})
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
