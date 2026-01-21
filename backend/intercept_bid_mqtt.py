"""
Intercept the exact MQTT message sent when placing a bid
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from playwright.async_api import async_playwright

# Get session
import sqlite3
conn = sqlite3.connect('auction_data.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT us.encrypted_browser_state, us.encryption_iv
    FROM user_sessions us
    JOIN auction_house_credentials ahc ON us.credential_id = ahc.id
    WHERE ahc.auction_house = 'goldin' AND us.is_active = 1
    ORDER BY us.id DESC LIMIT 1
""")
row = cursor.fetchone()
conn.close()

from app.services.encryption import get_encryption_service
encryption = get_encryption_service()
session_json = encryption.decrypt(row[0], row[1])
session_data = json.loads(session_json)

def decode_mqtt_frame(data):
    """Decode MQTT frame to understand the message type"""
    if isinstance(data, str):
        return {"type": "text", "data": data}

    if len(data) < 1:
        return {"type": "empty"}

    packet_type = (data[0] >> 4) & 0x0F

    types = {
        1: "CONNECT",
        2: "CONNACK",
        3: "PUBLISH",
        4: "PUBACK",
        5: "PUBREC",
        6: "PUBREL",
        7: "PUBCOMP",
        8: "SUBSCRIBE",
        9: "SUBACK",
        10: "UNSUBSCRIBE",
        11: "UNSUBACK",
        12: "PINGREQ",
        13: "PINGRESP",
        14: "DISCONNECT"
    }

    mqtt_type = types.get(packet_type, f"UNKNOWN({packet_type})")

    result = {"type": mqtt_type, "raw": data.hex()[:200]}

    # For PUBLISH messages, try to extract topic and payload
    if packet_type == 3:
        try:
            # Skip first 2 bytes (type + remaining length)
            idx = 1
            # Variable length encoding for remaining length
            remaining = 0
            multiplier = 1
            while idx < len(data):
                byte = data[idx]
                remaining += (byte & 0x7F) * multiplier
                multiplier *= 128
                idx += 1
                if (byte & 0x80) == 0:
                    break

            # Topic length (2 bytes)
            topic_len = (data[idx] << 8) | data[idx + 1]
            idx += 2

            # Topic
            topic = data[idx:idx + topic_len].decode('utf-8', errors='replace')
            idx += topic_len

            # Payload (rest of the message)
            payload = data[idx:]

            result["topic"] = topic
            result["payload_raw"] = payload.hex()

            # Try to decode as JSON
            try:
                result["payload"] = json.loads(payload.decode('utf-8'))
            except:
                try:
                    result["payload_text"] = payload.decode('utf-8', errors='replace')
                except:
                    pass

        except Exception as e:
            result["decode_error"] = str(e)

    return result

async def intercept_mqtt_bid():
    # Get a cheap item
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_url, title, current_bid, external_id FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
        ORDER BY current_bid ASC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    item_url, title, current_bid, external_id = row
    bid_amount = int(current_bid) + 2

    print(f"Item: {title[:50]}...")
    print(f"External ID: {external_id}")
    print(f"Current bid: ${current_bid}")
    print(f"Our bid: ${bid_amount}")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080},
    )

    # Restore session
    if session_data.get("cookies"):
        await context.add_cookies(session_data["cookies"])

    page = await context.new_page()

    # Restore localStorage
    if session_data.get("localStorage"):
        await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
        for key, value in session_data["localStorage"].items():
            await page.evaluate("(args) => localStorage.setItem(args.key, args.value)", {"key": key, "value": value})

    # Track all WebSocket frames
    all_ws_frames = []
    bid_phase = False

    def handle_websocket(ws):
        print(f"\n>>> WEBSOCKET CONNECTED: {ws.url[:100]}...")

        def on_frame_sent(payload):
            decoded = decode_mqtt_frame(payload)
            all_ws_frames.append({"direction": "SENT", "decoded": decoded, "bid_phase": bid_phase})
            if bid_phase or decoded.get("type") == "PUBLISH":
                print(f"\n  SENT [{decoded.get('type')}]: {json.dumps(decoded, indent=2)[:500]}")

        def on_frame_received(payload):
            decoded = decode_mqtt_frame(payload)
            all_ws_frames.append({"direction": "RECV", "decoded": decoded, "bid_phase": bid_phase})
            # Only print PUBLISH messages during bid phase to reduce noise
            if bid_phase and decoded.get("type") == "PUBLISH":
                print(f"\n  RECV [{decoded.get('type')}]: {json.dumps(decoded, indent=2)[:500]}")

        ws.on('framesent', on_frame_sent)
        ws.on('framereceived', on_frame_received)

    page.on('websocket', handle_websocket)

    try:
        print("\n=== Navigating to item ===")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
        except:
            pass

        print("\n=== Clicking Place Bid (opening modal) ===")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        print("\n=== Entering bid amount ===")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        if not bid_input:
            bid_input = await page.query_selector('input[type="number"]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("\n=== Clicking Place Bid (submit) ===")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and text == "Place Bid":
                await btn.click()
                break
        await asyncio.sleep(2)

        print("\n\n=== NOW CONFIRMING BID - WATCH FOR MQTT PUBLISH ===")
        bid_phase = True

        # Click confirm
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and "Confirm Your Bid" in text:
                print(f"Clicking: {text}")
                await btn.click()
                break

        # Wait for response
        await asyncio.sleep(5)
        bid_phase = False

        print(f"\n\n=== SUMMARY ===")
        print(f"Total WS frames: {len(all_ws_frames)}")

        # Show all PUBLISH messages
        print("\n=== ALL PUBLISH MESSAGES (sent or received) ===")
        for frame in all_ws_frames:
            if frame['decoded'].get('type') == 'PUBLISH':
                print(f"\nDirection: {frame['direction']}")
                print(f"During bid: {frame['bid_phase']}")
                print(f"Topic: {frame['decoded'].get('topic', 'N/A')}")
                if 'payload' in frame['decoded']:
                    print(f"Payload: {json.dumps(frame['decoded']['payload'], indent=2)}")
                elif 'payload_text' in frame['decoded']:
                    print(f"Payload text: {frame['decoded']['payload_text'][:500]}")
                else:
                    print(f"Payload raw: {frame['decoded'].get('payload_raw', 'N/A')[:200]}")

        # Also show frames that were sent during bid phase
        print("\n=== ALL SENT FRAMES DURING BID PHASE ===")
        for frame in all_ws_frames:
            if frame['direction'] == 'SENT' and frame['bid_phase']:
                print(f"\nType: {frame['decoded'].get('type')}")
                if frame['decoded'].get('topic'):
                    print(f"Topic: {frame['decoded']['topic']}")
                if 'payload' in frame['decoded']:
                    print(f"Payload: {json.dumps(frame['decoded']['payload'], indent=2)}")
                elif 'payload_text' in frame['decoded']:
                    print(f"Payload text: {frame['decoded']['payload_text']}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(intercept_mqtt_bid())
