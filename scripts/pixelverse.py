from src import telegram_session, logger, config, database, webclient, get_user_agent, WebUserTab, format_number, cache
from urllib.parse import quote
import asyncio
import random
from hmac import new
from hashlib import sha256
from datetime import datetime, timedelta
import aiohttp # for battle only
import json
from aiohttp import WSServerHandshakeError

class module:
    def __init__(self, session: telegram_session, user_tab: WebUserTab):
        self.session = session
        self.client = self.session.client
        self.user_tab = user_tab
        self.name = __name__.split(".")[-1]
        
        self.logger = logger(self.name, self.session.name, "&bgyellow", user_tab)
        self.config = config(self.name)
        self.db = database(self.name, self.session.name)
        self.webclient = webclient(self.session)
        self.cache = cache(self.name, self.session.name)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.api_domain = "https://api-clicker.pixelverse.xyz/api/"
        self.telegram_web_data = None
        self._key_hash = "adwawdasfajfklasjglrejnoierjboivrevioreboidwa" # may change
        self._secret_key = None
        
        self.points = 0
        self.pets_amount = 0
        self.level = 0
        
        self.earned = 0
        self.earned_session = self.cache.get("earned_session", 0)
        self.won_battles = 0
        self.lost_battles = 0
        
        self.info_placeholders = "Level: {lvl} | Points: {pts} | Pets: {pets}\nEarned with script: {earned} | Earned this session: {earned_session}\nBattles winrate with script: {winrate}\n{sleep_time}"
        self.info_label = user_tab.add_text_label(1)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self):
        self.config.load()
        self.refferal_code: str = self.config.get("refferal_code", "407777629")
        self.buy_new_pets: bool = self.config.get("buy_new_pets", True)
        self.pet_max_lvl: int = self.config.get("pet_max_lvl", 15)
        self.arena_pet_name: str | None = self.config.get("arena_pet_name", "")
        self.arena_play_amount_per_loop: str | None = self.config.get("arena_play_amount_per_loop", 10)
        self.arena_hit_cooldown: list = self.config.get("arena_hit_cooldown", [0.09, 0.089])
        self.mini_sleep: list = self.config.get("mini_sleep", [3, 5])
        self.config.save()
    
    async def init(self):
        self.earned = int(await self.db.get("earned", 0))
        self.won_battles = int(await self.db.get("won_battles", 0))
        self.lost_battles = int(await self.db.get("lost_battles", 0))
        
        self.webclient.user_agent = await get_user_agent(self.db)
        
        self.telegram_web_data = await self.session.request_web_view_data("pixelversexyzbot", self.refferal_code, "https://sexyzbot.pxlvrs.io/")
        self.user_tab.add_text_label(2, "[Open in web](%s)" % self.telegram_web_data.url)
        
        self.webclient._headers["initData"] = self.telegram_web_data.user_quoted_web_data
        self.webclient._headers["secret"] = self.secret
        self.webclient._headers["tg-id"] = str(self.session.account_data.id)
        self.webclient._headers["username"] = str(self.session.account_data.username)
        
    async def start(self):
        await self.run()

    async def cancel(self):
        self.running_allowed = False

    # CUSTOM
    @property
    def secret(self) -> str:
        if not self._secret_key:
            key_hash = str(self._key_hash).encode('utf-8')
            message = str(self.session.account_data.id).encode('utf-8')
            self._secret_key = new(key_hash, message, sha256).hexdigest()
            
        return self._secret_key
        
    async def my_boosts(self) -> list:
        response = await self.webclient.get(self.api_domain + "boost/my")
        if response.status == 200:
            return response.json
        
        return []
        
    async def my_levels(self) -> dict | None:
        response = await self.webclient.get(self.api_domain + "levels/my")
        if response.status == 200:
            return response.json
    async def levelup_start(self) -> dict | None:
        response = await self.webclient.post(self.api_domain + "levels/levelup/start")
        if response.is_json:
            return response.json
    async def levelup_finish(self) -> dict | None:
        response = await self.webclient.post(self.api_domain + "levels/levelup/finish")
        if response.is_json:
            return response.json
    
    async def shop_items(self) -> list:
        response = await self.webclient.get(self.api_domain + "shop/items")
        if response.status == 200:
            return response.json
        
        return []
    
    async def users(self) -> dict | str | None:
        response = await self.webclient.get(self.api_domain + "users")
        if response.status == 200:
            return response.json
        elif response.status == 400:
            is_banned = response.json.get("message") == "You have been blocked"
            return "ban" if is_banned else None
    
    async def mining_progress(self) -> dict | None:
        response = await self.webclient.get(self.api_domain + "mining/progress")
        if response.status == 200:
            return response.json
    async def mining_claim(self) -> dict | None:
        response = await self.webclient.post(self.api_domain + "mining/claim")
        if response.status == 201:
            return response.json
    
    async def gems(self) -> int:
        response = await self.webclient.post(self.api_domain + "user-gems")
        if response.status == 200:
            return response.json.get("gemsAmount")
        
        return 0
    
    async def pets(self) -> dict | None:
        response = await self.webclient.get(self.api_domain + "pets")
        if response.status == 200:
            return response.json
    async def buy_pet(self) -> dict:
        response = await self.webclient.get(self.api_domain + "pets/buy", json={})
        if response.status == 200:
            return response.json
    async def upgrade_pet(self, id: str) -> dict:
        response = await self.webclient.post(self.api_domain + "pets/user-pets/" + id + "/level-up")
        if response.status == 201:
            return response.json
    async def select_pet(self, id: str) -> dict:
        response = await self.webclient.post(self.api_domain + "pets/user-pets/" + id + "/select")
        if response.status == 201:
            return response.json
        
    async def tasks(self) -> list:
        response = await self.webclient.get(self.api_domain + "tasks/my")
        if response.status == 200:
            tasks = []
            for v in response.json.values():
                tasks.extend(v)
            return tasks
    async def task_start(self, id: str) -> dict | None:
        response = await self.webclient.post(self.api_domain + "tasks/start/" + id)
        if response.status == 201:
            return response.json
    async def task_check(self, id: str) -> dict | None:
        response = await self.webclient.get(self.api_domain + "user-tasks/" + id + "/check")
        if response.status == 200:
            return response.json
    async def task_check_telegram(self, id: str) -> dict | None:
        response = await self.webclient.post(self.api_domain + "telegram-tasks/subscribe/" + id + "/check")
        if response.status == 201:
            return response.json
    
    async def daily_rewards(self) -> dict | None:
        response = await self.webclient.get(self.api_domain + "daily-rewards")
        if response.status == 200:
            return response.json
    async def claim_daily_reward(self) -> dict | None:
        response = await self.webclient.post(self.api_domain + "daily-rewards/claim")
        if response.status == 201:
            return response.json
    
    async def roulette(self) -> dict | None:
        response = await self.webclient.get(self.api_domain + "roulette")
        if response.status == 200:
            return response.json
    async def roulette_spin(self) -> dict | None:
        response = await self.webclient.post(self.api_domain + "roulette/spin")
        if response.status == 201:
            return response.json
    
    async def cypher_games(self) -> None:
        response = await self.webclient.get("https://api-clicker.pixelverse.xyz/api/cypher-games/current")
        if response.status == 200:
            id = response.json.get("id")
            options: list = response.json.get("availableOptions")
            json = {}
            for i in range(0, 4):
                option: dict = random.choice(options)
                json.update({option["id"]: i})
                options.remove(option)
                
            response = await self.webclient.post("https://api-clicker.pixelverse.xyz/api/cypher-games/" + id + "/answer", json=json)
            if response.status == 201:
                reward = response.json.get("rewardAmount", 0)
                if reward > 0:
                    await self.add_earned(int(reward))
                    self.logger.success("Got:&yellow", reward, "&rfrom cypher game")
                    self.update_info_panel()
                else:
                    self.logger.background("Got nothing from cypher game")
    
    async def arena_battle(self) -> None:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.ws_connect("wss://api-clicker.pixelverse.xyz/socket.io/?EIO=4&transport=websocket") as ws:
                    
                    await ws.send_str('40{"tg-id":' + self.webclient._headers["tg-id"] + "," + 
                                    '"secret":"' + self.webclient._headers["secret"] + '",' +
                                    '"initData":"' + self.webclient._headers["initData"] + '"}'
                                    )
                    
                    battle_id = None
                    hits = 0
                    
                    async for message in ws:
                        if message.type != aiohttp.WSMsgType.TEXT:
                            continue
                        
                        if message.data == "2":
                            await ws.send_str("3")
                            continue
                        
                        if "42[" in message.data:
                            data = json.loads(message.data[2:])
                            
                            if data[0] == "START":
                                battle_id = data[1].get("id")
                            
                            if not battle_id:
                                continue
                            
                            if "SET_SUPER_HIT_DEFEND_ZONE" in message.data:
                                await ws.send_str(
                                    '42["SET_SUPER_HIT_DEFEND_ZONE",{"battleId":"' + battle_id + '","zone":' + str(random.randint(1, 4)) + '}]'
                                ) 
                                
                            if "SET_SUPER_HIT_ATTACK_ZONE" in message.data:
                                await ws.send_str(
                                    '42["SET_SUPER_HIT_ATTACK_ZONE",{"battleId":"' + battle_id + '","zone":' + str(random.randint(1, 4)) + '}]'
                                )
                                
                            if data[0] == "END":
                                match data[1].get("result"):
                                    case "WIN":
                                        self.won_battles += 1
                                        await self.db.update("won_battles", self.won_battles)
                                        self.logger.success("Won in battle | hits:&bright&cyan", hits, "| reward:&yellow", data[1].get("reward"))
                                    case "LOSE":
                                        self.lost_battles += 1
                                        await self.db.update("lost_battles", self.lost_battles)
                                        self.logger.background("Lost in battle | hits:&bright&cyan", hits, "| lost:&yellow", data[1].get("reward"))
                                
                                return
        
                            hits += 1
                            await ws.send_str('42["HIT",{"battleId":"' + battle_id + '"}]')
                            self.update_info_panel("Fighting... Hits: " + str(hits))
                            
                            await asyncio.sleep(random.uniform(*self.arena_hit_cooldown))
                    
        except ConnectionResetError:
            self.logger.background("Battle ended unexpectedly...")
        except WSServerHandshakeError:
            pass
        
    def update_info_panel(self, sleep_time: str = "Active...") -> None:
        total_games = self.won_battles + self.lost_battles
        winrate = "{}% ({}-{})".format(int(self.won_battles / total_games * 100), self.won_battles, self.lost_battles) if self.won_battles > 0 and self.lost_battles > 0 else "-"
        self.info_label.object = self.info_placeholders.format(
            lvl=self.level,
            pts=format_number(self.points),
            pets=format_number(self.pets_amount),
            earned=format_number(self.earned),
            earned_session=format_number(self.earned_session),
            winrate=winrate,
            sleep_time=sleep_time
        )
    
    async def add_earned(self, value: int) -> None:
        self.earned += value
        self.earned_session += value
        self.cache.set("earned_session", self.earned_session)
        self.points += value
        await self.db.update("earned", self.earned)
    
    async def run(self):
        while self.running_allowed:
            try:
                self.refresh_config()
                user_data = await self.users()
                pets = await self.pets()
                if user_data == "ban":
                    wait_time = timedelta(hours=4)
                    self.logger.error("Banned, retrying in", str(wait_time))
                    date_now = datetime.now()
                    sleep_until = date_now + wait_time
                    while date_now < sleep_until:
                        date_now = datetime.now()
                        self.info_label.object = "Banned, retrying in " + str(sleep_until - date_now).split(".")[0]
                        await asyncio.sleep(1)
                    continue
                
                if not user_data or not pets:
                    self.info_label.object = "Userdata or pets were not found.\nRetrying..."
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                    continue
                
                self.points = int(str(user_data.get("clicksCount")).split(".")[0])
                self.pets_amount = len(pets.get("data"))
                self.logger.info("Points:&yellow", self.points, "| Pets:&cyan", self.pets_amount)
                self.update_info_panel()

                await asyncio.sleep(random.randint(*self.mini_sleep))
                
                # mining
                self.logger.background("Checking mining progress...")
                mining_progress = await self.mining_progress()
                if mining_progress.get("currentlyAvailable") > mining_progress.get("minAmountForClaim"):
                    status = await self.mining_claim()
                    if status:
                        earned = int(status.get("claimedAmount"))
                        await self.add_earned(earned)
                        self.logger.success("Claimed:&yellow", earned, "&rfrom mining")
                        self.update_info_panel()
                
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                # daily rewards
                self.logger.background("Checking daily rewards...")
                daily_rewards_data = await self.daily_rewards()
                if daily_rewards_data and daily_rewards_data.get("todaysRewardAvailable"):
                    data = await self.claim_daily_reward()
                    if data:
                        earned = int(str(data.get("amount")).split(".")[0])
                        await self.add_earned(earned)
                        self.logger.success("Claimed daily:&yellow", earned)
                        self.update_info_panel()
                        
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                roulette_data = await self.roulette()
                if roulette_data and roulette_data.get("mySpinsAmount", 0) > 0:
                    for i in range(roulette_data.get("mySpinsAmount")):
                        data = await self.roulette_spin()
                        if not data:
                            break
                        
                        self.logger.success("Spinned roulette")
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                
                await self.cypher_games()
                
                await asyncio.sleep(random.randint(*self.mini_sleep))
                
                # tasks
                self.logger.background("Checking tasks...")
                tasks = await self.tasks()
                for task in tasks:
                    status = task.get("status")
                    type = task.get("type")
                    id = task.get("userTaskId", task.get("id"))
                    if task.get("taskStatus") != "ACTIVE" or status == "DONE":
                        continue
                    
                    if type in ["SNAPSHOT", "REGISTER_WITH_TELEGRAM", "PINATA", "LOOTIFY"]:
                        continue
                
                    if status is None:
                        task = await self.task_start(id)
                        status = task.get("status")
                        id = task.get("userTaskId", task.get("id"))
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                    if type == "TELEGRAM":
                        await self.session.revive(self.name)
                        joined = await self.session.temp_join_channel(self.name, task.get("redirectUrl"))
                        if joined:
                            self.logger.background("Temporarily joining to", task.get("redirectUrl"))
                    
                    if status == "IN_PROGRESS":
                        if type == "TELEGRAM":
                            task = await self.task_check_telegram(id)
                        else:
                            task = await self.task_check(id)
                            
                        status = task.get("status")
                        await asyncio.sleep(random.randint(*self.mini_sleep))
                    
                    if status == "DONE":
                        self.logger.success("Done&white", task.get("title", task.get("task").get("title")), "&rtask")
                        
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                await self.session.leave_temp_channels(self.name)
                await self.session.revive_end(self.name)
                
                user_data = await self.users()
                self.points = int(str(user_data.get("clicksCount")).split(".")[0])
                self.update_info_panel()
                
                # levels
                self.logger.background("Checking level requirements...")
                my_level = await self.my_levels()
                if my_level:
                    if my_level.get("levelupStartedAt") is None:
                        tasks_completed = 0
                        tasks = my_level.get("tasksToLevelup")
                        for task in tasks:
                            if not task.get("completed"):
                                self.logger.background("&white" + task.get("name"), "&rmust be completed to level up")
                                continue
                            
                            tasks_completed += 1
                    
                        if tasks_completed == len(tasks):
                            await self.levelup_start()
                            self.logger.success("Leveling up to&blue", my_level.get("value") + 1)
                    
                    if my_level.get("levelupStartedAt"):
                        start_time = datetime.strptime(my_level.get("levelupStartedAt"), "%Y-%m-%dT%H:%M:%S.%fZ")
                        time_elapsed = datetime.now() - start_time
                        if time_elapsed.total_seconds() - (my_level.get("levelupProcessDurationMs") / 1000) > 0:
                            my_level = await self.levelup_finish()
                            self.level = int(my_level.get("value"))
                            self.logger.success("Leveled up to&blue", my_level.get("value"))
                    
                self.update_info_panel()
                await asyncio.sleep(random.randint(*self.mini_sleep))
                
                class arena_pet:
                    name = "?"
                    id = "?"
                    power = 0
                    selected_by_user = True if self.arena_pet_name != "" else False
                
                # pets
                self.logger.background("Checking if new pet available for purchase...")
                if self.buy_new_pets and pets.get("buyPrice") < user_data.get("clicksCount"):
                    status = await self.buy_pet()
                    if status:
                        self.pets_amount += 1
                        self.logger.info("Bought new pet with name:&cyan", status.get("?"))
                        self.update_info_panel()
                        
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.logger.background("Trying to upgrade pets...")
                for pet in pets.get("data", []):
                    pet_name: str = pet.get("name")
                    pet: dict = pet.get("userPet")
                    pet_level: int = pet.get("level")
                    pet_id: str = pet.get("id")
                    if pet_level < self.pet_max_lvl: # try to upgrade
                        pet_lvlup_price = int(pet.get("levelUpPrice"))
                        if pet_lvlup_price < self.points:
                            status = await self.upgrade_pet(pet_id)
                            if status:
                                self.points -= pet_lvlup_price
                                self.logger.success("Upgraded&white", pet_name, "&r(" + str(pet_level) + "->" + str(pet_level + 1) + ")")
                                self.update_info_panel()
                    
                    if arena_pet.selected_by_user:
                        if pet_name.lower() == self.arena_pet_name.lower():
                            arena_pet.name = pet_name
                            arena_pet.id = pet_id
                            arena_pet.power = total_power
                    
                    else:
                        stats = pet.get("stats", [{}, {}, {}])
                        dmg = stats[0].get("currentValue", 0)
                        max_energy = stats[1].get("currentValue", 0)
                        energy_restoration = stats[2].get("currentValue", 0)
                        
                        total_power = (dmg * 1.2) + (max_energy * 1.1) + (energy_restoration * 1)
                        
                        if arena_pet.power < total_power:
                            arena_pet.name = pet_name
                            arena_pet.id = pet_id
                            arena_pet.power = total_power
                
                    await asyncio.sleep(random.randint(*self.mini_sleep))
                
                self.logger.background("Trying to start battles...")
                if arena_pet.name != "?":
                    await self.select_pet(arena_pet.id)
                    
                    self.logger.warn("DONT STOP SCRIPT UNTIL BATTLES IS ENDED, IF YOU DO SO, YOU'LL GET TEMP BANNED")
                    for _ in range(self.arena_play_amount_per_loop):
                        if not self.running_allowed:
                            break
                            
                        self.logger.background("Started battle")
                        await self.arena_battle()
                        if self.arena_play_amount_per_loop >= _:
                            wait_time = random.randint(30, 60)
                            self.logger.background("Staring new battle in", wait_time, "seconds")
                            while self.running_allowed and wait_time > 0:
                                self.update_info_panel("New battle starts in " + str(wait_time) + " seconds")
                                wait_time -= 1
                                await asyncio.sleep(1)
                                
                    self.logger.background("Ended fighting in battles.")
                    self.update_info_panel()
                
                mining_progress = await self.mining_progress()
                until_mining_ends = 1*60*60
                if mining_progress:
                    until_mining_ends = (datetime.strptime(mining_progress.get("nextFullRestorationDate"), "%Y-%m-%dT%H:%M:%S.%fZ") - datetime.now()).total_seconds() / 2
                    if until_mining_ends < 0:
                        until_mining_ends = 10*60
                    
                wait_time = timedelta(seconds=until_mining_ends)
                self.logger.info("Sleeping:", str(wait_time).split(".")[0])
                date_now = datetime.now()
                sleep_until = date_now + wait_time
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