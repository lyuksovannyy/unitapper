from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache, wait_until
import asyncio
import random
from datetime import datetime
import json

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.domain = "https://cms-api.nomis.cc/api/"
        # API Key from java script
        self.API_KEY = "8e25d2673c5025dfcd36556e7ae1b330095f681165fe964181b13430ddeb385a0844815b104eff05f44920b07c073c41ff19b7d95e487a34aa9f109cab754303cd994286af4bd9f6fbb945204d2509d4420e3486a363f61685c279ae5b77562856d3eb947e5da44459089b403eb5c80ea6d544c5aa99d4221b7ae61b5b4cbb55"
        
        self.logger = logger(self.name, self.session.name, "&bgmagenta&black", user_tab=user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.webclient._headers = {
            'Origin': 'https://telegram.nomis.cc',
            'Referer': 'https://telegram.nomis.cc/'
        }
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.user_data = {}
        self.user_id = 0
        
        self.points = 0
        self.earned = 0
        self.earned_session = self.cache.get("earned_session", 0)
        
        self.completed_tasks_ids = [] # only for bugged tasks that cannot be completed event if you completed them
        
        self.info_placeholders = "Points: {pts}\nEarned with script: {earned} | Earned this session: {earned_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "ref_wz7hlBn2EP")
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def init(self):
        self.earned = int(await self.db.get("earned", 0))
        self.completed_tasks_ids = json.loads(await self.db.get("compl_tasks_ids", "[]"))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        self.webclient.authorization = "Bearer " + self.API_KEY
        
        self.telegram_web_data = await self.session.request_web_view_data("NomisAppBot", self.refferal_code, "https://telegram.nomis.cc/")
        self.user_tab.add_text_label(2, "[Open in web](%s)" % self.telegram_web_data.url)
        
        self.webclient._headers["X-App-Init-Data"] = self.telegram_web_data.user_quoted_web_data

        await self.auth()
        self.user_id = self.user_data.get("id")
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            pts=format_number(self.points),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            sleep_time=sleep_time
        )
    
    # CUSTOM
    async def auth(self) -> bool:
        response = await self.webclient.post(
            self.domain + "users/auth", 
            json={
                "telegram_user_id": str(self.session.account_data.id),
                "telegram_username": self.session.account_data.username or "",
                "referrer": self.refferal_code.removeprefix("ref_")
            }
        )
        if response.status == 201:
            self.user_data = response.json
        
        return response.status == 201
    
    async def farm_data(self) -> dict:
        response = await self.webclient.get(self.domain + "users/farm-data")
        if response.status == 200:
            return response.json
        
    async def start_farm(self) -> dict:
        '''also updates user_data'''
        response = await self.webclient.post(
            "https://cms-api.nomis.cc/api/users/start-farm",
            json={
                "user_id": self.user_id
            }
        )
        if response.status == 200:
            self.user_data.update(response.json)
            return response.json
        
    async def claim_farm(self) -> dict:
        '''also updates user_data'''
        response = await self.webclient.post(
            "https://cms-api.nomis.cc/api/users/claim-farm",
            json={
                "user_id": self.user_id
            }
        )
        if response.status == 200:
            self.user_data.update(response.json)
            return response.json
    
    async def tasks(self) -> list:
        response = await self.webclient.get(self.domain + "users/tasks")
        if response.status == 200:
            return response.json
    
    async def verify_task(self, task_id: int) -> int | None:
        response = await self.webclient.post(
            "https://cms-tg.nomis.cc/api/ton-twa-user-tasks/verify",
            json={
                "task_id": task_id,
                "user_id": self.user_id
            }
        )
        if response.status == 200:
            data = response.json.get("data", response.json)
            if data.get("result"):
                return int((data.get("reward") + data.get("extraPoints")) / 1000)
    
    async def ref_data(self) -> dict:
        response = await self.webclient.get(self.domain + "users/referrals-data?user_id=" + str(self.user_id))
        if response.status == 200:
            return response.json
    
    async def claim_ref(self) -> bool:
        response = await self.webclient.post(
            "https://cms-tg.nomis.cc/api/ton-twa-users/claim-referral", 
            json={
                "user_id": self.user_id
            }
        )
        if response.status == 200:
            return response.json.get("result")
        return False
    
    async def earned_add(self, value: int) -> None:
        self.earned += int(value)
        self.earned_session += int(value)
        self.cache.set("earned_session", self.earned_session)
        await self.db.update("earned", self.earned)
    
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                
                date_now = datetime.now()
                farm_data = await self.farm_data()
                self.points = int(farm_data.get("points") / 1000)
                
                next_claim_at = self.user_data.get("nextFarmClaimAt")
                next_claim_at = datetime.fromtimestamp(datetime.fromisoformat(next_claim_at.replace('Z', '+00:00')).timestamp()) if next_claim_at else None
                
                self.logger.info("Points:&blue", self.points)
                self.update_info_panel()
                
                self.logger.background("Checking daily reward...")
                if self.user_data.get("checkIn", {}).get("updated"):
                    points = int(self.user_data.get("checkIn").get("points") / 1000)
                    await self.earned_add(points)
                    self.points += points
                    self.logger.success("Claimed:&blue", points, "&rfrom daily")
                    
                self.update_info_panel()
                
                self.logger.background("Trying to claim points from farm...")
                if next_claim_at and next_claim_at <= date_now:
                    state = await self.claim_farm()
                    if state:
                        next_claim_at = None
                        earned = int(farm_data.get("pointsPerClaim") / 1000)
                        await self.earned_add(earned)
                        self.points += earned
                        self.logger.success("Claimed&blue", earned, "&rfrom farming")
                        
                self.update_info_panel()
                        
                self.logger.background("Trying to start farm...")
                if not next_claim_at:
                    state = await self.start_farm()
                    if state:
                        next_claim_at = self.user_data.get("nextFarmClaimAt")
                        next_claim_at = datetime.fromtimestamp(datetime.fromisoformat(next_claim_at.replace('Z', '+00:00')).timestamp()) if next_claim_at else None
                
                        self.logger.success("Started farming...")
                
                self.logger.background("Checking refferals revenue...")
                ref_data = await self.ref_data()
                next_ref_claim_at = ref_data.get("nextReferralsClaimAt")
                next_ref_claim_at = datetime.fromtimestamp(datetime.fromisoformat(next_ref_claim_at.replace('Z', '+00:00')).timestamp()) if next_ref_claim_at else None
                if ref_data.get("claimAvailable") > 0 and next_ref_claim_at <= date_now:
                    status = await self.claim_ref()
                    if status:
                        amount = int(ref_data.get("claimAvailable") / 1000)
                        await self.earned_add(amount)
                        self.points += amount
                        self.logger.success("Claimed:&blue", amount, "&rfrom refferals")
                        
                self.update_info_panel()
                
                self.logger.background("Checking tasks...")
                tasks = await self.tasks()
                for category in tasks:
                    if category.get("isDisabled") or not self.running_allowed:
                        continue
                    
                    for task in category.get("ton_twa_tasks", []):
                        if task.get("isDisabled"):
                            continue
                        
                        if task.get("handler") not in [None, "telegramAuth"]:
                            continue
                        
                        task_name: str = task.get("title")
                        task_link: str = task.get("link")
                        task_id: int = task.get("id")
                        
                        if "start" in task_link: # bot link
                            pass
                        
                        if task_id in self.completed_tasks_ids:
                            continue
                        
                        self.completed_tasks_ids.append(task_id)
                        
                        if task_link.startswith("https://t.me/") or task_link.startswith("http://t.me/"):
                            self.logger.background("Temporarily joining to:", task_link)
                            await self.session.revive(self.name)
                            await self.session.temp_join_channel(self.name, task_link)
                            await asyncio.sleep(*self.mini_sleep)
                        
                        reward = await self.verify_task(task_id)
                        if reward:
                            self.points += reward
                            await self.earned_add(reward)
                            self.logger.success("Completed task:&white", task_name, "&rclaimed:&blue", reward)
                            
                            self.update_info_panel()
                        
                        await asyncio.sleep(*self.mini_sleep)
                
                await self.db.update("compl_tasks_ids", str(self.completed_tasks_ids))
                self.update_info_panel()
                
                await self.session.leave_temp_channels(self.name)
                await self.session.revive_end(self.name)
                
                await wait_until(self, next_claim_at)
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module