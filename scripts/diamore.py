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
        
        self.config = config(self.name)
        self.logger = logger(self.name, self.session.name, "&bright&bgblue", user_tab)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        self.user_data = {}
        self.user_quests = []
        
        self.diamonds = 0
        self.pinkies = 0
        self.earned = 0
        self.earned_session = self.cache.get("earned_session", 0)
        
        self.info_placeholders = "Diamonds: {diamonds} | Pinkies: {pinkies}\nEarned with script: {earned} | Earned this session: {earned_session}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
    
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "407777629")
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.click_count: list = self.config.get("click_count", [1000, 1200]) # clicks per 10 seconds
        self.upgrade_max_levels: dict = self.config.get("upgrade_max_level", {
            "tapPower": 0,
            "tapDuration": 0,
            "tapCoolDown": 0
        })
        self.config.save()
        
    async def init(self):
        url = await self.db.get("app_url")
        self.earned = float(await self.db.get("earned", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        self.webclient.authorization = await self.db.get("auth")
        
        while True:
            if not self.webclient.authorization or not url:
                self.telegram_web_data = await self.session.request_web_view_data("DiamoreCryptoBot", self.refferal_code)
                url = self.telegram_web_data.url
                await self.db.update("app_url", url)
                self.webclient.authorization = "Token " + self.telegram_web_data.full_quoted_raw_web_data
                await self.db.update("auth", self.webclient.authorization)
                response = await self.webclient.post("https://api.diamore.co/user/visit")
                break
            
            response = await self.webclient.post("https://api.diamore.co/user/visit")
            if response.status == 403 or "Invalid Telegram data" in response.text or "Missing authorization header" in response.text:
                self.webclient.authorization = None
                continue
            
            break
        
        self.user_tab.add_text_label(2, "[Open in web](%s)" % url)
        
    async def start(self):
        await self.run()
        
    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    async def get_user(self) -> dict:
        try:
            response = await self.webclient.get("https://api.diamore.co/user")
            if response.status == 200:
                return response.json
            
        except Exception as error:
            self.logger.error("self.get_user raised an error:", error)
            await asyncio.sleep(1)
            return None
    async def claim_daily(self) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/daily/claim')
            return response.json.get("message") == "Daily reward claimed"
        
        except Exception as error:
            self.logger.error("self.claim_daily raised an error:", error)
            return None
    async def claim_invition(self) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/referral/claim/invitation')
            return response.json.get("message") == "Invitation reward claimed"
        
        except Exception as error:
            self.logger.error("self.claim_invition raised an error:", error)
            return None

    async def get_upgrades(self) -> dict:
        try:
            response = await self.webclient.get(url='https://api.diamore.co/upgrades')
            return response.json

        except Exception as error:
            self.logger.error("self.get_upgrades raised an error:", error)
            await asyncio.sleep(1)
            return None
    async def buy_upgrade(self, upgrade_name: str) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/upgrades/buy', json={"type": upgrade_name})
            return response.json.get("message") == "Your level has been raised!"

        except Exception as error:
            self.logger.error("self.buy_upgrade raised an error:", error)
            await asyncio.sleep(1)
            return None
        
    async def get_friends(self) -> int | int:
        '''Returns available_bonus, friends_total
        '''
        try:
            response = await self.webclient.get(url='https://api.diamore.co/referral/recruits/?page=1&limit=1')
            return response.json.get("totalAvailableBonuses", 0), response.json.get("total", 0)

        except Exception as error:
            self.logger.error("self.get_friends raised an error:", error)
            await asyncio.sleep(1)
            return None
    async def claim_friends_bonus(self) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/referral/claim')
            return response.json.get("message") == "Bonuses claimed"

        except Exception as error:
            self.logger.error("self.claim_friends_bonus raised an error:", error)
            await asyncio.sleep(1)
            return None

    async def get_quests(self) -> list:
        try:
            response = await self.webclient.get(url='https://api.diamore.co/quests')
            available_quests = []
            for quest in response.json:
                if quest.get('checkType') == 'timer':
                    completed = False
                    for _quest in self.user_quests:
                        if _quest.get("name") == quest.get("name") and _quest.get("status") == "completed":
                            completed = True
                            break

                    if not completed:
                        available_quests.append(quest)
                
            return available_quests

        except Exception as error:
            self.logger.error("self.get_quests raised an error:", error)
            return None
    async def finish_quest(self, quest_name: str) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/quests/finish', json={"questName": quest_name})
            return response.json.get('message') == 'Quest marked as finished'

        except Exception as error:
            self.logger.error("self.finish_quest raised an error:", error)
            await asyncio.sleep(1)

    async def available_ads(self) -> int:
        try:
            response = await self.webclient.get(url='https://api.diamore.co/ads')
            return response.json.get("available", 0)

        except Exception as error:
            self.logger.error("self.available_ads raised an error:", error)
            return None
    async def skip_time(self) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/ads/watch', json={"type": "adsgram"})
            counted = response.json.get("message") == "Ad bonus applied!"
            if counted:
                await asyncio.sleep(15)
            
            return counted

        except Exception as error:
            self.logger.error("self.skip_time raised an error:", error)
            await asyncio.sleep(1)
            return None
    async def harvest(self, clicks: int, duration: int, tap_power: float) -> int:
        try:
            calc_clicks = clicks * (duration / 10) * tap_power
            response = await self.webclient.post(url='https://api.diamore.co/taps/claim', json={"amount": str(calc_clicks)})
            if response.json.get('message') == 'Taps claimed':
                await asyncio.sleep(duration)
                return calc_clicks

        except Exception as error:
            self.logger.error("self.harvest raised an error:", error)
            await asyncio.sleep(1)
    def get_game_timer(self) -> int:
        limit_date: str = self.user_data.get("limitDate")
        limit_date: int = datetime.fromisoformat(limit_date.replace("Z", "+00:00")).timestamp() if limit_date else 0
        requested_at: int = datetime.fromisoformat(self.user_data.get("requestedAt").replace("Z", "+00:00")).timestamp()
        time = limit_date - requested_at
        return time if time > 0 else 0
        
    async def visit(self) -> bool:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/visit')
            return response.json.get("message") == "ok"
        except Exception as error:
            self.logger.error("self.visit raised an error:", error)
            await asyncio.sleep(1)
        
    async def apply_code(self, code: str) -> bool | str:
        try:
            response = await self.webclient.post(url='https://api.diamore.co/promo/apply-code', json={"code": code})
            return response.json.get("message") if response.status == 200 else False
        except Exception as error:
            self.logger.error("self.visit raised an error:", error)
            await asyncio.sleep(1)
        
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        self.info_label.object = self.info_placeholders.format(
            diamonds=format_number(self.diamonds),
            pinkies=format_number(self.pinkies),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            sleep_time=sleep_time
        )
        
    async def earned_add(self, value) -> None:
        self.earned += value
        self.earned_session += value
        self.cache.set("earned_session", self.earned_session)
        await self.db.update("earned", self.earned)
        
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                # user info
                self.user_data = await self.get_user()
                if self.user_data is None:
                    self.logger.error("Unable to get user_data...")
                    await asyncio.sleep(*self.mini_sleep)
                    continue
                
                await self.visit()
                #for code in ["undX6YMK3jP4s9vaDHbqgEtVcL2eypm8xAzZhU-blue", "undX6YMK3jP4s9vaDHbqgEtVcL2eypm8xAzZhU-pink"]:
                #    redeem = await self.apply_code(code)
                #    if redeem:
                #        self.logger.success(redeem)
                
                upgrades_info = await self.get_upgrades()
                upgrades_tapPower = float(upgrades_info["tapPower"][0]["value"])
                upgrades_tapDuration = int(upgrades_info["tapDuration"][0]["durationMil"]) / 1000
                
                self.user_quests = self.user_data.get("quests", [])
                
                self.diamonds = int(float(self.user_data["balance"]))
                self.pinkies = int(float(self.user_data["pinkBalance"]))
                self.logger.info("Diamonds:&blue", self.diamonds, "&r| Pinkies:&bright&magenta", self.pinkies)
                self.update_info_panel()

                await asyncio.sleep(random.randint(*self.mini_sleep))

                self.logger.background("Checking if have any invition reward...")
                inv_reward = int(self.user_data.get("invitationReward", 0))
                if inv_reward > 0:
                    await self.claim_invition()
                    
                    self.user_data = await self.get_user()
                    new_bal = int(float(self.user_data["balance"]))
                    earned = new_bal - self.diamonds
                    self.diamonds = new_bal
                    await self.earned_add(earned)
                    
                    self.logger.success("Claimed invition reward, earned:&blue", earned)
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.update_info_panel()
                    
                # daily
                #daily_bonus = int(self.user_data.get("dailyBonusAvailable", 1))
                #if daily_bonus > 0:
                self.logger.background("Checking daily reward...")
                daily_reward = await self.claim_daily()
                if daily_reward:
                    self.user_data = await self.get_user()
                    new_bal = int(float(self.user_data["balance"]))
                    earned = new_bal - self.diamonds
                    self.diamonds = new_bal
                    await self.earned_add(earned)
                    
                    self.logger.success("Claimed daily", "bonus", "from daily reward")

                self.update_info_panel()
                await asyncio.sleep(random.randint(*self.mini_sleep))

                # refferals
                self.logger.background("Checking refferal rewards...")
                refferal_bonus, refferal_count = await self.get_friends()
                if refferal_bonus > 1:
                    status = await self.claim_friends_bonus()
                    
                    self.diamonds += refferal_bonus
                    await self.earned_add(refferal_bonus)
                    
                    self.logger.success("Claimed:&blue", refferal_bonus, "&greendiamonds from&bright&green", refferal_count, "&r&greenfriends")

                self.update_info_panel()
                await asyncio.sleep(random.randint(*self.mini_sleep))
                
                # quests
                completed_quests = 0
                not_completed_quests = 0
                
                self.logger.background("Checking tasks...")
                quests = await self.get_quests()
                for quest in quests:
                    status = await self.finish_quest(quest["name"])
                    if status:
                        completed_quests += 1
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                    else:
                        not_completed_quests += 1
                
                if completed_quests + not_completed_quests > 1:
                    self.logger.success("Completed quests:&bright&green", completed_quests, "&r&green|&Red", not_completed_quests)
                    
                # game
                available_ads = await self.available_ads()
                available_in = self.get_game_timer()

                self.logger.background("Checking available ads...")
                if available_in == 0:
                    clicks = await self.harvest(random.randint(*self.click_count), upgrades_tapDuration, upgrades_tapPower)
                    if clicks:
                        await self.earned_add(clicks)
                        self.logger.success("Played game and got:&blue", int(clicks), "&greendiamonds")
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                
                if available_ads > 0:
                    self.logger.info("Game is on cooldown,&green", available_ads, "&rskips available")
                    for attempt in range(0, available_ads):
                        if not self.running_allowed:
                            break
                        
                        self.update_info_panel("Watching ad...")
                        status = await self.skip_time()
                        if not status:
                            self.logger.error("Something went wrong while watching ad")
                            break
                        
                        self.logger.info("Watched&green", attempt + 1, "&rad")
                        self.update_info_panel("Playing game...")
                        
                        clicks = await self.harvest(random.randint(*self.click_count), upgrades_tapDuration, upgrades_tapPower)
                        if clicks:
                            await self.earned_add(clicks)
                            self.update_info_panel("Small pause...")
                            
                            self.logger.success("Played game and got:&blue", int(clicks), "&greendiamonds")
                            await asyncio.sleep(random.randint(*self.mini_sleep))

                # upgrades
                self.logger.background("Trying to upgrade...")
                upgrades_done = 0
                while upgrades_done < 3:
                    upgrades_done = 0
                    upgrades_info = await self.get_upgrades()
                    for upgrade, data in upgrades_info.items():
                        
                        level = data[0]["level"] if isinstance(data, list) and isinstance(data[0], dict) else None
                        
                        if level and self.upgrade_max_levels.get(upgrade, 0) > level:
                            upg_str = "(" + str(level) + "->" + str(data[1]["level"]) + ")"
                            price = float(data[1]["price"])
                            if price <= float(self.user_data["balance"]):
                                status = await self.buy_upgrade(upgrade)
                                if status:
                                    self.user_data["balance"] = str(float(self.user_data["balance"]) - price)
                                    self.diamonds = int(float(self.user_data["balance"]))
                                    self.logger.success("Upgraded&cyan", upgrade, "&green" + upg_str)
                                else:
                                    upgrades_done += 1
                                    self.logger.error("Unable to upgrade&cyan", upgrade, "&red" + upg_str)
                                await asyncio.sleep(random.randint(*self.mini_sleep))
                            else:
                                #self.logger.info("Not enough diamonds to upgrade:&cyan", upgrade, "&r" + upg_str)
                                upgrades_done += 1
                        else:
                            upgrades_done += 1
                            #self.logger.info("Upgrade:&cyan", upgrade, "&ris already at max(" + str(self.upgrade_max_levels[upgrade]) + ") allowed level by &yellowconfig")
                        self.update_info_panel("Checking for upgrades...")
                    
                self.user_data = await self.get_user()
                available_in = timedelta(seconds=self.get_game_timer())
                
                self.logger.info(f'Sleeping: {str(available_in).split(".")[0]}')
                date_now = datetime.now()
                sleep_until = date_now + available_in
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