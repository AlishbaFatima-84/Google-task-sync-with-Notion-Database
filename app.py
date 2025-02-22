from flask import Flask, request, render_template, jsonify
import threading
import time
import Google_with_Notion

app = Flask(__name__)

sync_thread = None
stop_event = threading.Event()
service = None  # Global service variable

def start_sync():
    global stop_event, sync_thread, service
    stop_event.clear()
    service = Google_with_Notion.google_task_authentication()
    print("Sync started...")
    while not stop_event.is_set():
        # If service is None, break out immediately.
        if service is None:
            print("Service is None. Exiting sync loop.")
            break
        Google_with_Notion.monitor_changes(service, stop_event=stop_event)
        if stop_event.is_set():
            break
        time.sleep(10)
    print("Sync loop terminated.")
    sync_thread = None

@app.route('/start_sync', methods=['POST'])
def start_sync_api():
    global sync_thread
    if sync_thread and sync_thread.is_alive():
        return jsonify({"message": "Sync is already running!"}), 400
    sync_thread = threading.Thread(target=start_sync, daemon=True)
    sync_thread.start()
    return jsonify({"message": "Sync started successfully!"})

@app.route('/stop_sync', methods=['POST'])
def stop_sync_api():
    global stop_event, service
    if not sync_thread or not sync_thread.is_alive():
        return jsonify({"message": "No sync process running!"}), 400
    stop_event.set()       # Signal the loop to stop
    service = None         # Remove the authenticated service so no further processing happens
    return jsonify({"message": "Sync process stopping..."})

@app.route('/')
def home():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)
