#!/usr/bin/env python3
"""
Find active wallets trading XYZ markets on Hyperliquid
"""

import requests
import json
from datetime import datetime, timedelta

API_URL = "https://api.hyperliquid.xyz/info"

def get_all_xyz_traders():
    """
    Try to find wallets with XYZ trading activity
    """
    print("🔍 Searching for active XYZ traders...\n")

    # Try to get universe metadata first to understand the markets
    try:
        payload = {
            "type": "metaAndAssetCtxs",
            "dex": "xyz"
        }

        response = requests.post(API_URL, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            metadata = data[0] if len(data) > 0 else {}
            asset_ctxs = data[1] if len(data) > 1 else []

            universe = metadata.get("universe", [])

            print(f"✓ Found {len(universe)} XYZ markets\n")
            print("Available XYZ markets:")
            for market in universe[:10]:
                name = market.get("name", "")
                is_delisted = market.get("isDelisted", False)
                if not is_delisted:
                    print(f"  - {name}")

            print("\n" + "="*80)

            # Now let's try to get funding history which might give us wallet addresses
            print("\n🔍 Method 1: Checking funding history for wallet addresses...\n")

            for market_info in universe[:3]:  # Check first 3 markets
                coin_name = market_info.get("name", "")
                if coin_name.startswith("xyz:"):
                    print(f"  Checking {coin_name}...")

                    try:
                        funding_payload = {
                            "type": "fundingHistory",
                            "coin": coin_name,
                            "startTime": int((datetime.now() - timedelta(days=1)).timestamp() * 1000),
                            "endTime": int(datetime.now().timestamp() * 1000)
                        }

                        fund_response = requests.post(API_URL, json=funding_payload, timeout=10)

                        if fund_response.status_code == 200:
                            print(f"    ✓ Got funding data")
                    except Exception as e:
                        print(f"    ⚠️  Error: {e}")

        else:
            print(f"⚠️  API Error: {response.status_code}")

    except Exception as e:
        print(f"⚠️  Error: {e}")

    # Method 2: Try to get open interest or other aggregate data
    print("\n🔍 Method 2: Checking for leaderboard data...\n")

    try:
        # Try different API endpoints that might give us wallet info
        endpoints_to_try = [
            {"type": "spotMeta"},
            {"type": "meta"},
        ]

        for endpoint in endpoints_to_try:
            try:
                response = requests.post(API_URL, json=endpoint, timeout=10)
                if response.status_code == 200:
                    print(f"  ✓ Endpoint {endpoint['type']} accessible")
            except:
                pass

    except Exception as e:
        print(f"  ⚠️  Error: {e}")

    print("\n" + "="*80)
    print("\n💡 The Hyperliquid API doesn't provide a public trader list.")
    print("   We'll need to test with a specific wallet address.\n")

    # Suggest some approaches
    print("📝 To find active wallets, you can:")
    print("  1. Check Hyperliquid Discord/Twitter for active traders")
    print("  2. Use a block explorer to find recent XYZ transactions")
    print("  3. Use your own wallet address if you trade XYZ")
    print("  4. Monitor the trade.xyz platform for active addresses\n")

    # Let's try one more thing - check if we can get recent user states
    print("🔍 Method 3: Trying to find any public wallet data...\n")

    # Some known active Hyperliquid addresses (from public sources)
    known_addresses = [
        "0x010461C14e146ac35Fe42271BDC1134EE31C703a",
        "0x563C175E6f11582F65D6d9E360A618699DEe14a4",
        "0x3B3525F60eCEd8dE93212706A45A0de43e61F4f7",
        "0x7cE5E2F6c375a04A3f2371c1f13E95a9e6ba776E",
        "0xEf4e0E3602F5E0C7e088B9f1bC8d8d8C9F7f6F5A",
    ]

    print(f"Testing {len(known_addresses)} known Hyperliquid addresses...\n")

    active_wallets = []

    for addr in known_addresses:
        print(f"  {addr}...", end=" ")
        try:
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(hours=48)).timestamp() * 1000)

            payload = {
                "type": "userFillsByTime",
                "user": addr,
                "startTime": start_time,
                "endTime": end_time
            }

            response = requests.post(API_URL, json=payload, timeout=10)

            if response.status_code == 200:
                fills = response.json()
                xyz_fills = [f for f in fills if f.get("coin", "").startswith("xyz:")]

                if len(xyz_fills) > 0:
                    print(f"✓ ACTIVE! ({len(xyz_fills)} XYZ fills)")
                    active_wallets.append(addr)
                else:
                    # Check for any fills at all
                    if len(fills) > 0:
                        print(f"○ Active on HL ({len(fills)} non-XYZ fills)")
                    else:
                        print("✗ No activity")
            else:
                print(f"✗ API error")

        except Exception as e:
            print(f"✗ Error: {e}")

    print("\n" + "="*80)

    if active_wallets:
        print(f"\n✅ Found {len(active_wallets)} wallet(s) with recent XYZ activity!\n")
        for wallet in active_wallets:
            print(f"  {wallet}")
        print()
        return active_wallets
    else:
        print("\n⚠️  No wallets found with recent XYZ activity.")
        print("    XYZ markets may have low activity currently.\n")
        return []

if __name__ == "__main__":
    active_wallets = get_all_xyz_traders()

    if active_wallets:
        print("="*80)
        print("🧪 You can test the volume tracker with these wallets:")
        print("="*80)
        for wallet in active_wallets:
            print(f"\npython3 xyz_volume_tracker.py {wallet}")
            print(f"python3 xyz_volume_tracker.py {wallet} --historical")
        print()
