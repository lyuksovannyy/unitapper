import aiohttp
import asyncio
import json
from aiohttp_socks import ProxyConnector, ProxyType

from .misc import parse_proxies

class _Response:
    def __init__(self, status: int, headers: dict, reason: str, text: str) -> None:
        self.status = status
        self.headers = headers
        self.reason = reason
        self.text = text
        self._json = None
        
    def raise_for_status(self) -> Exception | None:
        if self.status > 399:
            raise aiohttp.ClientResponseError("Response status in higher than 400", None)
        
    @property
    def is_json(self) -> bool:
        try:
            self._json = json.loads(self.text)
            return True
        except json.JSONDecodeError:
            return False
    
    @property
    def json(self) -> dict:
        if not self._json:
            self._json = json.loads(self.text)
        
        return self._json

class webclient:
    def __init__(self, session = None):
        self._headers = {}
        
        if session:
            self.proxy = parse_proxies(session.name)
            if self.proxy:
                scheme = self.proxy.get("scheme")
                
                if scheme == "http":
                    self.proxy_type = ProxyType.HTTP
                    
                elif scheme == "socks4":
                    self.proxy_type = ProxyType.SOCKS4
                    
                elif scheme == "socks5":
                    self.proxy_type = ProxyType.SOCKS5
                
                self.proxy_host=self.proxy.get("hostname")
                self.proxy_port=self.proxy.get("port")
                self.proxy_username=self.proxy.get("username")
                self.proxy_password=self.proxy.get("password")
        
        self.timeout = 3
        
    @property
    def _connector(self) -> aiohttp.TCPConnector | ProxyConnector:
        if self.proxy:
            return ProxyConnector(
                proxy_type=self.proxy_type,
                host=self.proxy_host,
                port=self.proxy_port,
                username=self.proxy_username,
                password=self.proxy_password,
            )
        
        return aiohttp.TCPConnector(verify_ssl=False)
        
    @property
    def headers(self):
        return self._headers
    @headers.setter
    def headers(self, value: dict):
        self._headers = value
        
    @property
    def user_agent(self):
        return self._headers.get("User-Agent")
    @user_agent.setter
    def user_agent(self, value: str | None):
        if value is None and "User-Agent" in self._headers:
            del self._headers["User-Agent"]
        elif value is not None:
            self._headers["User-Agent"] = value
        
    @property
    def authorization(self):
        return self._headers.get("Authorization")
    @authorization.setter
    def authorization(self, value: str | None):
        if value is None and "Authorization" in self._headers:
            del self._headers["Authorization"]
        elif value is not None:
            self._headers["Authorization"] = value
        
    async def get(self, url: str, **kwargs) -> _Response:
        async with aiohttp.ClientSession(headers=self._headers, trust_env=True, connector=self._connector) as client:
            while True:
                try:
                    async with client.get(url, **kwargs) as response:
                        return _Response(
                            response.status,
                            response.headers,
                            response.reason,
                            (await response.text())
                        )
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(1)
    
    async def post(self, url: str, **kwargs) -> _Response:
        async with aiohttp.ClientSession(headers=self._headers, trust_env=True, connector=self._connector) as client:
            while True:
                try:
                    async with client.post(url, **kwargs) as response:
                        return _Response(
                            response.status,
                            response.headers,
                            response.reason,
                            (await response.text())
                        )
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(1)
                
    async def options(self, url: str, **kwargs) -> _Response:
        async with aiohttp.ClientSession(headers=self._headers, trust_env=True, connector=self._connector) as client:
            while True:
                try:
                    async with client.options(url, **kwargs) as response:
                        return _Response(
                            response.status,
                            response.headers,
                            response.reason,
                            (await response.text())
                        )
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(1)
                
    async def delete(self, url: str, **kwargs) -> _Response:
        async with aiohttp.ClientSession(headers=self._headers, trust_env=True, connector=self._connector) as client:
            while True:
                try:
                    async with client.delete(url, **kwargs) as response:
                        return _Response(
                            response.status,
                            response.headers,
                            response.reason,
                            (await response.text())
                        )
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(1)