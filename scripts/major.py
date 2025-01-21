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
        
        self.logger = logger(self.name, self.session.name, "&bgyellow&black", user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.blocked_until = 0.0
        self.telegram_web_data = None
        self.user_data = None
        self.disallowed_tasks_types = [
            "boost",
            "boost_channel",
            "donate",
            "ton_transaction"
        ]
        
        self.rating = 0
        self.earned = 0
        self.earned_session = self.cache.get("earned_session", 0)
        self.completed_tasks = 0
        self.completed_tasks_session = self.cache.get("completed_tasks_session", 0)
        
        self.info_placeholders = "Rating: {rating}\nEarned with script: {earned} | Earned this session: {earned_session}\nCompleted tasks with script: {completed_tasks} | Completed tasks this session: {completed_tasks_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "407777629")
        self.bonus_coins: list = self.config.get("bonus_coins", [800, 1000])
        self.swipe_coins: list = self.config.get("swipe_coins", [2000, 2500])
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def init(self):
        url = await self.db.get("app_url")
        self.earned = int(await self.db.get("earned", 0))
        self.completed_tasks = int(await self.db.get("compl_tasks", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        self.webclient.authorization = await self.db.get("access_token")
        
        while True:
            if not self.webclient.authorization:
                self.telegram_web_data = await self.session.request_web_view_data("major", self.refferal_code, "start")
                url = self.telegram_web_data.url
                await self.db.update("app_url", url)
                response = await self.webclient.post("https://major.glados.app/api/auth/tg/", json={"init_data": str(self.telegram_web_data)})
                if response.status == 200:
                    token_type = response.json["token_type"].capitalize()
                    access_token = response.json["access_token"]
                    self.webclient.authorization = token_type + " " + access_token
                    await self.db.update("access_token", self.webclient.authorization)
                    break
        
            response = await self.webclient.get("https://major.glados.app/api/users/" + str(self.session.account_data.id) + "/")
            if response != 200:
                self.webclient.authorization = None
                continue
            
            break
        
        self.user_tab.add_text_label(2, "[Open in web](%s)" % url)
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def user(self) -> dict:
        response = await self.webclient.get("https://major.glados.app/api/users/" + str(self.session.account_data.id) + "/")
        if response.status == 200:
            self.user_data = response.json
            return self.user_data
        
    async def visit(self) -> dict:
        response = await self.webclient.post("https://major.glados.app/api/user-visits/visit/")
        if response.status == 200:
            return response.json
        
    async def get_squads(self, limit: int = 3) -> dict:
        response = await self.webclient.get("https://major.glados.app/api/squads/?limit=" + str(limit))
        if response.status == 200:
            return response.json
    async def join_squad(self, id: int) -> bool:
        response = await self.webclient.post("https://major.glados.app/api/squads/" + str(id) + "/join/")
        if response.is_json:
            return response.json.get("status") == "ok"
            
    async def bonus_coin(self, amount: int) -> bool:
        response = await self.webclient.post("https://major.glados.app/api/bonuses/coins/", json={"coins": amount})
        if response.is_json:
            detail = response.json.get("detail", {})
            is_blocked = detail.get("blocked_until")
            if is_blocked:
                self.blocked_until = is_blocked
                return False
            
            status = response.json.get("success")
            if status:
                await asyncio.sleep(60)
                
            return status
        
    async def roulette(self) -> dict | None:
        response = await self.webclient.post("https://major.glados.app/api/roulette/")
        if response.is_json:
            detail = response.json.get("detail", {})
            is_blocked = detail.get("blocked_until")
            if is_blocked:
                self.blocked_until = is_blocked
                return None
                
            return response.json
        
    async def swipe_coin(self, amount: int) -> bool:
        response = await self.webclient.post("https://major.glados.app/api/swipe_coin/", json={"coins": amount})
        if response.is_json:
            detail = response.json.get("detail", {})
            is_blocked = detail.get("blocked_until")
            if is_blocked:
                self.blocked_until = is_blocked
                return False
            
            status = response.json.get("success")
            if status:
                await asyncio.sleep(60)
                
            return status
        
    async def tasks(self, is_daily: bool = False) -> list:
        while True:
            response = await self.webclient.get("https://major.glados.app/api/tasks/?is_daily=" + str(is_daily).lower())
            if response.status == 200 and response.is_json:
                return response.json
            await asyncio.sleep(*self.mini_sleep)
    async def complete_task(self, id: str) -> bool:
        response = await self.webclient.post("https://major.glados.app/api/tasks/", json={"task_id": id})
        if response.is_json:
            return response.json.get("is_completed")
            
    async def refferals(self) -> list:
        response = await self.webclient.get("https://major.glados.app/api/users/referrals/")
        if response.status == 200:
            return response.json
            
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            rating=format_number(self.rating),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            completed_tasks=format_number(self.completed_tasks),
            completed_tasks_session=format_number(self.completed_tasks_session),
            sleep_time=sleep_time
        )
    
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                
                await self.user()
                if not self.user_data:
                    await asyncio.sleep(1)
                    continue
                
                self.rating = int(self.user_data["rating"])
                self.logger.info("Rating:&yellow", self.rating)
                self.update_info_panel()
                
                self.logger.background("Checking tasks...")
                daily_tasks = await self.tasks(True)
                tasks = await self.tasks()
                tasks.extend(daily_tasks)
                refferals = (await self.refferals()) or []
                refferals = len(refferals)
                for task in tasks:
                    if not self.running_allowed:
                        break
                    
                    if task.get("is_completed"):
                        continue
                    
                    if task["type"] == "subscribe_channel":
                        await self.session.revive(self.name)
                        channel_url = task["payload"]["url"]
                        self.logger.background("Joining temporarily to:", channel_url)
                        await self.session.temp_join_channel(self.name, channel_url)
                        
                    elif task["type"] == "referral" and task["payload"]["amount"] > refferals:
                        continue
                        
                    status = await self.complete_task(task["id"])
                    if status:
                        self.completed_tasks += 1
                        self.completed_tasks_session += 1
                        self.cache.set("completed_tasks_session", self.completed_tasks_session)
                        await self.db.update("compl_tasks", self.completed_tasks)
                        self.update_info_panel()
                        
                        self.logger.success("Completed:&white", task["title"], "&rtask")
                        
                    await asyncio.sleep(*self.mini_sleep)
            
                await self.session.leave_temp_channels(self.name)
                await self.session.revive_end(self.name)
            
                self.logger.background("Checking daily rewards...")
                visit = await self.visit()
                if visit and visit.get("is_increased") and visit.get("is_allowed"):
                    self.logger.success("Daily streak increased:&bright", visit.get("streak", "?"), "&rstreak")
                
                await self.user()
                new_bal = int(self.user_data["rating"])
                earned = new_bal - self.rating
                self.earned += earned
                self.earned_session += earned
                self.cache.set("earned_session", self.earned_session)
                await self.db.update("earned", self.earned)
                self.rating = new_bal
                
                self.update_info_panel()
                
                self.logger.background("Checking current squad...")
                if self.user_data.get("squad_id") is None:
                    squads = await self.get_squads()
                    squad = squads[0]
                    state = await self.join_squad(squad["id"])
                    if state:
                        self.logger.success("Joined:&white", squad["name"], "&rsquad")
                
                self.logger.background("Checking available bonuses...")
                now = datetime.now().timestamp()
                if self.blocked_until < now:
                    amount = random.randint(*self.bonus_coins)
                    is_bonus_available = await self.bonus_coin(random.randint(*self.bonus_coins))
                    if is_bonus_available:
                        self.earned += amount
                        self.earned_session += amount
                        self.rating += amount
                        self.logger.success("Claimed coin bonus and got:&yellow", amount, "&rrating")
                    
                    is_roulette_available = await self.roulette()
                    if is_roulette_available:
                        reward = int(is_roulette_available.get("rating_award"))
                        self.earned += reward
                        self.earned_session += reward
                        self.rating += reward
                        self.logger.success("Claimed roulette and got:&yellow", reward)
                    
                    amount = random.randint(*self.swipe_coins)
                    is_swipe_available = await self.swipe_coin(amount)
                    if is_swipe_available:
                        self.earned += amount
                        self.earned_session += amount
                        self.rating += amount
                        self.logger.success("Claimed swipe bonus and got:&yellow", amount, "&rrating")
                
                self.cache.set("earned_session", self.earned_session)
                await self.db.update("earned", self.earned)
                self.update_info_panel()
                
                sleep_time = self.blocked_until - now
                sleep_time = sleep_time if sleep_time > 60 else 60
                sleep_until = timedelta(seconds=sleep_time)
                self.logger.info("Sleeping:", str(sleep_until).split(".")[0])
                date_now = datetime.now()
                sleep_until = date_now + sleep_until
                while self.running_allowed and date_now < sleep_until:
                    date_now = datetime.now()
                    self.update_info_panel("Sleeping: " + str(sleep_until - date_now).split(".")[0])
                    await asyncio.sleep(1)
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module