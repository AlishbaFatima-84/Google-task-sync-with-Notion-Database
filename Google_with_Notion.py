import os
import time
import json
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# Configuration of Google API
SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']
TOKEN_FILE = 'token.json'
GOOGLE_CREDENTIALS_FILE = 'credentials.json'

# Configuration of Notion API
NOTION_API_KEY = "ntn_L16905775029c4xoR00eOBCL1Pe37R4tCfgXTH7C2CA7yM"
NOTION_DATABASE_ID = "1a1064c42a5e805da3bce58613d8178c"
NOTION_API_URL = "https://api.notion.com/v1/pages"

# Keep track of Google Task IDs and Notion page IDs bt mapping files
Mapping_task_file = "task_mapping.json"
Mapping_tasklist_file = "tasklist_mapping.json"

# Authentication of Google task
def google_task_authentication():
    credential = None
    if os.path.exists(TOKEN_FILE):
        credential= Credentials.from_authorized_user_file(TOKEN_FILE,SCOPES)
    if not credential or not credential.valid:
        if credential and credential.expired and credential.refresh_token:
            credential.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
            credential = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(credential.to_json())
    return build('tasks', 'v1', credentials=credential)    

#----------------  TASK LIST FUNCTIONS -------------------

# retrieve google task lists
def retrieve_task_lists(service):
    result = service.tasklists().list().execute()
    return result.get('items',[])

# Loading google 'Mapping_tasklist_file' 
def load_task_list_mapping():
    if os.path.exists(Mapping_tasklist_file):
        with open(Mapping_tasklist_file, "r") as file:
            return json.load(file)
    return {}

# Saving google 'Mapping_tasklist_file'
def save_task_list_mapping(mapping):
    with open(Mapping_tasklist_file, "w") as file:
        json.dump(mapping, file)


#------------------ TASK FUNCTIONS ---------------------

# retrieve google task 
def retrieve_tasks(service, tasklist_id):
    response = service.tasks().list(tasklist=tasklist_id).execute()
    return response.get('items', [])

# Loading google 'Mapping_task_file' 
def load_task_mapping():
    if os.path.exists(Mapping_task_file):
        with open(Mapping_task_file, "r") as file:
            return json.load(file)
    return {}

# Saving google 'Mapping_task_file'
def save_task_mapping(mapping):
    with open(Mapping_task_file, "w") as file:
        json.dump(mapping, file)


#------------------ NOTION FUNCTIONS ---------------------

# Add task from google task to notion database
def add_task(task_title, task_description=None, due_date=None):
    headers = {
         "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    properties = {"Task Name": {"title": [{"text": {"content": task_title}}]}}
    if due_date:
        properties["Due Date"] = {"date": {"start": due_date}}
    if task_description:
        properties["Description"] = {"rich_text": [{"text": {"content": task_description}}]}
    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    response = requests.post(NOTION_API_URL, headers=headers, json=payload)
    response_json = response.json()
    if response.status_code == 200:
        print(f"Task Added to Notion Database: {task_title}")
        return response_json["id"]
    else:
        print(f"Failed to add task: {task_title}")
        print(json.dumps(response_json, indent=4))
        return None


# Update task from google task to notion database
def update_task(notion_page_id, task_title, task_description=None, due_date=None):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    properties = {"Task Name": {"title": [{"text": {"content": task_title}}]}}
    if due_date:
        properties["Due Date"] = {"date": {"start": due_date}}
    if task_description:
        properties["Description"] = {"rich_text": [{"text": {"content": task_description}}]}
    payload = {"properties": properties}
    response = requests.patch(f"https://api.notion.com/v1/pages/{notion_page_id}", headers=headers, json=payload)
    if response.status_code == 200:
        print(f"Updated task in Notion: {task_title}")
    else:
        print(f"Failed to update task in Notion: {task_title}")


# Delete task from google task to notion database
def delete_task(notion_page_id):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {"archived": True}
    response = requests.patch(f"https://api.notion.com/v1/pages/{notion_page_id}", headers=headers, json=payload)
    if response.status_code == 200:
        print(f"Archived task in Notion: {notion_page_id}")
    else:
        print(f"Failed to archive task in Notion: {notion_page_id}")


# Function to mointor addition, updation and deletion of google tasks 
# And perform operations in notion database 
# Also keep track of sync buttons

def monitor_changes(service, stop_event=None):
    """
    Process one iteration of syncing Google Tasks with Notion.
    Exits immediately if stop_event is set.
    """
    last_tasks = load_task_mapping()
    last_tasklists = load_task_list_mapping()
    current_tasks = {}
    current_tasklists = {}

    try:
        task_lists = retrieve_task_lists(service)
    except Exception as e:
        print(f"Error fetching task lists: {e}")
        return

    for task_list in task_lists:
        if stop_event and stop_event.is_set():
            print("Stop event detected. Exiting iteration.")
            return
        tasklist_id = task_list['id']
        current_tasklists[tasklist_id] = task_list.get('title', "Untitled List")
        try:
            tasks = retrieve_tasks(service, tasklist_id)
        except Exception as e:
            print(f"Skipping task list '{task_list.get('title', 'Unknown')}' due to error: {e}")
            continue

        for task in tasks:
            if stop_event and stop_event.is_set():
                print("Stop event detected during task processing. Exiting iteration.")
                return
            task_id = task['id']
            task_title = task.get("title", "Untitled Task")
            task_description = task.get("notes", "")
            due_date = task.get("due")
            if due_date:
                due_date = due_date.split("T")[0]
            current_tasks[task_id] = {
                "title": task_title,
                "description": task_description,
                "due_date": due_date
            }
            if task_id in last_tasks:
                notion_page_id = last_tasks[task_id]["notion_page_id"]
                if (last_tasks[task_id]["title"] != task_title or
                    last_tasks[task_id]["description"] != task_description or
                    last_tasks[task_id]["due_date"] != due_date):
                    print(f"[UPDATED TASK] {last_tasks[task_id]['title']} → {task_title}")
                    update_task(notion_page_id, task_title, task_description, due_date)
                    last_tasks[task_id] = {
                        "notion_page_id": notion_page_id,
                        "title": task_title,
                        "description": task_description,
                        "due_date": due_date
                    }
            else:
                print(f"[NEW TASK] Adding: {task_title} (Due: {due_date})")
                notion_page_id = add_task(task_title, task_description, due_date)
                if notion_page_id:
                    last_tasks[task_id] = {
                        "notion_page_id": notion_page_id,
                        "title": task_title,
                        "description": task_description,
                        "due_date": due_date
                    }

    # Detect deleted tasks
    for task_id in list(last_tasks.keys()):
        if stop_event and stop_event.is_set():
            print("Stop event detected during deletion check. Exiting iteration.")
            return
        if task_id not in current_tasks:
            print(f"[DELETED TASK] Removing: {last_tasks[task_id]['title']}")
            delete_task(last_tasks[task_id]["notion_page_id"])
            del last_tasks[task_id]

    # Handle task list deletions
    deleted_tasklists = set(last_tasklists.keys()) - set(current_tasklists.keys())
    for tasklist_id in deleted_tasklists:
        if stop_event and stop_event.is_set():
            print("Stop event detected during task list deletion check. Exiting iteration.")
            return
        if last_tasklists.get(tasklist_id, {}).get("missed_count", 0) >= 3:
            print(f"Deleting task list: {last_tasklists[tasklist_id].get('name', 'Unknown')} (ID: {tasklist_id})")
            del last_tasklists[tasklist_id]
        else:
            last_tasklists[tasklist_id] = {
                "name": last_tasklists.get(tasklist_id, {}).get("name", "Unknown List"),
                "missed_count": last_tasklists.get(tasklist_id, {}).get("missed_count", 0) + 1
            }

    save_task_mapping(last_tasks)
    save_task_list_mapping(last_tasklists)
