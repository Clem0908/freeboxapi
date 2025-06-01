import base64
import datetime
import hmac
import hashlib
import requests
import time
import typing
from typing import Any
import urllib3
import json
urllib3.disable_warnings()


def request_failed(code: int, endpoint: str, response: dict[Any,Any]):

    print(f"!! HTTP request failed: {code} - {endpoint}\n!! {response.get("msg", "")}\n")
    action()

    return


def set_globals() -> None:

    ret: dict[str,str] = get_api_version()
    global HTTPS_PORT, API_DOMAIN, API_BASE_URL, API_VERSION, BASE_URL
    HTTPS_PORT = ret.get("https_port", "")
    API_DOMAIN = ret.get("api_domain", "")
    API_BASE_URL = ret.get("api_base_url", "")
    API_VERSION = ret.get("api_version", "")
    API_VERSION = float(API_VERSION)
    API_VERSION = int(API_VERSION)
    BASE_URL = "https://"+API_DOMAIN+":"+str(HTTPS_PORT)+API_BASE_URL+"v"+str(API_VERSION)

    return


def login() -> None:

    ans = requests.get(BASE_URL+"/login", verify=False)

    if ans.status_code != 200:
        request_failed(ans.status_code, BASE_URL+"/login", ans.json())

    global CHALLENGE
    CHALLENGE = ans.json().get("result", {}).get("challenge", "")
    
    with open(".challenge", "w") as f:
        f.write(CHALLENGE)

    action()
    
    return


def session_stop() -> None:

    ans = requests.post(BASE_URL+"/login/logout/", headers={ "X-Fbx-App-Auth": read_session_token() }, verify=False)

    if ans.status_code != 200:
        request_failed(ans.status_code, BASE_URL+"/login/logout/", ans.json())

    action()

    return


def get_api_version() -> dict[str, str]:

    ans: dict[str,str] = requests.get("http://mafreebox.freebox.fr/api_version", verify=False)
    #print("API info:\n"+str(ans.json()))

    return ans.json()

def action() -> None:

    print("Please select the desired action:\n"\
    "- login\n"\
    "- get_api_version\n"\
    "- get_app_token\n"\
    "- session_start\n"\
    "- session_stop\n"\
    "- lan_browser_interfaces\n"\
    "- clean_old_lan_macs\n"\
    "- exit\n")
    act = input("-> ")
    print("")

    if act == "login":
        login()
    elif act == "get_api_version":
        get_api_version()
    elif act == "get_app_token":
        get_app_token()
    elif act == "session_start":
        session_start()
    elif act == "session_stop":
        session_stop()
    elif act == "lan_browser_interfaces":
        lan_browser_interfaces()
    elif act == "clean_old_lan_macs":
        clean_old_lan_macs()
    elif act == "exit":
        exit(0)
    elif act == "\n":
        action()
    else:
        print("!! Command not recognized\n")
        action()


def retry_auth(data: dict[str, str]) -> dict[Any,Any]:
    ans = requests.post(BASE_URL+"/login/authorize/", data=json.dumps(data), verify=False)
    APP_TOKEN = ans.json().get("result", {}).get("app_token", "")

    return ans


def hmac_sha1(token, challenge) -> str:

    h = hmac.new(token.encode(), challenge.encode(), "sha1")
    return h.hexdigest()


def get_app_token():
    
    data: dict[str,str] = {
        "app_id": "081121",
        "app_name": "freebox_api.py",
        "app_version": "alpha",
        "device_name": "gentoo-hpdv5"
    }
    ans = requests.post(BASE_URL+"/login/authorize/", data=json.dumps(data), verify=False)
    global APP_TOKEN
    APP_TOKEN = ans.json().get("result", {}).get("app_token", "")
    with open(".app_token", "w") as f:
        f.write(APP_TOKEN)

    if ans.status_code == 200:

        print("Waiting 10 seconds for confirmation on the box screen...")
        time.sleep(10)
        auth = requests.get(BASE_URL+"/login/authorize/"+str(ans.json().get("result", {}).get("track_id", -1)), verify=False)

        if auth.json().get("result", {}).get("status", "") != "granted":
            print("Retrying auth request")
            ans = retry_auth(data=data)

            if ans.status_code != 200:
                request_failed(ans.status_code, BASE_URL+"/login/authorize/", ans.json())
                return

            print("Waiting 10 seconds for confirmation on the box screen...")
            time.sleep(10)
            auth = requests.get(BASE_URL+"/login/authorize/"+str(ans.json().get("track_id", -1)), verify=False)

            if auth.json().get("result", {}).get("status", "") != "granted":

                request_failed(auth.status_code, BASE_URL+"/login/authorize/"+str(ans.json().get("track_id", -1)), auth.json())

    else:

        request_failed(ans.status_code, BASE_URL+"/login/authorize/", ans.json())

    action()
    return


def session_start() -> None:
    f = open(".app_token", "r")
    g = open(".challenge", "r")
    password = hmac_sha1(f.read(), g.read())
    data: dict[str,str] = {
        "app_id": "081121",
        "app_version": "alpha",
        "password": password
    }
    f.close()
    g.close()
    ans = requests.post(BASE_URL+"/login/session/", data=json.dumps(data), verify=False)

    if ans.status_code != 200:

        request_failed(ans.status_code, BASE_URL+"/login/session/", ans.json())

    global SESSIONTOKEN
    SESSIONTOKEN = ans.json().get("result", {}).get("session_token", "")

    with open(".session_token", "w") as f:
        f.write(SESSIONTOKEN)
    action()
    return
 

def read_session_token() -> str:

    with open(".session_token", "r") as f:
        return f.read()


def lan_browser_interfaces():
    
    ans = requests.get(BASE_URL+"/lan/browser/interfaces", headers={ "X-Fbx-App-Auth": read_session_token() }, verify=False)
    print(ans.json())

    action()
    return


def clean_old_lan_macs():
    
    ans = requests.get(BASE_URL+"/lan/browser/pub", headers={ "X-Fbx-App-Auth": read_session_token() }, verify=False)

    if ans.status_code != 200:
        request_failed(ans.status_code, BASE_URL+"/lan/browser/pub", ans.json())

    last_seen: list[int] = []
    pub_hosts: list[dict[Any,Any]] = ans.json().get("result", [{}])

    now = datetime.datetime.now()
    delta = datetime.timedelta(days=182)
    now = int((now - delta).timestamp())

    for host in pub_hosts:
        if (host.get("last_time_reachable", -1) < now) and (host.get("last_time_reachable", -1) != 0):
            ans = requests.delete(BASE_URL+"/lan/browser/pub/"+host.get("id","")+"/", headers={ "X-Fbx-App-Auth": read_session_token() }, verify=False)
            if ans.status_code != 200:
                request_failed(ans.status_code, BASE_URL+"/lan/browser/pub/"+host.get("id","")+"/", ans.json())

    action()

    return


if __name__ == "__main__":
    set_globals()
    action()
