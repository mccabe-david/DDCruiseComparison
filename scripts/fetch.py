#!/usr/bin/env python3
"""Fetch Disney Cruise Line stateroom availability for a set of voyages.

Writes docs/data.json consumed by the GitHub Pages site.
Run with no logged-in session: an anonymous client token is fetched automatically.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

VOYAGES = ["DD1566", "DD1567", "DD1568"]
BASE = "https://disneycruise.disney.go.com"
TOKEN_URL = f"{BASE}/authentication/get-client-token/"
AVAIL_URL = f"{BASE}/dcl-apps-sailingavailability-vas/stateroom-availability/voyages/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36"

PARTY_MIX = {
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
}


def get_token():
    req = urllib.request.Request(TOKEN_URL, headers={"accept": "application/json", "user-agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def fetch_voyage(voyage, token):
    body = json.dumps(PARTY_MIX).encode()
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
    req = urllib.request.Request(AVAIL_URL + voyage, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def parse_voyage(voyage, raw):
    sessions = raw.get("sessions") or []
    if not sessions:
        return {"voyageId": voyage, "error": "no session data"}
    s = sessions[0]
    pkg = s.get("voyagePackage", {})
    types = []
    total = 0
    for tk, tv in s.get("stateroomTypes", {}).items():
        subtypes = []
        for sk, sv in tv.get("stateroomSubtypes", {}).items():
            subtypes.append({
                "name": sk,
                "category": sv.get("stateroomCategory"),
                "count": sv.get("stateroomCount", 0),
                "startingPrice": sv.get("startingPrice"),
            })
        count = tv.get("stateroomCount", 0)
        total += count
        types.append({
            "type": tk,
            "count": count,
            "startingPrice": tv.get("startingPrice"),
            "subtypes": sorted(subtypes, key=lambda x: x["category"] or ""),
        })
    types.sort(key=lambda x: x["type"])
    return {
        "voyageId": voyage,
        "packageCode": pkg.get("packageCode"),
        "startDate": pkg.get("vacStartDate"),
        "endDate": pkg.get("vacEndDate"),
        "totalAvailable": total,
        "stateroomTypes": types,
    }


def main():
    token = get_token()
    voyages = []
    for v in VOYAGES:
        try:
            voyages.append(parse_voyage(v, fetch_voyage(v, token)))
        except Exception as exc:  # noqa: BLE001
            voyages.append({"voyageId": v, "error": str(exc)})
    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "voyages": voyages,
    }
    with open("docs/data.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    if all("error" in v for v in voyages):
        sys.exit(1)


if __name__ == "__main__":
    main()
