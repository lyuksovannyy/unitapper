from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache
from aiohttp import ClientConnectionError
import random
import asyncio
from urllib.parse import quote, unquote
from datetime import timedelta, datetime

# TODO
# claim refferal rewards

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.config = config(self.name)
        self.logger = logger(self.name, self.session.name, user_tab=user_tab)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.user_data = None
        self.json_auth = {"token": None}
        self.sleep_box = timedelta(seconds=random.randint(*self.time_between_receiving_boxes))
        self.next_pool_reward_claim_time = datetime.now() # every 5 minutes
        
        self.drops_amount = 0
        self.m_boxes = 0
        self.mined_all = 0
        self.mined = 0
        self.mined_session = self.cache.get("mined_session", 0)
        
        self.info_placeholders = "Drops: {pts} | Mystery boxes: {boxes}\nMined: {mined_all} | Mined blocks with script: {mined} | Mined this session: {mined_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "0-from-5186710")
        self.allow_boost_pool: bool = self.config.get("allow_boost_pool", True)
        self.join_pool_id: int = self.config.get("join_pool_id", 542) # Notcoin pool
        self.minimum_invest_amount: int = self.config.get("minimum_invest_amount", 1000)
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.time_between_receiving_boxes: list = self.config.get("time_between_receiving_boxes", [3600, 7200])
        self.config.save()
        
    async def init(self):
        self.mined = int(await self.db.get("mined", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        
        # better to auth every time io sync data (user_data is availabe only upon auth)
        self.telegram_web_data = await self.session.request_web_view_data("cubesonthewater_bot", self.refferal_code, "https://www.thecubes.xyz/")
        self.user_tab.add_text_label(2, "[Open in web](%s)" % self.telegram_web_data.url)
        logged = None
        while logged is None:
            logged = await self.get_user()
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def get_user(self) -> dict:
        try:
            ref_parts = self.refferal_code.split("-from-")
            response = await self.webclient.post(url='https://server.questioncube.xyz/auth', json={'initData': quote(str(self.telegram_web_data)), "newRefData": {"ref": int(ref_parts[1]), "refPoolId": int(ref_parts[0])}})
            self.user_data = response.json
            self.json_auth = {"token": self.user_data.get("token")}
            return self.user_data
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.get_user raised an error:", error)
            return None
                    
    async def get_tg_x(self) -> bool:
        try:
            json = self.json_auth.copy()
            
            json["type"] = "telegram"
            response = await self.webclient.post(url='https://server.questioncube.xyz/auth/trustmebro', json=json)
            tg = response.json["ok"]
                    
            json["type"] = "twitter"
            response = await self.webclient.post(url='https://server.questioncube.xyz/auth/trustmebro', json=json)
            x = response.json["ok"]

            return tg or x
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.get_tg_x raised an error:", error)
            return None

    async def join_to_pool(self, pool_id: int) -> dict:
        try:
            response = await self.webclient.post(url='https://server.questioncube.xyz/pools/' + str(pool_id) + '/join', json=self.json_auth)
            return response.json
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.join_to_pool raised an error:", error)
            await asyncio.sleep(1)

    async def mine(self) -> dict | str | None:
        try:
            response = await self.webclient.post(url='https://server.questioncube.xyz/game/mined', json=self.json_auth)
            if response.status == 200:
                return response.json
            else:
                if response.text == '???????????????': # must mine abit slower
                    return None
                elif response.text == '? banned ?':
                    return 'energy recovery'
                elif response.text == 'Not enough energy':
                    return 'not enough'
                elif response.status == 400:
                    self.logger.error("self.mine bad request ? i guess we're fucked...")
                    #await asyncio.sleep(1*60*60)
                    return "broken"

        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.mine raised an error:", error)
            await asyncio.sleep(1)

    async def boost_pool(self, amount: int) -> dict:
        try:
            json = self.json_auth.copy()
            json.update({"amount": amount})
            response = await self.webclient.post(url='https://server.questioncube.xyz/pools/boost', json=json)
            if response.status == 200:
                return response.json
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.boost_pool raised an error:", error)
            await asyncio.sleep(1)
    async def claim_pool_reward(self) -> bool:
        try:
            if self.next_pool_reward_claim_time > datetime.now():
                return
            
            response = await self.webclient.post(url='https://server.questioncube.xyz/pools/claim', json=self.json_auth)
            if response.status == 200:
                self.next_pool_reward_claim_time = datetime.now() + timedelta(minutes=5)
                return response.json != {}
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.claim_pool_reward raised an error:", error)
            await asyncio.sleep(1)

    async def claim_boxes(self) -> int:
        try:
            response = await self.webclient.post(url='https://server.questioncube.xyz/pools/claim', json=self.json_auth)
            return response.json.get('boxesAmount', None)
                    
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.claim_boxes raised an error:", error)
            return None

    async def onboarding(self) -> bool:
        '''Complete tutorial(or whatever)
        '''
        try:
            response = await self.webclient.post(url='https://server.questioncube.xyz/game/onboarding', json=self.json_auth)
            return response.json.get('ok', False)
                
        except ClientConnectionError:
            await asyncio.sleep(1)

        except Exception as error:
            self.logger.error("self.claim_boxes raised an error:", error)
            return None

    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            pts=format_number(self.drops_amount),
            boxes=format_number(self.m_boxes),
            mined_all=format_number(self.mined_all),
            mined=format_number(self.mined),
            mined_session=format_number(self.mined_session),
            sleep_time=sleep_time
        )
        
    async def run(self):
        if not self.user_data.get("onboarding_done"):
            await self.onboarding()
            
        self.logger.info("Drops:&cyan", self.user_data.get("drops_amount", "?"), "&r| Mined:&blue", self.user_data.get("mined_count", "?"), "&rblocks |&magenta", self.user_data.get("drops_amount", "boxes_amount"), "&rmystery boxes")
        if self.user_data.get('pool_id') != str(self.join_pool_id):
            await self.join_to_pool(self.join_pool_id)
            self.logger.success("Joined to pool with id:&blue", self.join_pool_id)

        self.logger.background("Trying to complete one-time tasks...")
        status = await self.get_tg_x()
        if status:
            self.logger.success("Claimed telegram and twitter rewards")
        last_claim_time = datetime.now()

        while self.running_allowed:
            try:
                self.refresh_config()
                mine_data = await self.mine()
                if mine_data == "broken":
                    self.info_label.object = "Mining on this account is broken..."
                    break
                
                self.update_info_panel()
                    
                if mine_data == 'energy recovery':
                    await self.get_user()
                    self.drops_amount = int(self.user_data.get("drops_amount"))
                    sleep_time = timedelta(seconds=1000 - int(self.user_data.get('energy')))
                    self.logger.info("Recovering energy, sleeping:", str(sleep_time).split(".")[0])
                    date_now = datetime.now()
                    sleep_until = sleep_time + date_now
                    while self.running_allowed and date_now < sleep_until:
                        date_now = datetime.now()
                        
                        self.update_info_panel("Sleeping: " + str(sleep_until - date_now).split(".")[0])
                        
                        await asyncio.sleep(1)
                        
                    self.drops_amount = self.user_data.get("drops_amount", 0)
                    self.m_boxes = self.user_data.get("boxes_amount", 0)
                    self.mined_all = self.user_data.get("mined_count", 0)
                    self.logger.info("Drops:&cyan", self.drops_amount, "&r| Mined:&blue", self.mined_all, "&rblocks |&magenta", self.m_boxes, "&rmystery boxes")
                    continue

                elif mine_data == 'not enough':
                    self.update_info_panel("Small pause...")
                    #self.logger.background("Not enough energy, sleeping: 15 seconds")
                    await asyncio.sleep(15)
                    continue

                elif mine_data:
                    self.drops_amount = int(mine_data.get("drops_amount"))
                    self.mined += 1
                    self.mined_session += 1
                    self.cache.set("mined_session", self.mined_session)
                    await self.db.update("mined", self.mined)
                    
                    self.update_info_panel("Mining...")
                
                    if (len(mine_data.get('mystery_ids')) > 0 and int(mine_data.get('mystery_ids')[0]) == int(mine_data.get('mined_count'))):
                        self.logger.info("Mined &magentamystery box&r(" + mine_data.get("boxes_amount") + ") |", "Drops:&cyan", self.drops_amount)

                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                else:
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    continue
                    
                #self.logger.background("Checking if can claim mystery boxes...")
                if (datetime.now() - last_claim_time) >= self.sleep_box:
                    self.sleep_box = timedelta(seconds=random.randint(*self.time_between_receiving_boxes))
                    boxes_before_claim = int(mine_data.get('boxes_amount'))
                    boxes_after_claim = await self.claim_boxes()
                    if boxes_after_claim:
                        self.logger.background("Received&magenta", int(boxes_after_claim) - boxes_before_claim, "&rmystery boxes")
                        
                    last_claim_time = datetime.now()
                    await asyncio.sleep(random.randint(*self.mini_sleep))

                #self.logger.background("Checking if can boost pool...")
                if self.allow_boost_pool and int(self.drops_amount) > int(self.minimum_invest_amount):
                    boost_json = await self.boost_pool(self.drops_amount)

                    if boost_json:
                        self.logger.success("Pool boosted, invested:&cyan", self.drops_amount, "&greendrops")
                        
                #self.logger.background("Checking if can claim pool reward...")
                pool_reward = await self.claim_pool_reward()
                if pool_reward:
                    self.logger.success("Claimed pool reward")
                        
            except Exception as error:
                self.logger.error("Unexpected error occured:", error)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module