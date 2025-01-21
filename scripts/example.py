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
        self.bot_username = "example_bot"
        self.bot_url_short_name = "app" # most of the are using 'app' some may have different short name, someone doesn't have at all short name so you'll need to use mini-app's url instead
        
        # MANDATORY MODULES TO MAKE SCRIPT EASY TO MAKE
        self.logger = logger(self.name, self.session.name, user_tab=user_tab) # custom logger
        self.config = config(self.name)                  # config for script
        self.db = database(self.name, self.session.name) # database to store script's statistics or whatever you want, stores all info in strings...
        self.webclient = webclient(self.session)         # webclient to make all requests
        self.cache = cache(self.name, self.session.name) # used only to save data after script is gonna be restarted (not exited)
        
        self.refresh_config()
        
        self.running_allowed = True
        self.telegram_web_data = None
        
        self._earned = 0
        self._earned_session = self.cache.get("earned_session", 0)
        
        self.info_placeholders = "\nEarned with script: {earned} | Earned this session: {earned_session}\n{activity}"
        self.info_label = self.user_tab.add_text_label(1)
        self.open_in = self.user_tab.add_text_label(2)
        
        random.seed(str(self.session.account_data.id) + self.name)
        
    # DEFAULT
    def refresh_config(self) -> None:
        '''Update config data if changes were made'''
        self.config.load()
        self.referral_code: str = self.config.get("referral_code", "example_ref")
        self.mini_sleep: list = self.config.get("mini_sleep", [1, 5])
        self.config.save()
    
    async def auth(self, revive_session: bool = True) -> None:
        '''Authorize to mini-app and receive new login data'''
        if revive_session:
            await self.session.revive(self.name)
        
        self.telegram_web_data = await self.session.request_web_view_data(self.bot_username, self.referral_code, self.bot_url_short_name)
        self.open_in.object = "[Open in web](%s)" % self.telegram_web_data.url
        
        if revive_session:
            await self.session.revive_end(self.name)
    
    async def init(self) -> None:
        '''Starts before the main code (in general used for auth-only things)'''
        self.webclient.user_agent = await get_user_agent(self.db)
        self._earned = int(await self.db.get("earned", 0))
        
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
            earned=format_number(self._earned),
            earned_session=format_number(self._earned_session),
            activity=activity_text
        )
    
    async def earned(self, value: int) -> None:
        '''Save "earned" stat'''
        self._earned += value
        self._earned_session += value
        self.cache.set("earned_session", self._earned_session)
        await self.db.update("earned", self._earned)
    
    # CUSTOM
    async def run(self):
        '''Your code here'''
        while self.running_allowed:
            try:
                self.refresh_config()
                self.update_info_panel()
                
                await wait_until(self, 1)
            except Exception as err:
                self.logger.error("Unexpected error occurred:", err)
                await asyncio.sleep(1)

async def start(session, user_tab):
    _module = module(session, user_tab)
    await _module.init()
    return _module