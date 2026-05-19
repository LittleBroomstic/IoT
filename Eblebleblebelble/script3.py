import paho.mqtt.client as mqtt
import csv
import os
import time
import queue
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
BROKER = "192.168.220.1"
PORT = 1883
TOPICS = ["esp32/temp", "esp32/humid", "esp32/light"]

KEY, KEYLIMITER = 2137, 69
SHIFT = KEY % KEYLIMITER

THRESHOLDS = {
    "esp32/temp": {"min": 20, "max": 30},
    "esp32/humid": {"min": 45, "max": 65},
    "esp32/light": {"min": 7, "max": float('inf')}
}

# ==========================================
# WARNING AND LOGGING FUNCTIONS
# ==========================================

def log_system(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO: {message}")

def warn_nan(node_id, topic, count):
    print(f"WARNING: Node {node_id} on {topic} failed read. Consecutive NaNs: {count}")

def warn_timeout(node_id, topic, minutes):
    print(f"WARNING: Node {node_id} on {topic} disconnected. Silent for {minutes} minutes")

def warn_out_of_range(node_id, topic, value):
    print(f"WARNING: Node {node_id} on {topic} reported value out of range: {value}")

def error_malformed(topic, raw_data, error_msg):
    print(f"ERROR: Malformed message on {topic}. Data: '{raw_data}'. Info: {error_msg}")

def error_mqtt_connection(rc):
    print(f"ERROR: MQTT connection failed with result code: {rc}")


# ==========================================
# CORE LOGIC
# ==========================================
message_queue = queue.Queue()
node_states = {topic: {} for topic in TOPICS}

def decrypt_payload(payload):

    decrypted = ""

    for char in payload:
        decrypted += chr(ord(char) - SHIFT)

    return decrypted

def validate_value(topic, value):
    try:
        val = float(value)
        limits = THRESHOLDS.get(topic, {})
        return limits.get("min", -float('inf')) <= val <= limits.get("max", float('inf'))
    except ValueError:
        return False

def save_to_csv(topic, node_id, value):
    filename = f"{topic.split('/')[-1]}.csv"
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        if not file_exists:
            writer.writerow(["node_id", "timestamp", "payload"])
        writer.writerow([node_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), value])

# ==========================================
# MQTT CALLBACKS
# ==========================================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log_system("Connected to MQTT broker successfully")
        for topic in TOPICS:
            client.subscribe(topic)
    else:
        error_mqtt_connection(rc)

def on_message(client, userdata, msg):
    try:
        raw_message = msg.payload.decode('latin-1')
        message_queue.put({"topic": msg.topic, "raw": raw_message})
    except Exception as e:
        error_malformed(msg.topic, "Unknown", str(e))

# ==========================================
# PROCESSING
# ==========================================
def process_queue():
    seen_nodes = set()

    while not message_queue.empty():
        msg_data = message_queue.get()
        topic = msg_data["topic"]
        print(msg_data["raw"])
        try:
            if ';' not in msg_data["raw"]:
                raise ValueError("Delimiter ';' not found")
            
            node_id_str, encrypted_payload = msg_data["raw"].split(';', 1)
            node_id = int(node_id_str)
            payload = decrypt_payload(encrypted_payload)
        except (ValueError, IndexError) as e:
            error_malformed(topic, msg_data["raw"], str(e))
            continue

        seen_nodes.add((topic, node_id))

        if node_id not in node_states[topic]:
            node_states[topic][node_id] = {"timeout": 0, "nan": 0}
			
        node = node_states[topic][node_id]
        node["timeout"] = 0 
		
        if payload.lower() == "nan":
            node["nan"] += 1
            # 1. Informujemy o każdym wystąpieniu NaN
            print(f"ERROR: Received 'NaN' value from Node {node_id} on topic '{topic}' (Occurrence {node["nan"]})")
            
            # 2. Jeśli to dokładnie 5. wystąpienie z rzędu, odpalamy procedurę bezpieczeństwa
            if node["nan"] == 5:
                warn_nan(node_id, topic, node["nan"])
                
            # 3. Jeśli jest ich więcej niż 5, nadal ostrzegamy
            elif node["nan"] > 5:
                warn_nan(node_id, topic, node["nan"])
        else:
            node["nan"] = 0
            if not validate_value(topic, payload):
                warn_out_of_range(node_id, topic, payload)

        save_to_csv(topic, node_id, payload)

    for topic, nodes in node_states.items():
        for node_id, state in nodes.items():
            if (topic, node_id) not in seen_nodes:
                state["timeout"] += 1
                if state["timeout"] >= 5:
                    warn_timeout(node_id, topic, state["timeout"])

# ==========================================
# MAIN EXECUTION
# ==========================================
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    log_system("MQTT monitoring service started")

    while True:
        time.sleep(10) 
        if not message_queue.empty():
            process_queue()

except KeyboardInterrupt:
    log_system("User interrupted. Shutting down service")
    client.loop_stop()
    client.disconnect()
