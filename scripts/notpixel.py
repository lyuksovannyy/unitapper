from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, cache, wait_until, format_number
import asyncio
import random

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab) -> None:
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        # SCRIPT INITIAL SETTINGS
        self.bot_username = "notpixel"
        self.bot_url_short_name = "app" # most of the are using 'app' some may have different short name, someone doesn't have at all short name so you'll need to use mini-app's url instead
        
        # MANDATORY MODULES TO MAKE SCRIPT EASY TO MAKE
        self.logger = logger(self.name, self.session.name, user_tab=user_tab) # custom logger
        self.config = config(self.name)                  # config for script
        self.db = database(self.name, self.session.name) # database to store script's statistics or whatever you want, stores all info in strings...
        self.webclient = webclient(self.session)         # webclient to make all requests
        self.cache = cache(self.name, self.session.name) # used only to save data after script is gonna be restarted (not exited)
        
        self.refresh_config()
        
        self.plate_size = [1000, 1000] # x, y
        self.available_colors = [
            "#e46e6e", "#ffd635", "#7eed56", "#00ccc0", "#51e9f4", "#94b3ff", "#e4abff", "#ff99aa", "#ffb470", "#ffffff",
            "#be0039", "#ff9600", "#00cc78", "#009eaa", "#3690ea", "#6a5cff", "#b44ac0", "#ff3881", "#9c6926", "#898d90",
            "#6d001a", "#bf4300", "#00a368", "#00756f", "#2450a4", "#493ac1", "#811e9f", "#a00357", "#6d482f", "#000000"
        ]
        self.starting_stats = { # self.starting_stats[...] + self.level_step[...] * lvl
            "energyLimit": 4,
            "paintReward": 0.5,
            "reChargeSpeed": 630
        }
        self.level_step = {
            "energyLimit": 1,
            "paintReward": 0.5,
            "reChargeSpeed": 30
        }
        self.available_tasks = [
            dict(
                id="invite1Fren",
                requirements=dict(
                    invite=1
                )
            ),
            dict(
                id="invite3Frens",
                requirements=dict(
                    invite=3
                )
            ),
            dict(
                id="pain20pixels",
                requirements=dict(
                    paint=20
                )
            ),
            dict(
                id="joinSquad",
                requirements=dict(
                    squad=True
                )
            ),
            dict(
                id="telegramPremium",
                requirements=dict(
                    telegram_premium=True
                )
            ),
            dict(
                id="leagueBonusSilver",
                requirements=dict(
                    leagues=["silver", "gold", "platinum"]
                )
            ),
            dict(
                id="leagueBonusGold",
                requirements=dict(
                    leagues=["gold", "platinum"]
                )
            ),
            dict(
                id="leagueBonusPlatinum",
                requirements=dict(
                    leagues=["platinum"]
                )
            ),
            dict(
                id="notPixelChannel",
                requirements=dict(
                    join="https://t.me/notpixel_channel"
                )
            ),
            dict(
                id="notPixelX"
            ),
            dict(
                id="notCoinChannel",
                requirements=dict(
                    join="https://t.me/notcoin"
                )
            ),
            dict(
                id="notCoinX"
            ),
            #dict(
            #    id="notPixelBoostChannel"
            #),
            #dict(
            #    id="leagueBonusBronze",
            #    requirements=dict(
            #        join="https://t.me/notcoin"
            #    )
            #),
            #dict(
            #    id="spendStars"
            #),
            #dict(
            #    id="openLeague"
            #),
        ]
        self.running_allowed = True
        self.telegram_web_data = None
        
        self.balance = 0
        self.stats = {}
        self._earned = 0
        self._earned_session = self.cache.get("earned_session", 0)
        
        self.info_placeholders = "Balance: {bal}\nEarned with script: {earned} | Earned this session: {earned_session}\n{activity}"
        self.info_label = self.user_tab.add_text_label(1)
        self.open_in = self.user_tab.add_text_label(2)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self) -> None:
        '''Update config data if changes were made'''
        self.config.load()
        self.referral_code: str = self.config.get("referral_code", "f407777629")
        self.allow_join_channel_tasks: bool = self.config.get("allow_join_channel_tasks", True)
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def auth(self, revive_session: bool = True) -> None:
        '''Authorize to mini-app and receive new login data'''
        if revive_session:
            await self.session.revive(self.name)
        
        self.telegram_web_data = await self.session.request_web_view_data(self.bot_username, self.referral_code, self.bot_url_short_name)
        self.open_in.object = "[Open in web](%s)" % self.telegram_web_data.url
        
        self.webclient.authorization = "initData " + self.telegram_web_data.user_quoted_web_data
        
        if revive_session:
            await self.session.revive_end(self.name)
    
    async def init(self) -> None:
        '''Starts before the main code (in general used for auth-only things)'''
        self.webclient.user_agent = await get_user_agent(self.db)
        self._earned = float(await self.db.get("earned", 0))
        
        await self.auth(False)
        
    async def start(self) -> None:
        '''Starts after initializing all scripts'''
        await self.run()

    async def cancel(self) -> None:
        '''Function is needed only for soft end of the task\n'''
        self.running_allowed = False

    def update_info_panel(self, activity_text: str = "Active...") -> None:
        '''Web-panel related'''
        self.info_label.object = self.info_placeholders.format(
            bal=format_number(self.balance),
            earned=format_number(self._earned),
            earned_session=format_number(self._earned_session),
            activity=activity_text
        )
    
    async def earned(self, value: int) -> None:
        '''Save "earned" stat'''
        try:
            self._earned += value
            self._earned_session += value
            self.cache.set("earned_session", self._earned_session)
            #await self.db.update("earned", self._earned)
        except:
            pass
    
    # CUSTOM
    
    @property
    def energyLimit(self) -> int:
        return self.starting_stats["energyLimit"] + self.level_step["energyLimit"] * self.stats.get("energyLimit")
    @property
    def paintReward(self) -> int:
        return self.starting_stats["paintReward"] + self.level_step["paintReward"] * self.stats.get("paintReward")
    @property
    def reChargeSpeed(self) -> int:
        return self.starting_stats["reChargeSpeed"] + self.level_step["reChargeSpeed"] * self.stats.get("reChargeSpeed")
    
    @property
    def random_color(self) -> str:
        return random.choice(self.available_colors).upper()
    
    async def get_user(self) -> dict:
        response = await self.webclient.get("https://notpx.app/api/v1/users/me")
        response.raise_for_status()
        return response.json
    
    async def get_status(self) -> dict:
        response = await self.webclient.get("https://notpx.app/api/v1/mining/status")
        response.raise_for_status()
        return response.json
    
    async def paint(self, x: int, y: int, color: str) -> bool:
        # x = x or random.randint(0, self.plate_size[0] - 1)
        # y = y or random.randint(0, self.plate_size[1] - 1)
        # color = color or self.random_color
        
        response = await self.webclient.post(
            "https://notpx.app/api/v1/repaint/start",
            json={
                "newColor": color,
                "pixelId": y * self.plate_size[1] + (x + 1)
            }
        )
        response.raise_for_status()
        earned = self.paintReward #response.json.get("balance") - self.balance
        await self.earned(earned)
        self.balance = int(response.json.get("balance"))
        
        return earned
    
    async def claim_mining(self) -> float | None:
        try:
            response = await self.webclient.get("https://notpx.app/api/v1/mining/claim")
            response.raise_for_status()
            return response.json.get("activated") and response.json.get("claimed")
        except:
            pass
        
    async def check_task(self, task_id: str) -> bool:
        response = await self.webclient.get("https://notpx.app/api/v1/mining/task/check/" + task_id)
        return response.is_json and response.json.get(task_id)
        
    async def join_random_squad(self) -> bool | None:
        await self.session.revive(self.name)
        notgames_data = await self.session.request_web_view_data("notgames_bot", "cmVmPTQwNzc3NzYyOQ==", "squads")
        
        temp_web_client = webclient(self.session)
        
        response = await temp_web_client.post(
            "https://api.notcoin.tg/auth/login",
            json={
                "webAppData": notgames_data.user_quoted_web_data
            }
        )
        
        if not response.is_json:
            return
        
        if response.json.get("statusCode") != 200:
            return
        
        accessToken = response.json.get("data").get("accessToken")
        temp_web_client._headers["x-auth-token"] = "Bearer " + accessToken
        
        squads = (await temp_web_client.get("https://api.notcoin.tg/squads?sort=hot")).json.get("data", {}).get("squads", [])[:5]
        
        squad = random.choice(squads)
        slug = squad["slug"]
        chatId = squad["chatId"]
        squad_response = await temp_web_client.post(
            "https://api.notcoin.tg/squads/" + slug + "/join", 
            headers={
                "x-auth-token": "Bearer " + accessToken,
                "accept": "*/*",
                "Content-Type": "application/json"
            },
            json={
                "chatId": chatId
            }
        )
        squad = squad_response.json.get("data", {}).get("squad")
        if squad:
            self.logger.success("Joined to:", squad.get("name"))
            return True
        
    async def upgrade_booster(self, booster_id: str) -> bool:
        response = await self.webclient.get("https://notpx.app/api/v1/mining/boost/check/" + booster_id)
        data = response.is_json and response.json.get(booster_id)
        if data:
            self.stats[booster_id] += 1
        
        return data
        
    async def run(self):
        '''Your code here'''
        while self.running_allowed:
            try:
                await self.join_random_squad()
                self.refresh_config()
                
                user = await self.get_user()
                if not user:
                    await asyncio.sleep(*self.mini_sleep)
                    self.logger.error("Unable to get user data")
                    continue
                
                status = await self.get_status()
                if not status:
                    await asyncio.sleep(*self.mini_sleep)
                    self.logger.error("Unable to get status data")
                    continue
                
                self.stats: dict = status.get("boosts", self.stats)
                completed_tasks = status.get("tasks", [])
                
                self.balance = user.get("balance")
                self.logger.info("Balance:&cyan", self.balance)
                self.update_info_panel()
                
                self.logger.background("Checking mining...")
                mining_claimed = await self.claim_mining()
                if mining_claimed:
                    await self.earned(mining_claimed)
                    self.logger.success("Claimed:", mining_claimed, "from mining")
                    
                self.update_info_panel()
                await asyncio.sleep(*self.mini_sleep)
                
                self.logger.background("Checking tasks...")
                for task in self.available_tasks:
                    if task["id"] in completed_tasks:
                        continue
                    
                    req = task.get("requirements")
                    if req:
                        if req.get("telegram_premium") and not self.session.account_data.is_premium:
                            continue
                        
                        if req.get("leagues") and status.get("league", "") not in req.get("leagues"):
                            continue
                        
                        if req.get("paint") and user.get("repaints") < req.get("paint"):
                            continue
                        
                        if req.get("invite") and user.get("friends") < req.get("invite"):
                            continue
                        
                        if req.get("join") and self.allow_join_channel_tasks:
                            await self.session.revive(self.name)
                            await self.session.temp_join_channel(self.name, req.get("join"))
                            await asyncio.sleep(*self.mini_sleep)
                            
                        if req.get("squad"):
                            state = await self.join_random_squad()
                            await asyncio.sleep(*self.mini_sleep)
                            if not state:
                                continue
                        
                    state = await self.check_task(task["id"])
                    if state:
                        self.logger.success("Completed", task["id"])
                        
                    self.update_info_panel()
                    await asyncio.sleep(*self.mini_sleep)
                
                await self.session.leave_temp_channels(self.name)
                
                self.logger.background("Checking boosters...")
                for boost, lvl in self.stats.items():
                    if lvl >= 5:
                        continue
                    
                    state = await self.upgrade_booster(boost)
                    if state:
                        self.logger.success("Upgraded", boost, "to", lvl)
                        
                    self.update_info_panel()
                
                self.logger.background("Checking for paint charges...")
                x, y = random.randint(int(self.plate_size[0] * 0.2), int(self.plate_size[0] * 0.8)), random.randint(int(self.plate_size[1] * 0.2), int(self.plate_size[1] * 0.8))
                col = self.random_color
                for _ in range(status.get("charges", 0)):
                    _x, _y = random.randint(int(x * 0.2), int(x * 1.2)), random.randint(int(y * 0.2), int(y * 1.2))
                    status = await self.paint(_x, _y, col)
                    if status:
                        self.logger.success("Painted at: %s, %s coords with %s color, reward: %s" % (_x, _y, col, status))
                        
                    self.update_info_panel()
                    await asyncio.sleep(*self.mini_sleep)
                
                await wait_until(self, self.reChargeSpeed * self.energyLimit + random.randint(30, 60))
                
                await self.auth()
            except Exception as err:
                self.logger.error("Unexpected error occurred:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module