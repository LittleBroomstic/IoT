import paho.mqtt.client as mqtt
import csv
import os
import time
from datetime import datetime

# ==========================================
# MQTT CONFIG
# ==========================================

BROKER = "192.168.220.1"
PORT = 1883

TOPICS = [
    "esp32/temp",
    "esp32/humid",
    "esp32/light"
]

# ==========================================
# ENCRYPTION
# ==========================================

KEY = 2137
KEYLIMITER = 69
SHIFT = KEY % KEYLIMITER

# ==========================================
# VALUE RANGES
# ==========================================

TEMP_MIN = 20
TEMP_MAX = 30

HUMID_MIN = 45
HUMID_MAX = 65

LIGHT_MIN = 7

# ==========================================
# GLOBAL STORAGE
# ==========================================

message_queue = []

node_states = {
    "esp32/temp": {},
    "esp32/humid": {},
    "esp32/light": {}
}

# ==========================================
# WARNING FUNCTIONS
# ==========================================

def nan_warning(node_id, topic, count):
    print(f"WARNING: Node {node_id} of {topic} failed a read for {count} delivered NaNs")


def disconnect_warning(node_id, topic, cycles):
    print(f"WARNING: Node {node_id} of {topic} disconnected for {cycles} minutes")


def value_warning(node_id, topic, value):
    print(f"WARNING: Node {node_id} of topic {topic} produces wrong value {value}")

# ==========================================
# DECRYPTION
# ==========================================

def decrypt_payload(payload):

    decrypted = ""

    for char in payload:
        decrypted += chr(ord(char) - SHIFT)

    return decrypted

# ==========================================
# CSV
# ==========================================

def get_csv_filename(topic):

    topic_name = topic.split("/")[-1]
    return f"{topic_name}.csv"


def save_to_csv(topic, node_id, value):

    filename = get_csv_filename(topic)

    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='') as file:

        writer = csv.writer(file, delimiter=';')

        if not file_exists:
            writer.writerow(["node_id", "timestamp", "payload"])

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([node_id, timestamp, value])

# ==========================================
# MQTT CALLBACKS
# ==========================================

def on_connect(client, userdata, flags, rc):

    print("Connected with result code", rc)

    for topic in TOPICS:
        client.subscribe(topic)
        print(f"Subscribed to {topic}")


def on_message(client, userdata, msg):

    global message_queue

    try:

        topic = msg.topic

        raw_message = msg.payload.decode()

        node_id, encrypted_payload = raw_message.split(';', 1)

        decrypted_payload = decrypt_payload(encrypted_payload)

        message_queue.append({
            "topic": topic,
            "node_id": int(node_id),
            "payload": decrypted_payload
        })

    except Exception as e:

        print("Message processing error:", e)

# ==========================================
# VALUE VALIDATION
# ==========================================

def validate_value(topic, value):

    try:

        val = float(value)

        if topic == "esp32/temp":
            return TEMP_MIN <= val <= TEMP_MAX

        elif topic == "esp32/humid":
            return HUMID_MIN <= val <= HUMID_MAX

        elif topic == "esp32/light":
            return val >= LIGHT_MIN

    except:
        return False

    return True

# ==========================================
# BATCH PROCESSING
# ==========================================

def process_queue():

    global message_queue
    global node_states

    # Copy queue
    current_batch = message_queue.copy()

    # Clear original
    message_queue.clear()

    # Track nodes seen this cycle
    seen_nodes = set()

    # ======================================
    # PROCESS ALL MESSAGES
    # ======================================

    for message in current_batch:

        topic = message["topic"]
        node_id = message["node_id"]
        payload = message["payload"]

        seen_nodes.add((topic, node_id))

        # Initialize node
        if node_id not in node_states[topic]:

            node_states[topic][node_id] = {
                "timeout": 0,
                "nan": 0,
                "last_value": None
            }

        node = node_states[topic][node_id]

        # Reset timeout
        node["timeout"] = 0

        # Save latest value
        node["last_value"] = payload

        # Save CSV
        save_to_csv(topic, node_id, payload)

        print(f"[{topic}] Node {node_id}: {payload}")

        # ==================================
        # NaN CHECK
        # ==================================

        if payload.lower() == "nan":

            node["nan"] += 1

            if node["nan"] >= 5:
                nan_warning(node_id, topic, node["nan"])

            continue

        else:
            node["nan"] = 0

        # ==================================
        # RANGE CHECK
        # ==================================

        if not validate_value(topic, payload):

            value_warning(node_id, topic, payload)

    # ======================================
    # TIMEOUT CHECK
    # ======================================

    for topic in node_states:

        for node_id in node_states[topic]:

            if (topic, node_id) not in seen_nodes:

                node_states[topic][node_id]["timeout"] += 1

                timeout = node_states[topic][node_id]["timeout"]

                if timeout >= 5:

                    disconnect_warning(node_id, topic, timeout)

# ==========================================
# MAIN
# ==========================================

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

client.loop_start()

print("MQTT monitoring started")

# ==========================================
# MAIN LOOP
# ==========================================

while True:

    time.sleep(60)

    print("\nProcessing queued messages...\n")

    process_queue()
