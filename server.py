#!/usr/bin/env python3
"""
CVSE Web Server - Enhanced Version
Supports recording, preview, API debugging, offline changes
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

current_script_path = os.path.abspath(__file__)
sys.path.append(
    os.path.join(os.path.dirname(current_script_path), "CVSE-GatheringTools")
)
sys.path.append(
    os.path.join(os.path.dirname(current_script_path), "CVSE-GatheringTools/CVSE-API")
)

import capnp
import CVSE_capnp
from api_client import (
    CVSE_Client,
    RPCTime,
    Rank,
    capnp_to_Rank,
    ModifyEntry_to_capnp,
    Index_to_capnp,
)

CVSE_HOST = "47.104.152.246"
CVSE_PORT = "8663"
DEFAULT_PREVIEW_LIMIT = 30


def format_video_entry(entry):
    """Format video data for frontend"""
    ranks = list(map(capnp_to_Rank, entry.ranks))
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
        "ranks": [rank.value for rank in ranks],
        "is_examined": entry.isExamined,
        "is_republish": entry.isRepublish,
        "staff_info": entry.staffInfo,
    }


def format_rpc_time(rpc_time):
    """Format RPC time value for frontend display"""
    return datetime.fromtimestamp(
        rpc_time.seconds + rpc_time.nanoseconds / 1_000_000_000
    ).strftime("%Y-%m-%d %H:%M:%S")


def normalize_enum_value(value):
    """Normalize capnp enum values to frontend-friendly strings"""
    text = str(value)
    if "." in text:
        text = text.split(".")[-1]
    return text


def format_ranking_preview_entry(entry, meta_lookup):
    """Merge ranking info with meta info for preview page"""
    meta = meta_lookup.get(entry.bvid, {})
    special_rank = normalize_enum_value(entry.specialRank)
    rank_position = normalize_enum_value(entry.rankPosition)

    if special_rank == "normal" and entry.rank > 0:
        rank_label = f"#{entry.rank}"
    elif special_rank == "sh":
        rank_label = "SH"
    elif special_rank == "hot":
        rank_label = "HOT"
    else:
        rank_label = "待定"

    return {
        "avid": entry.avid,
        "bvid": entry.bvid,
        "title": meta.get("title", entry.bvid),
        "uploader": meta.get("uploader", ""),
        "cover": meta.get("cover", ""),
        "pubdate": meta.get("pubdate", ""),
        "duration": meta.get("duration", 0),
        "is_examined": meta.get("is_examined", False),
        "ranks": meta.get("ranks", []),
        "is_republish": meta.get("is_republish", False),
        "staff_info": meta.get("staff_info", ""),
        "rank": entry.rank,
        "rank_label": rank_label,
        "special_rank": special_rank,
        "rank_position": rank_position,
        "is_new": entry.isNew,
        "view_delta": entry.view,
        "like_delta": entry.like,
        "coin_delta": entry.coin,
        "favorite_delta": entry.favorite,
        "share_delta": entry.share,
        "reply_delta": entry.reply,
        "danmaku_delta": entry.danmaku,
        "score_a": round(entry.scoreA, 3),
        "score_b": round(entry.scoreB, 3),
        "score_c": round(entry.scoreC, 3),
        "total_score": round(entry.totalScore, 3),
        "on_main_count_in_ten_weeks": entry.onMainCountInTenWeeks,
    }


async def get_videos_async(keyword, rank_filter, examined, bvid, avid, page, page_size, date_str=None):
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


async def get_video_async(bvid):
    """Get single video by bvid"""
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)

    indices = [Index_to_capnp({"avid": "", "bvid": bvid})]
    videos = await client.lookupMetaInfo(indices)

    if not videos:
        return None

    return format_video_entry(videos[0])


async def submit_changes_async(changes):
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
            
        entry = {
            "avid": change.get("avid", ""),
            "bvid": change.get("bvid", ""),
            "ranks": ranks,
            "is_republish": change.get("is_republish")
            if "is_republish" in change
            else None,
            "staff": change.get("staff_info"),
            "is_examined": change.get("is_examined")
            if "is_examined" in change
            else None,
        }
        modify_entries.append(ModifyEntry_to_capnp(entry))

    await client.updateModifyEntry(modify_entries)
    return len(changes)


async def get_ranking_preview_async(
    rank_name, index, contain_unexamined, lock=False, refresh=True, limit=DEFAULT_PREVIEW_LIMIT
):
    """Fetch ranking preview data and refresh it when auth is available"""
    rank = Rank[rank_name.upper()]
    client = await CVSE_Client.create(CVSE_HOST, CVSE_PORT)

    refreshed = False
    if refresh and client.auth_key is not None:
        await client.reCalculateRankings(rank, index, contain_unexamined, lock)
        refreshed = True

    stat = await client.lookupRankingMetaInfo(rank, index, contain_unexamined)
    count = int(getattr(stat, "count", 0) or 0)
    preview_limit = max(1, min(int(limit or DEFAULT_PREVIEW_LIMIT), DEFAULT_PREVIEW_LIMIT))

    if count == 0:
        return {
            "entries": [],
            "meta": {
                "count": 0,
                "total_view": 0,
                "total_like": 0,
                "total_coin": 0,
                "total_favorite": 0,
                "total_share": 0,
                "total_reply": 0,
                "total_danmaku": 0,
                "total_new": 0,
                "start_time": None,
                "end_time": None,
                "auth_configured": client.auth_key is not None,
                "refreshed": refreshed,
                "limit": preview_limit,
            },
        }

    indices = list(
        await client.getAllRankingInfo(
            rank,
            index,
            contain_unexamined,
            from_rank=1,
            to_rank=min(count, preview_limit) + 1,
        )
    )
    ranking_entries = list(
        await client.lookupRankingInfo(rank, index, contain_unexamined, indices)
    )
    meta_entries = list(await client.lookupMetaInfo(indices))
    meta_lookup = {entry.bvid: format_video_entry(entry) for entry in meta_entries}

    return {
        "entries": [
            format_ranking_preview_entry(entry, meta_lookup)
            for entry in ranking_entries
        ],
        "meta": {
            "count": count,
            "total_view": int(stat.totalView),
            "total_like": int(stat.totalLike),
            "total_coin": int(stat.totalCoin),
            "total_favorite": int(stat.totalFavorite),
            "total_share": int(stat.totalShare),
            "total_reply": int(stat.totalReply),
            "total_danmaku": int(stat.totalDanmaku),
            "total_new": int(stat.totalNew),
            "start_time": format_rpc_time(stat.startTime),
            "end_time": format_rpc_time(stat.endTime),
            "auth_configured": client.auth_key is not None,
            "refreshed": refreshed,
            "limit": preview_limit,
        },
    }


@app.route("/")
def index():
    """Return frontend page"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.route("/api/health")
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
def submit_changes():
    """API: Submit batch changes to CVSE server"""
    try:
        data = request.get_json(silent=True) or {}
        changes = data.get("changes", [])

        if not changes:
            return jsonify({"success": False, "error": "No changes to submit"})

        count = asyncio.run(capnp.run(submit_changes_async(changes)))

        return jsonify({"success": True, "message": f"Submitted {count} changes"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calculate-rankings", methods=["POST"])
def calculate_rankings():
    """API: Refresh rankings when possible and return preview data"""
    try:
        data = request.get_json(silent=True) or {}
        rank_name = data.get("rank", "domestic")
        index = int(data.get("index", 0))
        contain_unexamined = data.get("contain_unexamined", False)
        lock = data.get("lock", False)
        refresh = data.get("refresh", True)
        limit = int(data.get("limit", DEFAULT_PREVIEW_LIMIT))

        preview_data = asyncio.run(
            capnp.run(
                get_ranking_preview_async(
                    rank_name,
                    index,
                    contain_unexamined,
                    lock=lock,
                    refresh=refresh,
                    limit=limit,
                )
            )
        )

        refreshed = preview_data["meta"]["refreshed"]
        auth_configured = preview_data["meta"]["auth_configured"]
        if refreshed:
            message = f"Rankings refreshed for {rank_name}"
        elif auth_configured:
            message = f"Preview loaded for {rank_name}"
        else:
            message = f"Preview loaded for {rank_name} (auth_key not configured, using cached rankings)"

        return jsonify(
            {
                "success": True,
                "message": message,
                "meta": preview_data["meta"],
                "data": preview_data["entries"],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/debug", methods=["GET", "POST"])
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


if __name__ == "__main__":
    print("Starting CVSE server (Enhanced Version)...")
    print("Visit: http://localhost:5123")
    app.run(host="::", port=5123, debug=True)
    # app.run(host="0.0.0.0", port=5123, debug=True)
