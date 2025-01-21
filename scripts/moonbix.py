from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, cache, wait_until, format_number
import asyncio
import random
from datetime import datetime, timedelta

import base64
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab) -> None:
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bgyellow", user_tab=user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.resource_id = 2056
        self.telegram_web_data = None
        
        self.balance = 0
        self._expires_at = datetime.now()
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
        self.refferal_code: str = self.config.get("refferal_code", "ref_407777629")
        self.max_game_reward: int = self.config.get("max_game_reward", 200)
        self.sleep_hours: float = self.config.get("sleep_hours", 2.0)
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def init(self) -> None:
        '''Starts before the main code (in general used for auth-only things)'''
        self.webclient.user_agent = await get_user_agent(self.db)
        self._earned = int(await self.db.get("earned", 0))
        
        self.webclient._headers["Referer"] = "https://www.binance.com/en/game/tg/moon-bix?tgWebAppStartParam=" + self.refferal_code
        
        self.telegram_web_data = await self.session.request_web_view_data("Binance_Moonbix_bot", self.refferal_code, "start")
        self.open_in.object = "[Open in web](%s)" % self.telegram_web_data.url
        
        await self.access_token(False)
        
    async def start(self) -> None:
        '''Starts after initalizing all scripts'''
        await self.run()

    async def cancel(self) -> None:
        '''Function is needed only for soft end of the task\n'''
        self.running_allowed = False

    def update_info_panel(self, activity_text: str = "Active...") -> None:
        '''Web-panel related'''
        self.info_label.object = self.info_placeholders.format(
            earned=format_number(self._earned),
            earned_session=format_number(self._earned_session),
            bal=format_number(self.balance),
            activity=activity_text
        )
    
    async def earned(self, value: int) -> None:
        '''Save "earned" stat'''
        self._earned += value
        self._earned_session += value
        self.cache.set("earned_session", self._earned_session)
        await self.db.update("earned", self._earned)
    
    async def access_token(self, revive_session: bool = True) -> None:
        if datetime.now() < self._expires_at:
            return
        
        if revive_session:
            await self.session.revive(self.name)
            self.telegram_web_data = await self.session.request_web_view_data("Binance_Moonbix_bot", self.refferal_code, "start")
            self.open_in.object = "[Open in web](%s)" % self.telegram_web_data.url
        
        if "X-Growth-Token" in self.webclient._headers:
            del self.webclient._headers["X-Growth-Token"]
        
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/third-party/access/accessToken",
            json={
                "queryString": self.telegram_web_data.user_quoted_web_data,
                "socialType": "telegram"
            }
        )
        if response.status == 200:
            data = response.json.get("data")
            self._token = data["accessToken"]
            self._ref_token = data["refreshToken"]
            self._expires_at = datetime.now() + timedelta(seconds=data["expiredTime"])
            
            self.webclient._headers["X-Growth-Token"] = self._token
    
        if revive_session:
            await self.session.revive_end(self.name)
    
    async def tasks(self) -> list[dict]:
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/task/list",
            json={
                "resourceId": self.resource_id
            }
        )
        return response.is_json and response.json.get("data", {}).get("data") or []
        
    async def complete_task(self, task_id: int) -> bool:
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/task/complete",
            json={
                "referralCode": "null",
                "resourceIdList": [task_id]
            }
        )
        return response.is_json and response.json.get("success")
    
    async def setup_account(self) -> None:
        payload = {
            "agentId": str(self.refferal_code.removeprefix("ref_")),
            "resourceId": self.resource_id
        }
        
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/referral",
            json=payload
        )
        if not response.json.get("success"):
            return
        
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/game/participated",
            json=payload
        )
        if not response.json.get("success"):
            return
        
        self.logger.success("Account was setted up")
        await self.complete_task(2057)
        
    async def user_data(self) -> dict:
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/user/user-info",
            json={"resourceId": self.resource_id}
        )
        if response.status == 200:
            data = response.json.get("data")
            
            if not data.get("participated"):
                await self.setup_account()
                return await self.user_data()
            
            return data
        
        return {}
        
    async def start_game(self) -> tuple[str, list] | None:
        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/game/start",
            json={"resourceId": self.resource_id}
        )
        data = response.is_json and response.json.get("data") or {}
        error = response.is_json and (response.json.get("message") or response.json.get("data", {}).get("needCaptchaVerification") and "Captcha") or None
        return data.get("gameTag"), data.get("cryptoMinerConfig", {}).get("itemSettingList"), error
        
    def encrypt_game_data(self, text: str, key: str) -> str:
        iv = get_random_bytes(12)
        iv_base64 = base64.b64encode(iv).decode("utf-8")
        cipher = AES.new(key, AES.MODE_CBC, iv_base64[:16].encode("utf-8"))

        def pad(s):
            block_size = AES.block_size
            return s + (block_size - len(s) % block_size) * chr(
                block_size - len(s) % block_size
            )

        padded_text = pad(text).encode("utf-8")
        encrypted = cipher.encrypt(padded_text)
        encrypted_base64 = base64.b64encode(encrypted).decode("utf-8")

        return iv_base64 + encrypted_base64
        
    async def complete_game(self, start_time: datetime, play_time: int, game_tag: str, item_settings: list) -> int | None:
        start_time = int(start_time.timestamp() * 1000)
        current_time = start_time
        end_time = start_time + (play_time * 1000)

        score = 100
        game_events = []

        while current_time < end_time: # pasted entirely 🤑🤑🤑
            time_increment = random.randint(1500, 2500)
            current_time += time_increment

            if current_time >= end_time:
                break

            hook_pos_x = round(random.uniform(75, 275), 3)
            hook_pos_y = round(random.uniform(199, 251), 3)
            hook_shot_angle = round(random.uniform(-1, 1), 3)
            hook_hit_x = round(random.uniform(100, 400), 3)
            hook_hit_y = round(random.uniform(250, 700), 3)

            item_type, item_size, points = 0, 0, 0
            random_value = random.random()

            if random_value < 0.6:
                reward_items = [item for item in item_settings if item["type"] == "REWARD"]
                selected_reward = random.choice(reward_items)
                item_type = 1
                item_size = selected_reward["size"]
                points = min(selected_reward["rewardValueList"][0], 10)
                score = min(score + points, self.max_game_reward)
            elif random_value < 0.8:
                trap_items = [item for item in item_settings if item["type"] == "TRAP"]
                selected_trap = random.choice(trap_items)
                item_type = 1
                item_size = selected_trap["size"]
                points = min(abs(selected_trap["rewardValueList"][0]), 20)
                score = max(100, score - points)
            else:
                bonus_item = next(
                    (item for item in item_settings if item["type"] == "BONUS"), None
                )
                if bonus_item:
                    item_type = 2
                    item_size = bonus_item["size"]
                    points = min(bonus_item["rewardValueList"][0], 15)
                    score = min(score + points, self.max_game_reward)

            game_events.append(f"{current_time}|{hook_pos_x}|{hook_pos_y}|{hook_shot_angle}|{hook_hit_x}|{hook_hit_y}|{item_type}|{item_size}|{points}")

        payload = ";".join(game_events)
        payload = self.encrypt_game_data(payload, game_tag.encode("utf-8"))

        response = await self.webclient.post(
            "https://www.binance.com/bapi/growth/v1/friendly/growth-paas/mini-app-activity/third-party/game/complete",
            json={
                "log": score,
                "payload": payload,
                "resourceId": self.resource_id
            }
        )
        return score if response.is_json and response.json.get("success") else None
        
    # CUSTOM
    async def run(self):
        while self.running_allowed:
            try:
                await self.access_token()
                self.refresh_config()
                
                user_data = await self.user_data()
                if not user_data:
                    self.logger.background("Unable to get user_data")
                    await asyncio.sleep(*self.mini_sleep)
                    continue
                
                meta_info: dict = user_data.get("metaInfo", {})
                remaining_attempts = meta_info.get("totalAttempts", 0) - meta_info.get("consumedAttempts", 0)
                self.balance = meta_info.get("totalGrade", 0)
                
                self.logger.info("Balance:&yellow", self.balance, "| Remaining attempts:&cyan", remaining_attempts)
                self.update_info_panel()
                
                self.logger.background("Checking tasks...")
                for tasks in (await self.tasks()):
                    for task in tasks.get("taskList").get("data"):
                        if task.get("status") == "COMPLETED" or task.get("type") == "THIRD_PARTY_BIND":
                            continue
                        
                        reward = task.get("rewardList", [{}])[0].get("amount", 0)
                        
                        completed = await self.complete_task(task.get("resourceId"))
                        if completed and reward > 0:
                            await self.earned(reward)
                            self.logger.success("Completed task:&white", task.get("code"), "&rfor:&yellow", reward)
                            
                        self.update_info_panel()
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.logger.background("Checking game...")
                for i in range(remaining_attempts):
                    start_time = datetime.now()
                    game_tag, items, error = await self.start_game()
                    
                    if error:
                        self.logger.error(error)
                        break
                    
                    await wait_until(self, 45, "Playing " + str(i+1) + " game")
                    reward = await self.complete_game(start_time, 45, game_tag, items)
                    if reward:
                        await self.earned(reward)
                        self.logger.success("Got:&yellow", reward, "&rfrom game")
                    
                    await asyncio.sleep(*self.mini_sleep)
                
                await wait_until(self, 3600*self.sleep_hours)
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module