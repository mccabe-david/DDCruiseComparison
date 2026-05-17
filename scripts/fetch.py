#!/usr/bin/env python3
"""Fetch Disney Cruise Line stateroom availability for a set of voyages.

For each voyage it pulls the per-stateroom list (room numbers, deck, price),
then keeps only rooms that are available on every voyage. Writes docs/data.json
consumed by the GitHub Pages site.

Runs with no logged-in session: an anonymous client token is fetched first.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

VOYAGES = ["DD1566", "DD1567", "DD1568"]
BASE = "https://disneycruise.disney.go.com"
TOKEN_URL = f"{BASE}/authentication/get-client-token/"
ROOMS_URL = f"{BASE}/dcl-apps-sailingavailability-vas/stateroom-availability/voyages/{{}}/staterooms"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36"

REQUEST_BODY = json.dumps({
    "region": "en-us",
    "currency": "USD",
    "partyMix": [{
        "isDefault": True, "accessible": False,
        "adultCount": 2, "childCount": 0,
        "nonAdultAges": [], "partyMixId": "0", "number": 1,
        "stateroomInfo": {}, "enableShowADAError": False,
    }],
    "affiliations": [],
    "swid": "",
    "cartId": "",
}).encode()


def get_token():
    req = urllib.request.Request(TOKEN_URL, headers={"accept": "application/json", "user-agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def fetch_rooms(voyage, token):
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"BEARER {token}",
        "content-type": "application/json",
        "origin": BASE,
        "referer": f"{BASE}/select-stateroom/{voyage}",
        "user-agent": UA,
        "x-use-voyage-svc": "true",
        "x-dash-phase-one": "true",
    }
    req = urllib.request.Request(ROOMS_URL.format(voyage), data=REQUEST_BODY, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.load(r)
    session = (raw.get("sessions") or [None])[0]
    if not session:
        raise RuntimeError("no session data")
    pkg = session.get("voyagePackage", {})
    meta = {
        "voyageId": voyage,
        "packageCode": pkg.get("packageCode"),
        "startDate": pkg.get("vacStartDate"),
        "endDate": pkg.get("vacEndDate"),
    }
    rooms = {}
    for tv in session.get("stateroomTypes", {}).values():
        for sv in tv.get("stateroomSubtypes", {}).values():
            for loc in sv.get("locations", {}).values():
                for deck in loc.get("decks", {}).values():
                    for room in deck.get("staterooms", []):
                        rid = room.get("stateroomId")
                        if not rid:
                            continue
                        rooms[rid] = {
                            "stateroomId": rid,
                            "deck": room.get("stateroomDeck"),
                            "type": room.get("stateroomType"),
                            "subtype": room.get("stateroomSubtype"),
                            "category": room.get("stateroomCategory"),
                            "location": room.get("stateroomLocation"),
                            "price": (room.get("price", {}).get("summary", {}) or {}).get("total"),
                        }
    return meta, rooms


def main():
    token = get_token()
    metas = []
    per_voyage = {}
    for v in VOYAGES:
        meta, rooms = fetch_rooms(v, token)
        metas.append(meta)
        per_voyage[v] = rooms

    # rooms available on every voyage
    common_ids = set.intersection(*(set(r.keys()) for r in per_voyage.values()))
    rooms = []
    for rid in common_ids:
        ref = per_voyage[VOYAGES[0]][rid]
        prices = {v: per_voyage[v][rid]["price"] for v in VOYAGES}
        total = sum(p for p in prices.values() if p is not None) if all(
            prices[v] is not None for v in VOYAGES) else None
        rooms.append({
            "stateroomId": rid,
            "deck": ref["deck"],
            "type": ref["type"],
            "subtype": ref["subtype"],
            "category": ref["category"],
            "location": ref["location"],
            "prices": prices,
            "total": total,
        })
    rooms.sort(key=lambda r: ((r["deck"] or 0), r["type"] or "", r["stateroomId"]))

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "voyageOrder": VOYAGES,
        "voyages": metas,
        "rooms": rooms,
    }
    with open("docs/data.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"voyages: {VOYAGES}")
    for v, r in per_voyage.items():
        print(f"  {v}: {len(r)} rooms")
    print(f"common to all 3: {len(rooms)} rooms")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
