#!/usr/bin/env python3
"""
Test StreamPulse deployed service with real stream data
Tests the stream ingestion and webhook endpoints
"""
import httpx
import json

# Deployed service URL
STREAMPULSE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing StreamPulse Health...")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{STREAMPULSE_URL}/health")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Health Check: {result.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Health Check Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Health Check Error: {e}")
        return False

def test_stream_status():
    """Test stream status endpoint"""
    print("\nTesting Stream Status...")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{STREAMPULSE_URL}/api/v1/streams/status")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Stream Status: {result}")
                return True
            else:
                print(f"❌ Stream Status Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Stream Status Error: {e}")
        return False

def test_webhook_endpoint():
    """Test webhook endpoint with mock stream data"""
    print("\nTesting Webhook Endpoint...")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            # Mock stream data (simulating a Twitch or YouTube stream event)
            webhook_data = {
                "event": "stream.online",
                "platform": "twitch",
                "stream_id": "test_stream_123",
                "streamer": "test_user",
                "title": "Test Stream",
                "game": "Test Game",
                "viewer_count": 100
            }
            
            response = client.post(f"{STREAMPULSE_URL}/api/v1/webhooks/stream", json=webhook_data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Webhook Success: {result}")
                return True
            else:
                print(f"❌ Webhook Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("StreamPulse Testing Against Deployed Service")
    print("=" * 60)
    
    results = {
        "Health Check": test_health(),
        "Stream Status": test_stream_status(),
        "Webhook Endpoint": test_webhook_endpoint()
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print("=" * 60)