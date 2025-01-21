import os
import json
from typing import Tuple, Any, List
from urllib.parse import unquote, parse_qs

from dotenv import load_dotenv
import aiosqlite
import asyncio

import pyrogram
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait, UserAlreadyParticipant, UsernameInvalid, UserNotParticipant
from pyrogram.raw.functions.messages import RequestAppWebView, RequestWebView
from pyrogram.raw.base import AppWebViewResult, WebViewResult
from pyrogram.raw.types import InputBotAppShortName

load_dotenv()

class web_view_data:
    def __init__(self, web_view: AppWebViewResult | WebViewResult) -> None:
        self.url: str = web_view.url
        self.query_id: int | None = web_view.query if isinstance(web_view, WebViewResult) else None
        
        self.full_quoted_raw_web_data = self.url.split("tgWebAppData=", 1)[1].split("&tgWebAppVersion", 1)[0] # web app data
        self.user_quoted_web_data = unquote(self.full_quoted_raw_web_data) # web app data with 'user' quoted only
        self.raw_web_data = unquote(self.user_quoted_web_data) # web app data unquoted
        
        self.web_data = {}
        for param, value in parse_qs(self.raw_web_data).items():
            self.web_data[param] = value[0]
        
        self.web_data["user"] = json.loads(self.web_data["user"])
        self.web_user_data: dict = self.web_data.get("user")
        
        self.version = float(self.url.split("&tgWebAppVersion=", 1)[1].split("&tgWebAppPlatform", 1)[0])
        self._platform = self.url.split("&tgWebAppPlatform=", 1)[1].split("&", 1)[0]
    
    @property
    def platform(self) -> str:
        '''possbile values: android, ios, web, weba, tdesktop'''
        return self._platform
    
    def __str__(self) -> str:
        return self.raw_web_data
    
class telegram_session:
    def __init__(self, session_name: str, proxy: dict = None) -> None:
        self.name = str(session_name).lower()
        self.session_path = "sessions/" + self.name + ".session"
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        self.account_data: pyrogram.types.User = None
        self.cache_data: aiosqlite.Row = None
        self.client = pyrogram.Client(
            name=self.name,
            api_id=self.api_id,
            api_hash=self.api_hash,
            app_version="unitapper-v1.0-release",
            lang_code="en_US",
            workdir="sessions/",
            proxy=proxy
        )
        
        self.revive_queue = []
        self.temp_chats = {}
        self.temp_names = {}
    
    @property
    def proxy(self) -> dict:
        return self.client.proxy
    @proxy.setter
    def proxy(self, value: dict) -> None:
        self.client.proxy = value
    
    async def _get_user_info_from_session_file(self) -> aiosqlite.Row:
        async with aiosqlite.connect(self.session_path) as db:
            db.row_factory = aiosqlite.Row
            response = await db.execute("SELECT * FROM peers")
            # id, username, phone_number, last_update_on
            return await response.fetchone()
    
    async def _remove_session(self, reason: str) -> Any:
        self.cache_data = await self._get_user_info_from_session_file()
        os.remove(self.session_path)
        return (False, reason)
    
    async def check(self) -> Tuple[bool, str]:
        '''Checks if session valid and\n
        account is not bot
        '''
        try:
            async with self.client as session:
                self.account_data = await session.get_me()
                if self.account_data.is_bot:
                    return self._remove_session("Account is bot.")
                
            return True, ""
        except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
            return self._remove_session("Session invalided.")
        
    async def remove(self) -> None:
        if os.path.exists(self.session_path):
            try:
                async with self.client as session:
                    await session.log_out()
            except:
                os.remove(self.session_path)
        
    async def request_web_view_data(self, bot_username: str, start_param: str = None, url_or_short_name: str = "app", platform: str = "android") -> web_view_data:
        '''Request data for mini-app (in general only for auth)
        '''
        while True:
            try:
                peer = await self.client.resolve_peer(bot_username)
                web_view = None
                if "http" in url_or_short_name:
                    web_view = await self.client.invoke(
                        RequestWebView(
                            peer=peer,
                            bot=peer,
                            url=url_or_short_name,
                            start_param=start_param,
                            platform=platform,
                            from_bot_menu=False,
                        )
                    )
                else:
                    app = InputBotAppShortName(bot_id=peer, short_name=url_or_short_name)
                    web_view = await self.client.invoke(
                        RequestAppWebView(
                            peer=peer,
                            app=app,
                            start_param=start_param,
                            platform=platform,
                            write_allowed=True,
                        )
                    )
                    
                return web_view_data(web_view)
            
            except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                return self._remove_session("Session is invalided.")
            
            except FloodWait as flood:
                await asyncio.sleep(flood.value)

    async def temp_join_channel(self, script_name: str, channel_username: str) -> bool:
        while True:
            try:
                channel_username = channel_username if channel_username.startswith("https://t.me/+") else channel_username.removeprefix("https://t.me/")
                chat = await self.client.join_chat(channel_username)
                if script_name not in self.temp_chats:
                    self.temp_chats[script_name] = []
                
                self.temp_chats[script_name].append(chat.id)
                return True
            
            except FloodWait as flood:
                await asyncio.sleep(flood.value)
            
            except:
                return False

    async def leave_temp_channels(self, script_name: str) -> bool:
        while True:
            try:
                if script_name not in self.temp_chats:
                    return
                    
                for id in self.temp_chats[script_name]:
                    await self.client.leave_chat(id)
                    await asyncio.sleep(1.2)
                    
                self.temp_chats[script_name] = []
                return True
            
            except FloodWait as flood:
                await asyncio.sleep(flood.value)
                
            except:
                return False

    async def revive(self, script_name: str):
        '''Yields until another script gonna end his scenario\n
        **Better to avoid this function due to possible errors**
        '''
        if script_name not in self.revive_queue:
            self.revive_queue.append(script_name)
        while self.revive_queue[0] != script_name:
            await asyncio.sleep(0.3)
            
        if not self.client.is_connected:
            await self.client.connect()
        
    async def revive_end(self, script_name: str): # ugly
        if script_name in self.revive_queue:
            self.revive_queue.remove(script_name)
        if self.client.is_connected and len(self.revive_queue) == 0:
            await self.client.disconnect()

def get_sessions(proxies: dict = {}) -> List[telegram_session]:
    if not os.path.exists("sessions"):
        os.mkdir("sessions")
    
    sessions = []
    for file in os.listdir("sessions"):
        if file.endswith(".session"):
            session_name = file.removesuffix(".session")
            sessions.append(
                telegram_session(
                        session_name, 
                        proxies.get(session_name, None)
                    )
                )
    
    return sessions

def get_sessions_count() -> int:
    if not os.path.exists("sessions"):
        os.mkdir("sessions")
        
    return len(os.listdir("sessions"))