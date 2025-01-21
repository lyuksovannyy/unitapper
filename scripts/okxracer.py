from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, cache, wait_until, format_number
import asyncio
import random
from datetime import datetime

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab) -> None:
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bgwhite&black", user_tab=user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        
        self._earned = 0
        self._earned_session = self.cache.get("earned_session", 0)
        self._predictions = 0
        self._good_predictions = 0
        
        self.info_placeholders = "Balance: {bal}\nEarned with script: {earned} | Earned this session: {earned_session}\nPrediction rate: {pred_rate}\n{activity}"
        self.info_label = self.user_tab.add_text_label(1)
        self.open_in = self.user_tab.add_text_label(2)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self) -> None:
        '''Update config data if changes were made'''
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "linkCode_134568692")
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.sleep_time: float = self.config.get("sleep_time", 1.2)
        self.config.save()
    
    async def init(self) -> None:
        '''Starts before the main code (in general used for auth-only things)'''
        self.webclient.user_agent = await get_user_agent(self.db)
        self._earned = int(await self.db.get("earned", 0))
        self._predictions = int(await self.db.get("predictions", 0))
        self._good_predictions = int(await self.db.get("good_predictions", 0))
        
        self.telegram_web_data = await self.session.request_web_view_data("OKX_official_bot", self.refferal_code, "OKX_Racer")
        self.open_in.object = "[Open in web](%s)" % self.telegram_web_data.url
        self.webclient._headers['X-Telegram-Init-Data'] = self.telegram_web_data.user_quoted_web_data
        
    async def start(self) -> None:
        '''Starts after initalizing all scripts'''
        await self.run()

    async def cancel(self) -> None:
        '''Function is needed only for soft end of the task\n'''
        self.running_allowed = False

    def update_info_panel(self, activity_text: str = "Active...") -> None:
        '''Web-panel related'''
        bad_predictions = self._predictions - self._good_predictions
        predictions_rate = "{}% ({}-{})".format(int(self._good_predictions / self._predictions * 100), self._good_predictions, bad_predictions) if self._good_predictions > 0 and bad_predictions > 0 else "-"
        self.info_label.object = self.info_placeholders.format(
            bal=format_number(self.balance),
            earned=format_number(self._earned),
            earned_session=format_number(self._earned_session),
            pred_rate=predictions_rate,
            activity=activity_text
        )
    
    async def earned(self, value: int) -> None:
        '''Save "earned" stat'''
        self._earned += value
        self._earned_session += value
        self.cache.set("earned_session", self._earned_session)
        await self.db.update("earned", self._earned)
    
    async def user_data(self) -> dict:
        response = await self.webclient.post(
            "https://www.okx.com/priapi/v1/affiliate/game/racer/info", 
            json={
                "extUserId": str(self.session.account_data.id),
                # "extUserName": self.session.account_data.first_name + ((" " + self.session.account_data.last_name) if self.session.account_data.last_name else ""),
                "linkCode": self.refferal_code[9:]
            }
        )
        return response.is_json and response.json.get("code") == 0 and response.json.get("data")
    
    async def get_tasks(self):
        response = await self.webclient.get("https://www.okx.com/priapi/v1/affiliate/game/racer/tasks")
        return response.json.get("data", [])
    
    async def do_task(self, id : int):
        response = await self.webclient.post(
            "https://www.okx.com/priapi/v1/affiliate/game/racer/task",
            json={
                "extUserId": self.session.account_data.id,
                "id": id,
            }
        )
        
        return response.json.get("code") == 0
    
    async def get_boosts(self):
        response = await self.webclient.get("https://www.okx.com/priapi/v1/affiliate/game/racer/boosts")
        return response.json.get("data", [])
    
    async def buy_boost(self, id: int):
        json_data = {
            "extUserId": self.session.account_data.id,
            'id': id,
        }

        response = await self.webclient.post(
            "https://www.okx.com/priapi/v1/affiliate/game/racer/boost",
            json=json_data,
        )
        
        return response.json.get("code") == 0
    
    # CUSTOM
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                
                self.logger.background("Getting user data...")
                user_data = await self.user_data()
                if not user_data:
                    self.logger.error("Failed to fetch user data")
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    continue
                
                self.balance = user_data["balancePoints"]
                self.logger.info("Balance:&blue", self.balance)
                self.update_info_panel()
                    
                self.logger.background("Getting user tasks...")
                user_tasks = await self.get_tasks()
                for task in user_tasks:
                    if task['state'] == 1 or not self.running_allowed:
                        continue
                    
                    is_done = await self.do_task(task["id"])
                    if is_done:
                        await self.earned(int(task["points"]))
                        self.logger.success("Task&cyan", task["context"]["name"], "&rfinished, claimed:&blue", task["points"], "&rpoints")
                        
                    self.update_info_panel()
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.logger.background("Getting user boosts...")
                user_boosts = [] #await self.get_boosts()
                for boost in user_boosts:
                    if boost.get('isLocked') or not self.running_allowed:
                        continue
                    
                    curStage = boost['curStage']
                    totalStage = boost['totalStage']
                    pointCost = boost['pointCost']
                    if curStage > totalStage or pointCost > self.balance:
                        continue
                
                    bought = await self.buy_boost(boost["id"])
                    if bought:
                        self.balance -= boost["context"].get("pointCost", 0)
                        self.logger.success("Bought boost&cyan", task["context"]["name"], "&rfor:&blue", boost["context"].get("pointCost", 0), "&rpoints")
                        
                    self.update_info_panel()
                    await asyncio.sleep(random.randint(*self.mini_sleep))

                self.logger.background("Making predictions (%s)..." % user_data["numChances"])
                for chance in range(user_data["numChances"]):
                    if not self.running_allowed:
                        break
                    
                    self._predictions += 1
                    await self.db.update("predictions", self._predictions)
                        
                    response = await self.webclient.post(
                        'https://www.okx.com/priapi/v1/affiliate/game/racer/assess',
                        json={ "predict": random.randint(0, 1) }
                    )
                    is_won = response.is_json and response.json.get("data", {}).get("won")
                    claimed = response.is_json and response.json.get("data", {}).get("basePoint")
                    
                    if is_won:
                        self._good_predictions += 1
                        await self.db.update("good_predictions", self._good_predictions)
                        self.logger.success("Successfully predicted rate and earned&blue", claimed, "&rpoints")
                        await self.earned(int(claimed))
                    else:
                        self.logger.background("Predict failed")
                        
                    self.update_info_panel()
                    await asyncio.sleep(random.randint(5, 7))
                        
                await wait_until(self, self.sleep_time * 60 * 60)
            except Exception as err:
                self.logger.error("Unexpected error occurred:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module