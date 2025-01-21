from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache
import asyncio
import random
from datetime import datetime, timedelta

# TODO
# Try to fix tap issue

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bgcyan&white", user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.json_auth = {
            "authData": "?",
            "data": {},
            "devAuthData": 0,
            "platform": "android"
        }
        self.game_config = None
        self.user_cards = {}
        self.cryptos = {}
        self.tapping_unavailable_until = datetime.now()
        
        self.domain = "https://cexp.cex.io/"
        self.app_version = "0.16.0"
        
        self.balance = 0.0
        self.compl_tasks = 0
        self.compl_tasks_session = self.cache.get("compl_tasks_session", 0)
        self.upgrades = 0
        self.upgrades_session = self.cache.get("upgrades_session", 0)
        
        self.info_placeholders = "Balance: {pts} | {cryptos}\nUpgraded with script: {upgrades} | Upgraded this session: {upgrades_session}\nCompleted tasks with script: {compl_tasks} | Completed tasks this session: {compl_tasks_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "1723996298023353")
        self.min_convert_value: float = self.config.get("min_convert_value", 1.0)
        self.max_upgrade_lvl: float = self.config.get("max_upgrade_lvl", 99)
        self.taps_per_sec: list = self.config.get("taps_per_second", [3, 5])
        self.mini_sleep: list = self.config.get("taps_per_second", [1, 5])
        self.config.save()
    
    async def init(self):
        self.upgrades = int(await self.db.get("upgrades", 0))
        self.compl_tasks = int(await self.db.get("compl_tasks", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        
        self.telegram_web_data = await self.session.request_web_view_data("cexio_tap_bot", self.refferal_code, "https://cexp.cex.io/")
        self.user_tab.add_text_label(2, "[Open in web](%s)" % self.telegram_web_data.url)
        
        self.webclient._headers["x-request-userhash"] = self.telegram_web_data.web_data["hash"]
        self.webclient._headers["x-appl-version"] = self.app_version
        self.webclient._headers["origin"] = self.domain
        self.webclient._headers["referer"] = self.domain
        
        self.json_auth["authData"] = str(self.telegram_web_data)
        self.json_auth["devAuthData"] = int(self.session.account_data.id)
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def get_user(self) -> dict:
        response = await self.webclient.post(self.domain + "api/v2/getUserInfo", json=self.json_auth)
        if response.status == 200:
            return response.json.get("data")
        
    async def get_game_cfg(self) -> dict:
        response = await self.webclient.post(self.domain + "api/v2/getGameConfig", json=self.json_auth)
        if response.status == 200:
            return response.json
    
    async def get_user_cards(self) -> dict:
        response = await self.webclient.post(self.domain + "api/v2/getUserCards", json=self.json_auth)
        if response.status == 200:
            return response.json.get("cards")
    
    async def get_tasks(self) -> dict:
        response = await self.webclient.post(self.domain + "api/v2/getUserTasks", json=self.json_auth)
        if response.status == 200:
            return response.json.get("tasks")
    async def start_task(self, task_id: str) -> dict:
        json = self.json_auth.copy()
        json["data"] = {
            "taskId": task_id
        }
        response = await self.webclient.post(self.domain + "api/v2/getUserTasks", json=json)
        if response.status == 200:
            return response.json.get("data")
    async def check_task(self, task_id: str) -> dict:
        json = self.json_auth.copy()
        json["data"] = {
            "taskId": task_id
        }
        response = await self.webclient.post(self.domain + "api/v2/checkTask", json=json)
        if response.status == 200:
            return response.json.get("data")
    async def claim_task(self, task_id: str) -> dict:
        json = self.json_auth.copy()
        json["data"] = {
            "taskId": task_id
        }
        response = await self.webclient.post(self.domain + "api/v2/claimTask", json=json)
        if response.status == 200:
            data: dict = response.json.get("data", {})
            if data:
                self.balance = float(data.get("balance"))
                return data.get("task")
    
    async def tap(self, taps: int = 1) -> bool:
        if self.tapping_unavailable_until > datetime.now():
            return False
        
        json = self.json_auth.copy()
        json["data"] = {
            "tapsEnergy": "1000", # :)
            "tapsToClaim": str(taps),
            "tapsTs": int(datetime.now().timestamp() * 1000)
        }
        response = await self.webclient.post(self.domain + "api/v2/claimMultiTaps", json=json)
        if response.status == 200:
            balance = response.json.get("data", {}).get("balance_USD")
            if balance:
                self.balance = float(balance)
            return response.json.get("status") == "ok"
        elif "too slow" in response.text:
            self.tapping_unavailable_until = (datetime.now() + timedelta(minutes=10))
        #elif "from future" in response.text:
        #    self.time_offset -= 10000
            
    async def claim_crypto(self) -> bool:
        response = await self.webclient.post(self.domain + "api/v2/claimCrypto", json=self.json_auth)
        if response.is_json:
            cryptos = response.json.get("data")
            if cryptos:
                self.cryptos = cryptos
            return response.json.get("status") == "ok"
    
    async def get_convert_price(self) -> float:
        response = await self.webclient.post(self.domain + "api/v2/getConvertData", json=self.json_auth)
        if response.status == 200:
            return float(response.json.get("convertData").get("lastPrices")[-1])
        
    async def upgrade(self, category_id: str, cost: int, ccy: str, effect: int, effectccy: str, level: int, upgrade_id: str) -> bool:
        json = self.json_auth.copy()

        json["data"] = {
            "categoryId": category_id,
            "ccy": ccy,
            "cost": cost,
            "effect": effect,
            "effectCcy": effectccy,
            "nextLevel": level,
            "upgradeId": upgrade_id
        }
        response = await self.webclient.post(self.domain + "api/v2/buyUpgrade", json=json)
        if response.status == 200:
            return response.json.get("status") == "ok"
        
    async def convert(self, fromCcy: str, toCcy: str, amount: int) -> bool:
        json = self.json_auth.copy()
        json["data"] = {
            "fromAmount": str(amount),
            "fromCcy": fromCcy.upper(),
            "price": str((await self.get_convert_price())),
            "toCcy": toCcy.upper()
        }
        response = await self.webclient.post(self.domain + "api/v2/convert", json=json)
        if response.status == 200:
            data = response.json.get("convert")
            bal = data.get("balance_USD")
            if bal:
                self.balance = float(bal)
            return response.json.get("status") == "ok"
    
    async def pass_onboarding(self) -> bool:
        response = await self.webclient.post(self.domain + "api/v2/passOnboarding", json=self.json_auth)
        if response.status == 200:
            return response.json.get("status") == "ok"
    
    def get_true_crypto_value(self, crypto_name: str) -> float:
        crypto = self.cryptos.get(crypto_name, {})
        return float(crypto.get("balance_" + crypto_name, 0) / int("1" + "0"*int(crypto.get("precision_" + crypto_name, 1))))
    
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        formatted_cryptos = []
        for crypto, data in self.cryptos.items():
            formatted_cryptos.append("{}: {}".format(crypto, format_number(self.get_true_crypto_value(crypto))))
            
        self.info_label.object = self.info_placeholders.format(
            pts=format_number(self.balance),
            cryptos=" | ".join(formatted_cryptos),
            upgrades=self.upgrades,
            upgrades_session=self.upgrades_session,
            compl_tasks=self.compl_tasks,
            compl_tasks_session=self.compl_tasks_session,
            sleep_time=sleep_time
        )
        
    async def run(self):
        while self.running_allowed:
            try:
                user_data = await self.get_user()
                if not user_data:
                    self.logger.error("No user data found")
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    continue
                
                if not self.game_config:
                    self.logger.error("No game config found")
                    self.game_config = await self.get_game_cfg()
                    await asyncio.sleep(random.randint(*self.mini_sleep) * 30)
                    continue
                
                await self.claim_crypto()
                
                self.balance = float(user_data.get("balance_USD"))
                
                if not user_data.get("onboardingPassed"):
                    state = await self.pass_onboarding()
                    if state:
                        self.logger.success("Passed onboarding")
                
                self.logger.info("Balance:&yellow", self.balance, "| BTC:&yellow", self.get_true_crypto_value("BTC"))
                self.update_info_panel()
                
                # convert
                self.logger.background("Trying to convert crypto...")
                for crypto, data in self.cryptos.items():
                    bal = self.get_true_crypto_value(crypto)
                    if self.min_convert_value < bal:
                        state = await self.convert(crypto, "USD", bal)
                        if state:
                            self.logger.success("Converted&yellow", crypto, "&rto&yellow USD")

                        await asyncio.sleep(random.randint(*self.mini_sleep))
                        
                # tasks
                self.logger.background("Checking tasks...")
                tasks = (await self.get_tasks()) or {}
                for task_id, data in tasks.items():
                    reward: int = data.get("reward")
                    state: str = data.get("state")
                    type: str = data.get("type")
                    if state in ["Claimed", "Locked"]:
                        continue

                    if state == "NONE":
                        status = await self.start_task(task_id)
                        if status:
                            state = status["state"]
                            #self.logger.background("Started:&white", task_id)
                            
                            await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                    if type in ["refferal"]:
                        continue
                    
                    if state == "ReadyToCheck":
                        status = await self.check_task(task_id)
                        if status:
                            state = status["state"]
                            #self.logger.background("Checking:&white", task_id)
                            
                            await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                    if state == "ReadyToClaim":
                        status = await self.claim_task(task_id)
                        if status:
                            state = status["state"]
                            
                            await asyncio.sleep(random.randint(*self.mini_sleep))

                    if state == "Claimed":
                        self.compl_tasks += 1
                        self.compl_tasks_session += 1
                        self.cache.set("compl_tasks_session", self.compl_tasks_session)
                        await self.db.update("compl_tasks", self.compl_tasks)
                        self.update_info_panel()
                        self.logger.success("Completed task:&white", task_id, "&rreward:&yellow", reward, "&rBTC")
                
                # upgrades
                self.logger.background("Checking upgrades...")
                something_upgraded = True
                while something_upgraded:
                    something_upgraded = False
                    self.user_cards = (await self.get_user_cards()) or {}
                    for category in self.game_config.get("upgradeCardsConfig", []):
                        category_id = category.get("categoryId")
                        category_name = category.get("categoryName")
                        for upgrade in category.get("upgrades", []):
                            upgrade_id = upgrade.get("upgradeId")
                            upgrade_name = upgrade.get("upgradeName")
                            
                            lvl = self.user_cards.get(upgrade_id, {}).get("lvl", 0)
                            price: list = upgrade.get("levels", [])
                            try:
                                price = price[lvl]
                            except:
                                price = []
                            
                            dependency = upgrade.get("dependency", {})
                            if dependency != {}:
                                required_upgrade = dependency.get("upgradeId", "")
                                required_lvl = dependency.get("level")
                                current_lvl = self.user_cards.get(required_upgrade, {}).get("lvl", 0)
                                if current_lvl < required_lvl:
                                    continue
                            
                            if len(price) != 0 and price[0] <= self.balance and self.max_upgrade_lvl >= lvl+1:
                                if len(price) == 5:
                                    del price[4]
                                    
                                status = await self.upgrade(category_id, *price, lvl+1, upgrade_id)
                                if status:
                                    self.balance -= price[0]
                                    something_upgraded = True
                                    
                                    self.upgrades += 1
                                    self.upgrades_session += 1
                                    self.cache.set("upgrades_session", self.upgrades_session)
                                    await self.db.update("upgrades", self.upgrades)
                                    self.update_info_panel()
                                    
                                    self.logger.success("Upgraded:&white", category_name, "-", upgrade_name if len(upgrade_name) < 15 else upgrade_name[:12] + "...", "&rto level ->&blue", lvl+1)
                                    
                                await asyncio.sleep(random.randint(*self.mini_sleep))
                            
                time_sleep = timedelta(minutes=60)
                tap_until = datetime.now() + time_sleep
                self.logger.background("Tapping for next:", str(time_sleep).split(".")[0])
                date_now = datetime.now()
                while self.running_allowed and date_now < tap_until:
                    date_now = datetime.now()
                    self.refresh_config()

                    await self.claim_crypto()
                    await self.tap(random.randint(*self.taps_per_sec))
                    
                    self.update_info_panel("Tapping: " + str(tap_until - date_now).split(".")[0])
                    
                    await asyncio.sleep(1)
                    
            except Exception as err:
                self.logger.error("Unexpected error occured:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module