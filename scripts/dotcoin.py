from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache
import asyncio
import random
from datetime import datetime, timedelta

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bgyellow", user_tab=user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name ,self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impqdm5tb3luY21jZXdudXlreWlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDg3MDE5ODIsImV4cCI6MjAyNDI3Nzk4Mn0.oZh_ECA6fA2NlwoUamf1TqF45lrMC0uIdJXvVitDbZ8"
        self.telegram_web_data = None
        self.multitap_lvl = 0
        self.attempts_lvl = 0
        self.dtc_lvl = 0
        self.balance = 0
        self.group_id = 0
        self.earned = self.cache.get("earned")
        self.earned_session = self.cache.get("earned_session", 0)
        
        self.info_placeholders = "Balance: {bal}\nEarned with script: {earned} | Earned this session: {earned_session}\n{sleep_time}"
        self.info_label = self.user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "r_407777629")
        self.save_coins_amount: list = self.config.get("save_coins_amount", [180, 220]) # multiplies with booster
        self.max_lvl: dict = self.config.get("max_lvl", {
            "multitap": 10,
            "attempts": 10
        })
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def init(self):
        url = await self.db.get("app_url")
        self.earned = int(await self.db.get("earned", 0))
        self.auth_token = await self.db.get("auth_token")
        self.webclient.user_agent = await get_user_agent(self.db)
        
        if not self.auth_token:
            await self.session.client.send_message("dotcoin_bot", "/start " + self.refferal_code)
        
        self.telegram_web_data = await self.session.request_web_view_data("dotcoin_bot", self.refferal_code, "https://app.dotcoin.bot/")
        url = self.telegram_web_data.url
        await self.db.update("app_url", url)
        await self.get_token()
            
        self.user_tab.add_text_label(2, "[Open in web](%s)" % url)
        self.webclient._headers["apikey"] = self.API_KEY
        self.webclient._headers["x-telegram-user-id"] = str(self.session.account_data.id)
        self.webclient.authorization = "Bearer " + self.auth_token
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            bal=format_number(self.balance),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            sleep_time=sleep_time
        )
    
    # CUSTOM
    async def get_token(self) -> None:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/functions/v1/getToken",
            json={
                "hash": None,
                "initData": self.telegram_web_data.user_quoted_web_data
            },
            headers = {
                "Authorization": "Bearer " + self.API_KEY,
                "Content-Type": "application/json",
                "Origin": "https://app.dotcoin.bot",
                "Referer": "https://app.dotcoin.bot/"
            }
        )
        if response.status == 200:
            self.auth_token = response.json.get("token")
            await self.db.update("auth_token", self.auth_token)
        
    async def get_user(self) -> dict:
        response = await self.webclient.get("https://api.dotcoin.bot/rest/v1/rpc/get_user_info")
        if response.status == 200:
            return response.json
        
    async def get_tasks(self, platform: str = "android", locale: str = "en", isprem: str = "true") -> list:
        response = await self.webclient.get(
            "https://api.dotcoin.bot/rest/v1/rpc/get_filtered_tasks?platform=%s&locale=%s&is_premium=%s" % (platform, locale, isprem)
        )
        if response.status == 200:
            return response.json
        
    async def complete_task(self, id: int) -> bool:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/rest/v1/rpc/complete_task",
            json={
                "oid": id
            }
        )
        return response.status == 200 and response.json.get("success")
            
    async def get_groups(self) -> list:
        response = await self.webclient.get("https://api.dotcoin.bot/rest/v1/cached_groups?select=id,title,description,slug,coins,users,attempts,multitap&order=coins.desc&limit=100")
        if response.status == 200:
            return response.json
    
    async def join_group(self, id: int) -> bool:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/rest/v1/rpc/join_group",
            json={
                "gid": id
            }
        )
        return response.status == 200
        
    async def leave_group(self) -> bool:
        return await self.join_group(None)
    
    async def add_multitap(self) -> bool:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/rest/v1/rpc/add_multitap",
            json={
                "lvl": self.multitap_lvl
            }
        )
        return response.status == 200
    
    async def add_attempts(self) -> bool:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/rest/v1/rpc/add_attempts",
            json={
                "lvl": self.attempts_lvl
            }
        )
        return response.status == 200
    
    async def save_coins(self, amount: int) -> bool:
        response = await self.webclient.post(
            "https://api.dotcoin.bot/rest/v1/rpc/save_coins",
            json={
                "coins": amount
            }
        )
        return response.status == 200 and response.json.get("success")
    
    async def get_refferals(self) -> dict:
        response = await self.webclient.get("https://api.dotcoin.bot/rest/v1/rpc/get_referrals")
        if response.status == 200:
            return response.json
    
    async def watch_ad(self) -> bool:
        response = await self.webclient.post("https://api.dotcoin.bot/rest/v1/rpc/restore_attempt", json={})
        return response.status == 200 and response.json.get("success")
    
    async def upgradeDTCMiner(self) -> dict:
        response = await self.webclient.post("https://api.dotcoin.bot/functions/v1/upgradeDTCMiner")
        if response.status == 200:
            return response.json
    
    async def earnings_add(self, value: int) -> None:
        self.earned += value
        self.earned_session += value
        self.cache.set("earned_session", self.earned_session)
        await self.db.update("earned", self.earned)
        self.update_info_panel()
    
    async def run(self):
        dtc_upg_until = datetime.now()
        while self.running_allowed:
            try:
                self.refresh_config()
                
                user_data = await self.get_user()
                self.balance = int(user_data.get("balance"))
                self.multitap_lvl = int(user_data.get("multiple_clicks"))
                self.attempts_lvl = int(user_data.get("limit_attempts")) - 9
                self.dtc_lvl = int(user_data.get("dtc_level")) + 1
                
                self.logger.info("Balance:&yellow", self.balance)
                self.update_info_panel()
                
                # choosing the best group
                my_group = user_data.get("group") or {}
                if not my_group:
                    groups = (await self.get_groups()) or {}
                    best_group = {}
                    for group in groups:
                        group_score = group.get("attempts", 0) + group.get("multitap", 0) * 1.1
                        my_group_score = my_group.get("attempts", 0) + my_group.get("multitap", 0) * 1.1
                        if group_score > my_group_score:
                            best_group = group
                    
                    if best_group.get("id") != my_group.get("id"):
                        if my_group:
                            await self.leave_group()
                        
                        await self.join_group(best_group.get("id"))
                        self.logger.success("Joined to the best group with +%s attempts & +%s multitaps" % (best_group.get("attempts"), best_group.get("multitap")))
                        user_data = await self.get_user()
                        await asyncio.sleep(*self.mini_sleep)

                # tasks
                tasks = await self.get_tasks()
                ref_info = await self.get_refferals()
                for task in tasks:
                    if task.get("is_completed"):
                        continue
                    
                    if "Invite" in task.get("title"):
                        ref_amount = int(ref_info.get("total_count"))
                        requirement = int(task.get("title").split(" ", 2)[1])
                        if requirement > ref_amount:
                            continue
                    
                    state = await self.complete_task(task.get("id"))
                    if state:
                        earned = int(task.get("reward"))
                        self.balance += earned
                        await self.earnings_add(earned)
                        self.logger.success("Completed task:&white", task.get("title"), "&rgot:&yellow", earned)
                    await asyncio.sleep(*self.mini_sleep)
                
                # taps
                for attempt in range(0, int(user_data.get("daily_attempts"))):
                    coins_amount = random.randint(*self.save_coins_amount)
                    coins_amount *= int(user_data.get("multiple_clicks"))
                    status = await self.save_coins(coins_amount)
                    if status:
                        self.balance += coins_amount
                        await self.earnings_add(coins_amount)
                        self.update_info_panel("Playing...")
                        self.logger.success("Claimed&yellow", coins_amount, "&rfrom game")
                        
                    await asyncio.sleep(30)
                    
                self.update_info_panel()
                    
                # upgrades
                tap_upg = True
                atm_upg = True
                dtc_upg = True
                while self.running_allowed and tap_upg or atm_upg or dtc_upg:
                    if tap_upg and self.multitap_lvl <= self.max_lvl["multitap"]:
                        price = 2**self.multitap_lvl * 1000
                        if price > self.balance:
                            tap_upg = False
                        else:
                            state = await self.add_multitap()
                            if state:
                                self.balance -= price
                                self.multitap_lvl += 1
                                self.logger.success("Upgraded multitaps to", self.multitap_lvl, "level")
                            else:
                                tap_upg = False
                            await asyncio.sleep(*self.mini_sleep)
                    else:
                        tap_upg = False
                        
                    if atm_upg and self.attempts_lvl <= self.max_lvl["attempts"]:
                        price = 2**self.attempts_lvl * 1000
                        if price > self.balance:
                            atm_upg = False
                        else:
                            state = await self.add_attempts()
                            if state:
                                self.balance -= price
                                self.attempts_lvl += 1
                                self.logger.success("Upgraded attempts to", self.attempts_lvl, "level")
                            else:
                                atm_upg = False
                            await asyncio.sleep(*self.mini_sleep)
                    else:
                        atm_upg = False
                        
                    if int(ref_info.get("total_count")) < self.dtc_lvl or dtc_upg_until > datetime.now():
                        dtc_upg = False
                        
                    if dtc_upg:
                        dtc_price = 5*self.dtc_lvl * 10000
                        dtc_upg = False
                        if dtc_price <= self.balance:
                            state = (await self.upgradeDTCMiner()) or {}
                            code = state.get("code")
                            if code == 22:
                                dtc_upg_until = datetime.now() + timedelta(hours=2)
                            elif code == 20:
                                dtc_upg = True
                                self.logger.background("Temporarily joining to https://t.me/dotcoincommunity")
                                await self.session.revive(self.name)
                                await self.session.temp_join_channel(self.name, "https://t.me/dotcoincommunity")
                            elif code == 21:
                                self.logger.background("To upgrade DTCMiner you need", self.dtc_lvl, "refferals in total")
                            elif state.get("success"):
                                dtc_upg_until = datetime.now() + timedelta(hours=8)
                                self.balance -= dtc_price
                                self.logger.success("Upgraded DTC miner to", self.dtc_lvl)
                                self.dtc_lvl += 1
                            await asyncio.sleep(*self.mini_sleep)
                        
                    self.update_info_panel()
                
                await self.session.leave_temp_channels(self.name)
                
                max_ads_per_hour = 4
                ads_watched = 0
                ad_watch_time = timedelta(seconds=30)
                last_watched_ad_at = datetime.now() - ad_watch_time
                sleep_time = timedelta(hours=1)
                date_now = datetime.now()
                sleep_until = date_now + sleep_time
                self.logger.background("Watching ads for", str(sleep_time).split(".")[0])
                while self.running_allowed and date_now < sleep_until:
                    date_now = datetime.now()
                    self.update_info_panel("Watching ads: " + str(sleep_until - date_now).split(".")[0])
                    
                    if max_ads_per_hour >= ads_watched and last_watched_ad_at <= date_now:
                        ads_watched += 1
                        await self.watch_ad()
                        last_watched_ad_at = date_now + ad_watch_time
                    
                    await asyncio.sleep(1)
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module