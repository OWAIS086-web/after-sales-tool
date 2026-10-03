from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional
from ai.utils.whatsapp_data import whatsapp_json_to_conversation_blocks
from dataclasses import asdict



def _parse_created_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    # Handles trailing "Z"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _clean_text(t: Optional[str]) -> Optional[str]:
    if t is None:
        return None
    t = t.replace("\r\n", "\n").strip()
    return t if t else None


def _min_ticket_detailed(d: Any) -> Optional[dict]:
    if not isinstance(d, dict):
        return None
    # keep only a few fields that help you understand why the event happened
    return {
        "type": d.get("type"),
        "agentName": d.get("agentName"),
        "flowName": d.get("flowName"),
        "triggerSource": d.get("triggerSource"),
    }


def _min_event(e: Dict[str, Any]) -> Dict[str, Any]:
    event_type = e.get("eventType")  # "message" or "ticket"

    if event_type == "message":
        owner = bool(e.get("owner"))
        return {
            "kind": "message",
            "id": e.get("id"),
            "created": e.get("created"),
            "timestamp": _to_int(e.get("timestamp")),
            "sender": "agent" if owner else "contact",
            "operatorName": e.get("operatorName"),
            "status": e.get("statusString"),
            "messageType": e.get("type"),
            "text": _clean_text(e.get("text")),
            "ticketId": e.get("ticketId"),
        }

    # default: treat everything else as ticket/system event
    return {
        "kind": "ticket",
        "id": e.get("id"),
        "created": e.get("created"),
        "type": e.get("type"),
        "eventDescription": e.get("eventDescription"),
        "actor": e.get("actor"),
        "assignee": e.get("assignee"),
        "ticketId": e.get("ticketId"),
        "topicName": e.get("topicName"),
        "detailed": _min_ticket_detailed(e.get("detailedEventDescription")),
    }


def build_conversation_blocks(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for e in items:
        cid = e.get("conversationId")
        if not cid:
            continue
        grouped[cid].append(e)

    blocks: List[Dict[str, Any]] = []

    for cid, events in grouped.items():
        # sort by created time if possible, otherwise by timestamp, otherwise keep input order
        def sort_key(ev: Dict[str, Any]):
            dc = _parse_created_iso(ev.get("created"))
            ts = _to_int(ev.get("timestamp"))
            # datetime first, then timestamp
            return (
                dc or datetime.min.replace(tzinfo=timezone.utc),
                ts if ts is not None else -1,
            )

        events_sorted = sorted(events, key=sort_key)
        min_events = [_min_event(e) for e in events_sorted]

        # ticketIds + topicName + start/end
        ticket_ids = []
        topic_name = None
        created_list = [e.get("created") for e in events_sorted if e.get("created")]
        start = created_list[0] if created_list else None
        end = created_list[-1] if created_list else None

        for e in events_sorted:
            tid = e.get("ticketId")
            if tid and tid not in ticket_ids:
                ticket_ids.append(tid)
            if not topic_name and e.get("topicName"):
                topic_name = e.get("topicName")

        blocks.append(
            {
                "conversationId": cid,
                "ticketIds": ticket_ids,
                "topicName": topic_name,
                "start": start,
                "end": end,
                "events": min_events,
            }
        )

    # optional: sort conversations by start time
    def block_sort_key(b: Dict[str, Any]):
        dt = _parse_created_iso(b.get("start"))
        return dt or datetime.min.replace(tzinfo=timezone.utc)

    return sorted(blocks, key=block_sort_key)


if __name__ == "__main__":
    # Usage:
    #   python build_blocks.py input.json output_blocks.json
    import sys

    if len(sys.argv) < 3:
        print("Usage: python build_blocks.py input.json output_blocks.json")
        raise SystemExit(2)

    in_path, out_path = sys.argv[1], sys.argv[2]
    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected the input JSON to be a top-level list of events.")

    blocks = whatsapp_json_to_conversation_blocks(data)

    
    def _json_default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)  # fallback (optional)

    with open(out_path, "w", encoding="utf-8") as f:
            json.dump([asdict(b) for b in blocks], f, ensure_ascii=False, indent=2, default=_json_default)

    print(f"Wrote {len(blocks)} conversation blocks to: {out_path}")
