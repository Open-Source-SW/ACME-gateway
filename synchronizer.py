from flask import Flask, request, jsonify
import requests
import random
import string


app = Flask(__name__)

BASE_URL = "http://127.0.0.1:8081"
EXECUTION_STATE_CONTAINER = "/cse-mn/NoiseCancellationSystem/DeviceStatus"

# X-M2M-RI value
def generate_random_string(length=10):
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choices(characters, k=length))

def update_device_state(state):
    payload = {
        "m2m:cin": {
            "con": state
        }
    }
    url = f"{BASE_URL}{EXECUTION_STATE_CONTAINER}"
    HEADERS = {
        "Content-Type": "application/json;ty=4",
        "X-M2M-Origin": "CAdmin",
        "X-M2M-RVI": "3",
        "X-M2M-RI": generate_random_string()
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code == 201:
        print(f"DeviceStatus updated to {state}")
    else:
        print(f"Failed to update DeviceStatus: {response.status_code} - {response.text}")


@app.route('/sync', methods=['POST'])
def sync():
    data = request.json
    try:
        is_start = data["m2m:sgn"]["nev"]["rep"]["m2m:cin"]["con"]
        print(f"Received new state: {is_start}")
        state = "start" if is_start == "ON" else "stop"
        update_device_state(state)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error processing callback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(port=3001)
