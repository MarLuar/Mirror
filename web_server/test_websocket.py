import websocket
import threading
import time

def on_message(ws, message):
    print(f"Received: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### Connection closed ###")

def on_open(ws):
    print("### Connection opened ###")
    # Send a test message
    ws.send("Hello Server!")

if __name__ == "__main__":
    # Enable tracing for debugging
    websocket.enableTrace(True)
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp("ws://192.168.50.130:8000/audio_ws",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    # Run the WebSocket in a separate thread
    ws.run_forever()