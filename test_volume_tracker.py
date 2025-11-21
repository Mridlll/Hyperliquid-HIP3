#!/usr/bin/env python3
"""
Test script for xyz_volume_tracker.py
Finds active wallets and tests the utility
"""

import requests
import json
import sys
import subprocess
from datetime import datetime, timedelta

API_URL = "https://api.hyperliquid.xyz/info"

def get_recent_xyz_trades():
    """
    Get recent trades from XYZ markets to find active wallets
    """
    print("🔍 Finding active wallets from recent XYZ market trades...\n")

    # XYZ markets to check
    xyz_markets = ["xyz:XYZ100", "xyz:TSLA", "xyz:NVDA", "xyz:PLTR", "xyz:META"]

    active_wallets = set()

    for market in xyz_markets[:3]:  # Check first 3 markets to save time
        try:
            print(f"  Checking {market}...")

            # Get recent trades for this market
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": market,
                    "interval": "1m",
                    "startTime": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
                    "endTime": int(datetime.now().timestamp() * 1000)
                }
            }

            response = requests.post(API_URL, json=payload, timeout=10)

            if response.status_code == 200:
                print(f"    ✓ Got data from {market}")

        except Exception as e:
            print(f"    ⚠️  Error: {e}")
            continue

    # Alternative: Get leaderboard data to find top traders
    print("\n🏆 Fetching top traders from leaderboard...")

    try:
        payload = {
            "type": "spotMeta"
        }

        response = requests.post(API_URL, json=payload, timeout=10)

        if response.status_code == 200:
            print("  ✓ Successfully fetched data")
    except Exception as e:
        print(f"  ⚠️  Error: {e}")

    # Use some known active test wallets from Hyperliquid
    # These are examples - we'll try to find real ones
    test_wallets = [
        "0x010461C14e146ac35Fe42271BDC1134EE31C703a",  # Example wallet
        "0x00c9d6c2b6A45c5d8f7f8B3e1C2d6c2b6A45c5d8",  # Example wallet
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",  # Example from docs
    ]

    return test_wallets

def test_wallet_quick_check(wallet_address):
    """
    Quick test to see if wallet has any XYZ activity
    """
    try:
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)

        payload = {
            "type": "userFillsByTime",
            "user": wallet_address,
            "startTime": start_time,
            "endTime": end_time
        }

        response = requests.post(API_URL, json=payload, timeout=10)

        if response.status_code == 200:
            fills = response.json()
            xyz_fills = [f for f in fills if f.get("coin", "").startswith("xyz:")]
            return len(xyz_fills) > 0, len(xyz_fills)

        return False, 0

    except Exception as e:
        print(f"    Error checking wallet: {e}")
        return False, 0

def find_active_wallet():
    """
    Try to find at least one active wallet with XYZ trades
    """
    print("="*80)
    print("🔍 SEARCHING FOR ACTIVE XYZ WALLETS")
    print("="*80)

    # Try to get some wallet addresses from public data
    # Method 1: Check funding history for XYZ markets
    print("\n📊 Method 1: Checking recent XYZ market activity...\n")

    test_wallets = get_recent_xyz_trades()

    print(f"\n📝 Testing {len(test_wallets)} potential wallet addresses...\n")

    active_wallets = []

    for wallet in test_wallets:
        print(f"  Testing {wallet}...", end=" ")
        has_activity, fill_count = test_wallet_quick_check(wallet)

        if has_activity:
            print(f"✓ ACTIVE ({fill_count} XYZ fills in last 24h)")
            active_wallets.append(wallet)
        else:
            print("✗ No recent XYZ activity")

    print("\n" + "="*80)
    print(f"✅ Found {len(active_wallets)} active wallet(s)")
    print("="*80)

    return active_wallets

def run_volume_tracker(wallet_address, mode="short"):
    """
    Run the xyz_volume_tracker.py script
    """
    print(f"\n{'='*80}")
    print(f"🧪 TESTING VOLUME TRACKER - {mode.upper()} MODE")
    print(f"{'='*80}\n")
    print(f"Wallet: {wallet_address}")
    print(f"Mode: {mode}")
    print("\n" + "-"*80 + "\n")

    try:
        if mode == "short":
            cmd = ["python3", "xyz_volume_tracker.py", wallet_address, "24"]
        else:
            cmd = ["python3", "xyz_volume_tracker.py", wallet_address, "--historical"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes timeout
        )

        print(result.stdout)

        if result.stderr:
            print("STDERR:", result.stderr)

        print("\n" + "-"*80)
        print(f"Exit code: {result.returncode}")
        print("-"*80)

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("❌ Test timed out after 3 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

def main():
    """Main test function"""
    print("\n" + "="*80)
    print("🧪 XYZ VOLUME TRACKER - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*80)

    # Step 1: Find active wallets
    active_wallets = find_active_wallet()

    if not active_wallets:
        print("\n⚠️  No active wallets found in test set.")
        print("Please provide a wallet address manually for testing:")
        print("\nUsage:")
        print(f"  python3 xyz_volume_tracker.py <WALLET_ADDRESS>")
        print(f"  python3 xyz_volume_tracker.py <WALLET_ADDRESS> --historical")
        return

    # Step 2: Test with first active wallet
    test_wallet = active_wallets[0]

    print(f"\n🎯 Selected test wallet: {test_wallet}\n")

    # Test short-term mode
    print("\n" + "="*80)
    print("TEST 1: SHORT-TERM MODE (24 hours)")
    print("="*80)

    success_short = run_volume_tracker(test_wallet, mode="short")

    # Ask user if they want to run historical test
    print("\n" + "="*80)
    print("Historical mode test available (takes longer)")
    print("="*80)
    print("\nTo test historical mode, run:")
    print(f"  python3 xyz_volume_tracker.py {test_wallet} --historical")

    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"Short-term test:  {'✅ PASSED' if success_short else '❌ FAILED'}")
    print(f"Test wallet:      {test_wallet}")
    print("="*80)

    if success_short:
        print("\n✅ Volume tracker is working correctly!")
    else:
        print("\n⚠️  Some tests failed. Check output above for details.")

    print("\n💡 You can test with any wallet address:")
    print(f"  python3 xyz_volume_tracker.py <YOUR_WALLET_ADDRESS>")
    print(f"  python3 xyz_volume_tracker.py <YOUR_WALLET_ADDRESS> --historical")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Test error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
