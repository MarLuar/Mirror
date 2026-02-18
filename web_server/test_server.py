"""
Test script to verify the ESP32 receiver server is working
"""
import requests
import json

def test_server():
    """Test the ESP32 receiver server"""
    url = "http://127.0.0.1:8000/health"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("✓ Server is running and healthy")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"✗ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"✗ Error testing server: {e}")
        return False

def test_audio_endpoint():
    """Test the audio endpoint with dummy data"""
    url = "http://127.0.0.1:8000/audio"
    
    # Send empty data to test the endpoint
    try:
        response = requests.post(url, data=b'')
        print(f"Audio endpoint test - Status: {response.status_code}")
        if response.status_code == 400:
            print("✓ Audio endpoint responded correctly (expected error for empty data)")
        else:
            print(f"Response: {response.text}")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to audio endpoint. Is the server running?")
        return False
    except Exception as e:
        print(f"✗ Error testing audio endpoint: {e}")
        return False

if __name__ == "__main__":
    print("Testing ESP32 Receiver Server...")
    print("="*40)
    
    if test_server():
        test_audio_endpoint()
    
    print("="*40)
    print("Test complete.")