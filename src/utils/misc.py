import os
from ua_generator import generate
from datetime import datetime, timedelta
import asyncio
    
from .. import cache
    
def split_list(lst: list, max_size: int):
    return [lst[i:i + max_size] for i in range(0, len(lst), max_size)]

def generate_user_agent():
    ua = generate(device="mobile", platform="android", browser=("chrome", "edge"))
    return ua

async def get_user_agent(db): # database.database
    ua = generate_user_agent()
    return await db.get("user_agent", ua.text)

def format_number(number: int | float | str) -> str:
    '''formats given number\n
    example: 100000 -> 100k, 18528341294.0 -> 18b
    '''
    if isinstance(number, str):
        if "." in number:
            number = float(number)
        else:
            number = int(number)
    
    if 1000 > number:
        return str(number)
    
    number = int(number)
    if number < 1_000_000 and number > 999:
        return str(int(number / 1_000)) + "k"
    
    elif number < 1_000_000_000 and number > 999_999:
        return str(int(number / 1_000_000)) + "m"
    
    elif number < 1_000_000_000_000 and number > 999_999_999:
        return str(int(number / 1_000_000_000)) + "b"
    
    elif number < 1_000_000_000_000_000 and number > 999_999_999_999:
        return str(int(number / 1_000_000_000_000)) + "aa"
    
    elif number < 1_000_000_000_000_000_000 and number > 999_999_999_999_999:
        return str(int(number / 1_000_000_000_000_000)) + "ab"
    
    elif number < 1_000_000_000_000_000_000_000 and number > 999_999_999_999_999_999:
        return str(int(number / 1_000_000_000_000_000_000)) + "ac"
    
    else:
        return "999ac+"

def dict_proxy(proxy: str = None) -> dict | None:
    if proxy is None:
        return None
    
    response = {}
    if proxy.startswith("http://") or proxy.startswith("https://"):
        response["scheme"] = "http"
        
    elif proxy.startswith("socks4://"):
        response["scheme"] = "socks4"
        
    elif proxy.startswith("socks5://"):
        response["scheme"] = "socks5"

    raw_proxy = proxy.split("//")[1]
    if "@" in raw_proxy: # have auth
        parts = raw_proxy.split("@")
        raw_proxy = parts[1]
        
        auth = parts[0].split(":")
        response["username"] = auth[0]
        response["password"] = auth[1]

    address = raw_proxy.split(":")
    response["hostname"] = address[0]
    response["port"] = int(address[1])
    
    return response

def parse_proxies(session_name: str = None) -> dict | str | None:
    cached_proxies = cache("__proxies__", "root")
    if cached_proxies.get("data"):
        if session_name:
            return cached_proxies.get("data").get(session_name)
        
        return cached_proxies.get("data")
    
    if not os.path.exists("proxies.txt"):
        with open("./proxies.txt", "w", encoding="utf-8") as f:
            f.write(
'''# supports socks4, socks5, http, https
# supports authorization aswell
# example how to provide proxies:
# session1 http://proxy_host:proxy_port
# session2 socks5://proxy_host:proxy_port
# session3 https://username:password@proxy_host:proxy_port
# session4 socks4://username:password@proxy_host:proxy_port
# you can also use variables for easier proxy change in future
# an_http_proxy=http://proxy_host:proxy_port # setting proxy to an variable
# session5 an_http_proxy # setting variable-proxy to session
# session6 an_http_proxy''')
    
    proxies_raw = ""
    proxies = {} # {session: proxy}
    
    with open("./proxies.txt", "r", encoding="utf-8") as f:
        proxies_raw = f.read()
        
    variables = {}
    for line in proxies_raw.split("\n"):
        if line.startswith("#") or line.replace(" ", "") == "":
            continue
        
        if "=" in line:
            key, value = line.replace(" ", "").split("=")
            variables.update({key: value})
        
        elif session_name is None or line.startswith(session_name):
            parts = line.split(" ")
            session = parts[0]
            proxy = dict_proxy(variables.get(parts[1], parts[1]))
            
            proxies.update({session: proxy})
    
    cached_proxies.set("data", proxies)
    if session_name:
        return proxies.get(session_name)
    
    return proxies

async def wait_until(self_node, wait_until: datetime | int | float = None, activity_text: str = "Sleeping", min_wait_time: int = 600) -> None:
    '''
    :param: self_node: self | Must contain: update_info_panel, logger, running_allowed
    :param: wait_until: datetime or int to wait until the sleep is completed (default is 600 = 10mins)
    :param: min_wait_time: if `wait_until` is None then this value gonna be used instead
    '''
    
    date_now = datetime.now()
    
    if wait_until is None:
        wait_until = min_wait_time
        
    if isinstance(wait_until, int) or isinstance(wait_until, float):
        wait_until = date_now + timedelta(seconds=wait_until)
    
    activity_text = activity_text + ": "
    self_node.logger.info(activity_text + str(wait_until - date_now).split(".")[0])
    while self_node.running_allowed and date_now < wait_until:
        date_now = datetime.now()
        self_node.update_info_panel(activity_text + str(wait_until - date_now).split(".")[0])
        await asyncio.sleep(1)
    
    self_node.update_info_panel("...")