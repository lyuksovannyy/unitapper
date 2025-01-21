from src import telegram_session, logger, config, webclient, database, get_user_agent, WebUserTab, format_number, cache, wait_until
import asyncio
import random
import string
from aiohttp import ClientTimeout
from datetime import timedelta, datetime

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.config = config(self.name)
        self.logger = logger(self.name, self.session.name, "&bgpurple", user_tab)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.points_balance = 0
        self.play_passes = 0
        self.next_farm_claim_at = 0
        
        self.earned = 0
        self.played = 0
        self.earned_session = self.cache.get("earned_session", 0)
        self.played_session = self.cache.get("played_session", 0)
        
        self.info_placeholders = 'Points: {pts} | PlayPasses: {tickets}\nEarned with script: {earned} | Earned this session: {earned_session} | Played with script: {played} | Played this session: {played_session}\n{sleep_time}'
        self.info_label = user_tab.add_text_label(1)
        self.openin = self.user_tab.add_text_label(2, "...")
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "ref_cKsp5uTxrv")
        self.spend_play_passes: bool = self.config.get("spend_playPasses", True)
        self.drop_game_points: list = self.config.get("drop_game_points", [280, 300])
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
        
    async def init(self):
        self.earned = int(await self.db.get("earned", 0))
        self.played = int(await self.db.get("played", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        
        await self.reauth(False)
            
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def reauth(self, revive_session: bool = True) -> None:
        if revive_session:
            await self.session.revive(self.name)
            
        username = None
        while self.running_allowed:
            self.webclient.authorization = None
            self.telegram_web_data = await self.session.request_web_view_data("BlumCryptoBot", self.refferal_code)
            
            json = {
                "query": self.telegram_web_data.user_quoted_web_data,
                "referralToken": self.refferal_code
            }
            
            if username:
                json.update({"username": username})
                
            try:
                response = await self.webclient.post(
                    url="https://user-domain.blum.codes/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                    json=json,
                    headers={
                        "origin": "https://telegram.blum.codes",
                        "content-type": "application/json"
                    }
                )
                
            except TimeoutError:
                await asyncio.sleep(1)
                continue
            
            except Exception as e:
                self.logger.error("Unexpected error while logging in:", e)
                await asyncio.sleep(1)
                continue
            
            if response.status == 200:
                data: dict = response.json.get("token")
                self.ref_token = data.get("refresh")
                self.webclient.authorization = "Bearer " + data.get("access")
                break
            
            elif response.status == 400 and response.json.get("message") == "Invalid username":
                while True:
                    username = ''.join(random.choice(string.ascii_lowercase) for i in range(random.randint(8, 12)))
                    response = await self.webclient.post("https://gateway.blum.codes/v1/user/username/check", data={"username": username})
                    if response.status == 200:
                        self.logger.success("Using", username, " username for registration...")
                        break
                    await asyncio.sleep(0.3)
                continue
            
            self.logger.error(response.status, response.text[:128])
            await asyncio.sleep(1)
            
        self.openin.object = "[Open in web](%s)" % self.telegram_web_data.url
        if revive_session:
            await self.session.revive_end(self.name)
    
    async def _validate_token(self, response, asked_by = "?") -> None:
        '''Checks if request has valid token
        '''
        try:
            valid = True
            if response.status == 200:
                valid = True
            elif response.status == 401:
                valid = '16' not in response.text and "Invalid jwt token" not in response.text

            if not valid and self.running_allowed:
                self.logger.background(asked_by + " Token invalided...")
                self.webclient.authorization = None
                response = await self.webclient.post(
                    "https://gateway.blum.codes/v1/auth/refresh", 
                    json={"refresh": self.ref_token}
                )
                if response.status == 200:
                    access = response.json.get("access")
                    self.ref_token = response.json.get("refresh")
                    self.webclient.authorization = "Bearer " + access
                    self.logger.background("Refreshed token")
                    return
                
                await self.reauth()
            
        except Exception as err:
            self.logger.error("self._validate_token raised an error:", err)
            await asyncio.sleep(1)
            
    async def balance(self) -> int | int:
        '''Returns balance, playPasses
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.get("https://game-domain.blum.codes/api/v1/user/balance")
                await self._validate_token(response, "balance")
                if response.status == 200:
                    self.points_balance = int(float(response.json["availableBalance"]))
                    self.play_passes = response.json["playPasses"]
                    return self.points_balance, self.play_passes
                
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.balance raised an error:", err)
            await asyncio.sleep(1)
    
    async def remain_time(self) -> int | None:
        '''Returns seconds to end of the farm or\n
        None if farm not started
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.get("https://game-domain.blum.codes/api/v1/user/balance")
                await self._validate_token(response, "remain_time")
                if response.status == 200:
                    is_farming = response.json.get("farming", None)
                    if is_farming:
                        self.next_farm_claim_at = is_farming["endTime"]
                        remains = int(float(self.next_farm_claim_at - response.json["timestamp"])) / 1000
                        return remains if remains > 0 else 0
                    return None
                
                await asyncio.sleep(1)
        
        except Exception as err:
            self.logger.error("self.remain_time raised an error:", err)
            await asyncio.sleep(1)
    
    async def get_tribe_leaderboard(self) -> list:
        try:
            while self.running_allowed:
                response = await self.webclient.get("https://tribe-domain.blum.codes/api/v1/tribe/leaderboard")
                await self._validate_token(response, "get_tribe_leaderboard")
                if response.status == 200:
                    return response.json.get("items")
    
                await asyncio.sleep(1)
                        
        except Exception as err:
            self.logger.error("self.get_tribe_leaderboard raised an error:", err)
            await asyncio.sleep(1)
    async def get_tribe(self) -> dict | None:
        '''Get tribe info\n
        title: str, chatname: str, id: str, ...
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.get("https://tribe-domain.blum.codes/api/v1/tribe/my")
                await self._validate_token(response, "get_tribe")
                if response.status == 200:
                    return response.json
                elif response.status == 404:
                    return None
    
                await asyncio.sleep(1)
                        
        except Exception as err:
            self.logger.error("self.get_tribe raised an error:", err)
            await asyncio.sleep(1)
    async def join_tribe(self, tribe_id: str) -> bool:
        '''Join an tribe
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://tribe-domain.blum.codes/api/v1/tribe/" + tribe_id + "/join")
                await self._validate_token(response, "join_tribe")
                if response.status == 200:
                    return response.text == "OK"
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.join_tribe raised an error:", err)
            await asyncio.sleep(1)
    
    async def start_farm(self) -> bool:
        '''Start farming
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://game-domain.blum.codes/api/v1/farming/start")
                await self._validate_token(response, "start_farm")
                if response.status == 200:
                    self.next_farm_claim_at = response.json["endTime"]
                    return True
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.start_farm raised an error:", err)
            await asyncio.sleep(1)
    async def claim_farm(self) -> bool:
        '''Claim farm
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://game-domain.blum.codes/api/v1/farming/claim")
                await self._validate_token(response, "claim_farm")
                if response.status == 200:
                    self.points_balance = int(float(response.json["availableBalance"]))
                    self.play_passes = response.json["playPasses"]
                    return True
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.claim_farm raised an error:", err)
            await asyncio.sleep(1)
    
    async def get_refferals(self) -> dict:
        '''Get refferals info\n
        ammountForClaim: str(int), canClaim: bool, usedInvitation: str(int), ...
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.get("https://user-domain.blum.codes/api/v1/friends/balance")
                await self._validate_token(response, "get_refferals")
                if response.status == 200:
                    return response.json
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.get_refferals raised an error:", err)
            await asyncio.sleep(1)
    async def claim_referral(self) -> dict:
        '''Claim refferals points\n
        ?, ...
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://user-domain.blum.codes/api/v1/friends/claim")
                await self._validate_token(response, "claim_refferal")
                if response.status == 200:
                    return response.json
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.claim_referral raised an error:", err)
            await asyncio.sleep(1)
            
    async def claim_daily(self) -> bool:
        '''Claim daily reward
        '''
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180")
                await self._validate_token(response, "claim_daily")
                if response.status in [200, 400]:
                    return response.text == "OK"
    
                await asyncio.sleep(1)
            
        except Exception as err:
            self.logger.error("self.claim_daily raised an error:", err)
            await asyncio.sleep(1)
            
    async def _start_or_claim_task(self, task: dict):
        STARTED = False
        if task.get('status') == "NOT_STARTED":
            response = await self.webclient.post("https://earn-domain.blum.codes/api/v1/tasks/" + task['id'] + "/start")
            STARTED = response.status == 200
            await asyncio.sleep(random.randint(*self.mini_sleep))
            
        if STARTED or task.get('status') == "READY_FOR_CLAIM":
            response = await self.webclient.post("https://earn-domain.blum.codes/api/v1/tasks/" + task['id'] + "/claim")
            if response.status == 200:
                earned = int(response.json.get('reward', 0))
                self.earned += earned
                self.earned_session += earned
                self.cache.set("earned_session", self.earned_session)
                await self.db.update("earned", self.earned)
                
                self.logger.success("Done&white", task['title'], "&rtask | Claimed:&bright", earned)
                self.update_info_panel()
                await asyncio.sleep(random.randint(*self.mini_sleep))
        
    async def do_tasks(self):
        try:
            response = await self.webclient.get("https://earn-domain.blum.codes/api/v1/tasks")
            if response.status == 200:
                for category in response.json:
                    if not self.running_allowed:
                        break
                    
                    tasks = category['tasks'] if len(category['tasks']) > 0 else category['subSections']
                    for task in tasks:
                        if not self.running_allowed:
                            break
                    
                        subtasks = task['subTasks'] if task.get("subTasks") else task.get("tasks")
                        if subtasks:
                            for subtask in subtasks:
                                if not self.running_allowed:
                                    break
                                
                                await self._start_or_claim_task(subtask)
                            
                        else:
                            progress = task.get("progressTarget")
                            if progress:
                                if progress["progress"] == progress["target"]:
                                    await self._start_or_claim_task(task)
                            else:
                                await self._start_or_claim_task(task)
                                
        except Exception as err:
            self.logger.error("self.do_tasks raised an error:", err)
            await asyncio.sleep(1)
    
    async def play_game(self) -> None | int:
        try:
            while self.running_allowed:
                response = await self.webclient.post("https://game-domain.blum.codes/api/v2/game/play")
                await self._validate_token(response, "play_game")
                if response.status == 200:
                    game_id = response.json.get("gameId", None)
                    click_count = random.randint(*self.drop_game_points)
                    
                    json_data = {
                        "gameId": game_id,
                        "points": click_count
                    }
                    
                    sleep_time = 30 if click_count < 160 else (30 + (click_count - 160)//7*4)
                    await wait_until(self, sleep_time, "Playing game")
                    
                    response = await self.webclient.post("https://game-domain.blum.codes/api/v2/game/claim", json=json_data)
                    if response.status == 200:
                        return click_count if response.text == "OK" else None
                        
        except Exception as err:
            self.logger.error("self.play_game raised an error:", err)
            await asyncio.sleep(1)
    
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            pts=format_number(self.points_balance), 
            tickets=format_number(self.play_passes),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            played=format_number(self.played),
            played_session=format_number(self.played_session),
            sleep_time=sleep_time
        )
    
    async def earned_add(self, value: int) -> None:
        self.earned += value
        self.earned_session += value
        self.cache.set("earned_session", self.earned_session)
        await self.db.update("earned", self.earned)
    
    async def run(self):
        my_tribe = await self.get_tribe()
        if not my_tribe:
            leaderboard = await self.get_tribe_leaderboard()
            tribe = leaderboard[0]
            await self.join_tribe(tribe["id"])
            self.logger.success("Joined&blue", tribe["title"], "&rtribe")
        
        while self.running_allowed:
            try:
                self.refresh_config()
                
                await self.balance()
                self.logger.info("Points:&green", self.points_balance, "&r| PlayPasses:&bright&magenta", self.play_passes)
                self.update_info_panel()
                    
                self.logger.background("Checking daily...")
                claimed_daily = await self.claim_daily()
                if claimed_daily:
                    old_bal = self.points_balance
                    await self.balance()
                    earned = int(self.points_balance - old_bal)
                    await self.earned_add(earned)
                    
                    self.logger.success("Claimed daily reward")
                    self.update_info_panel()
                
                self.logger.background("Getting refferals...")
                refferal_info = await self.get_refferals()
                if refferal_info and refferal_info.get("canClaim"):
                    ref_reward_claimed = await self.claim_referral()
                    if ref_reward_claimed:
                        earned = int(float(refferal_info.get("amountForClaim")))
                        await self.earned_add(earned)
                        
                        self.logger.success("Claimed", earned, "from refferal reward")
                        self.update_info_panel()
                
                self.logger.background("Tryng to claim farming...")
                remain_time = await self.remain_time()
                if remain_time == 0:
                    await self.claim_farm()
                    remain_time = None
                    
                    old_bal = self.points_balance
                    await self.balance()
                    earned = int(self.points_balance - old_bal)
                    await self.earned_add(earned)
                    
                    self.logger.success("Claimed&bright", earned, "&rfrom farming")
                    self.update_info_panel()
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                self.logger.background("Trying to start farming...")
                if remain_time is None:
                    await self.start_farm()
                    self.logger.info("Started farming")
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                self.logger.background("Checking tasks...")
                await self.do_tasks()
                self.update_info_panel()
                await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.logger.background("Checking game...")
                if self.spend_play_passes and self.play_passes > 0:
                    for _ in range(self.play_passes):
                        if not self.running_allowed:
                            break
                        
                        self.logger.background("Playing drop game...")
                        earned = await self.play_game()
                        if earned:
                            self.play_passes -= 1
                            await self.earned_add(earned)
                            self.points_balance += earned
                            self.played += 1
                            self.played_session += 1
                            self.cache.set("played_session", self.played_session)
                            await self.db.update("played", self.played)
                            
                            self.logger.success("Played game and got:&blue", earned, "&rpoints")
                            self.update_info_panel()
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                remain_time = await self.remain_time()
                await wait_until(self, remain_time)
            except Exception as err:
                self.logger.error("Unexpected error raised:", err)
                await asyncio.sleep(1)
        
async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module