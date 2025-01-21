from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache
import asyncio
import random
from datetime import timedelta, datetime

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bggray&Reallywhite", user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.domain = "https://api.catshouse.club/"
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.user_data = None
        self.user_tasks = None
        
        self.earned = 0
        self.earned_session = self.cache.get("earned_session", 0)
        
        self.info_placeholders = "Points: {pts}\nEarned with script: {earned} | Earned this session: {earned_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "fEaHs816_2oQhhfsl6TGH")
        self.mini_sleep: str = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def init(self):
        url = await self.db.get("app_url")
        self.earned = int(await self.db.get("earned", 0))
        auth_token = await self.db.get("auth_token")
        
        self.webclient.user_agent = await get_user_agent(self.db)
        
        while True:
            if not auth_token or not url:
                self.telegram_web_data = await self.session.request_web_view_data("catsgang_bot", self.refferal_code, "join")
                url = self.telegram_web_data.url
                await self.db.update("app_url", url)
                self.webclient.authorization = "tma " + self.telegram_web_data.user_quoted_web_data
                await self.db.update("auth_token", self.webclient.authorization)
                break
            
            else:
                self.webclient.authorization = auth_token
            
            await self.user()
            if not self.user_data:
                auth_token = None
                continue
            
            break
        
        await self.webclient.get("https://cats-frontend.tgapps.store/?tgWebAppStartParam=" + self.refferal_code) # ???
        response = await self.webclient.get(self.domain + "user")
        
        if response.is_json and response.json.get("message") == "User was not found":
            response = await self.webclient.post(self.domain + "user/create?referral_code=" + self.refferal_code, data={})
            if response.status == 200:
                self.user_data = response.json
                
        self.user_tab.add_text_label(2, "[Open in web](%s)" % url)
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def user(self) -> dict:
        response = await self.webclient.get(self.domain + "user")
        if response.status == 200:
            self.user_data = response.json
            return self.user_data
        return None
        
    async def tasks(self) -> dict:
        response = await self.webclient.get(self.domain + "tasks/user?group=cats")
        if response.status == 200:
            self.user_tasks = response.json.get("tasks", [])
            return self.user_tasks
        return []
    async def complete_task(self, id: int):
        response = await self.webclient.post(self.domain + "tasks/" + str(id) + "/complete", data={})
        if response.status == 200:
            return response.json["success"]
        return False
    async def check_task(self, id: int):
        response = await self.webclient.post(self.domain + "tasks/" + str(id) + "/check", data={})
        if response.status == 200:
            return response.json["completed"]
        return False
    
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            pts=format_number(self.pts),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            sleep_time=sleep_time
        )
    
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                await self.user()
                if not self.user_data:
                    self.logger.background("Unable to get user data...")
                    await asyncio.sleep(1)
                    continue
                
                self.pts = int(self.user_data.get("totalRewards", 0))
                self.logger.info("Points:", self.pts)
                self.update_info_panel()
                
                if not self.running_allowed:
                    break
                
                self.logger.background("Checking tasks...")
                self.user_tasks = await self.tasks() or []
                for task in self.user_tasks:
                    if not self.running_allowed:
                        break
                    
                    if task.get("completed") or task.get("type", "?") in ["ACTIVITY_CHALLENGE", "TON_TRANSACTION", "BOOST_CHANNEL", "?"]:
                        continue
                    
                    status = None
                    if task.get("type") == "SUBSCRIBE_TO_CHANNEL":
                        link = task.get("params")["channelUrl"]
                        await self.session.revive(self.name)
                        await self.session.temp_join_channel(self.name, link)
                        status = await self.check_task(task["id"])
                        if status:
                            self.logger.success("Completed task:&white", task.get("title"))
                    
                    elif isinstance(task.get("progress"), dict): 
                        progress = list(task.get("progress").values())
                        params = list(task.get("params").values())
                        if progress[0] == params[0]:
                            status = await self.complete_task(task["id"])
                            if status:
                                self.logger.success("Completed task:&white", task.get("title"))
                    else:
                        status = await self.complete_task(task["id"])
                        if status:
                            self.logger.success("Completed task:&white", task.get("title"))
                    
                    if status:
                        await self.user()
                        bal = int(self.user_data.get("totalRewards", 0))
                        earned = bal - self.pts
                        self.earned += earned
                        self.earned_session += earned
                        self.cache.set("earned_session", self.earned_session)
                        await self.db.update("earned", self.earned)
                        self.pts = bal
                        self.update_info_panel()
                        
                    await asyncio.sleep(*self.mini_sleep)
                
                await self.session.leave_temp_channels(self.name)
                await self.session.revive_end(self.name)
                
                sleep_time = timedelta(hours=4)
                self.logger.info("Sleeping:", str(sleep_time).split(".")[0])
                date_now = datetime.now()
                sleeping_until = datetime.fromtimestamp(date_now.timestamp() + sleep_time.total_seconds())
                while self.running_allowed and date_now < sleeping_until:
                    date_now = datetime.now()
                    self.update_info_panel("Sleeping: " + str(sleeping_until - date_now).split(".")[0])
                    await asyncio.sleep(1)
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module