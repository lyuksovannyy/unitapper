import asyncio
import importlib
import os

from .terminal import terminal
from .misc import split_list, parse_proxies
from .. import get_sessions_count, get_sessions, telegram_session, database
from ..webpanel import webpanel

from datetime import datetime, timedelta

# schema classes (ignore)
class _example_script_module:
    def __init__(self) -> None:
        class logger:
            sns: int = ...
            uns: int = ...
        self.logger = logger
        ...
    async def init(self) -> None:
        ...
    async def start(self) -> None:
        ...
    async def cancel(self) -> None:
        ...
class _example_script:
    def __init__(self) -> None:
        ...
    async def start(self) -> _example_script_module:
        ...
    class module:
        ...
# end of the schema

class launcher:
    def __init__(self, script: str = None, session: str = None) -> None:
        self.title = '''&purple
:::    ::: ::::    ::: ::::::::::: ::::::::::: :::     :::::::::  :::::::::  :::::::::: :::::::::  
:+:    :+: :+:+:   :+:     :+:         :+:   :+: :+:   :+:    :+: :+:    :+: :+:        :+:    :+: 
+:+    +:+ :+:+:+  +:+     +:+         +:+  +:+   +:+  +:+    +:+ +:+    +:+ +:+        +:+    +:+ 
+#+    +:+ +#+ +:+ +#+     +#+         +#+ +#++:++#++: +#++:++#+  +#++:++#+  +#++:++#   +#++:++#:  
+#+    +#+ +#+  +#+#+#     +#+         +#+ +#+     +#+ +#+        +#+        +#+        +#+    +#+ 
#+#    #+# #+#   #+#+#     #+#         #+# #+#     #+# #+#        #+#        #+#        #+#    #+# 
 ########  ###    #### ###########     ### ###     ### ###        ###        ########## ###    ###&r

WebServer started at http://localhost:''' + str(webpanel._port) + '\n'

        self.scripts_running = False

        self.output_prefix = "    &yellow𝚒&r"
        self.output = ""
    
        self.disabled_scripts = [
            "example.py",
            "__init__.py"
        ]
        self.allowed_scripts = str(script) if script else ""
        self.allowed_sessions = str(session) if session else ""

        self.options_title = "    Select action:&r"
        self.option_prefix = "    &gray○ &r&cyan{} &gray-&r"
        self.option_suffix = ""
        self.options = {
            "True": { # have sessions
                "Start &purpleUniTapper&r scripts": self.start_scripts,
                "Check &bright&cyanTelegram&r sessions": self.check_sessions,
                "Make &bright&cyanTelegram&r session&r": self.make_session
            },
            "False": { # no sessions
                "Make &bright&cyanTelegram&r session&r": self.make_session
            }
        }
    
    @property
    def has_sessions(self) -> bool:
        return get_sessions_count() > 0
    
    async def show(self) -> None:
        #terminal.clear()
        terminal.write(self.title)
        terminal.write(self.options_title)
        num = 0
        for option in self.options[str(self.has_sessions)].keys():
            num += 1
            terminal.write(self.option_prefix.format(num), option, self.option_suffix)
            
        if self.output != "":
            terminal.write("\n" + self.output_prefix, self.output)
            
    async def select_option(self, option_num: int) -> bool | str:
        '''Indicates if correct option provided
        '''
        num = 0
        for option in self.options[str(self.has_sessions)].values():
            num += 1
            if option_num == num:
                state = await option()
                return True if state is None else state
        
        return False
    
    async def start_scripts(self) -> None:
        global biggest_user_name, modules, progress # :( shitty method
        
        biggest_script_name = 0
        biggest_user_name = 0
        tasks: dict[asyncio.Task] = []
        modules = []
        scripts: dict[str, _example_script] = {}
        progress = terminal.loading("")
        
        allowed_logins_at_same_time = int(os.getenv("MAX_LOGINS_AT_SAME_TIME"))
        restart_every_hrs = int(os.getenv("RESTART_EVERY_HRS"))
        
        proxies = parse_proxies()
        _sessions = get_sessions(proxies)
        
        splitted_sessions = split_list(_sessions, allowed_logins_at_same_time)
        
        for script in os.listdir("scripts/"):
            name = script.removesuffix(".py")
            if script.endswith(".py") and script not in self.disabled_scripts and (self.allowed_scripts == "" or name in self.allowed_scripts):
                if len(name) > biggest_script_name:
                    biggest_script_name = len(name)
                progress.text = ("Prepairing script: &bright&blue" + name)
                scripts[name] = importlib.import_module("scripts." + name)
        
        async def prepare_session(session: telegram_session) -> None:
            global biggest_user_name, modules, progress # :( shitty method
            state, err = await session.check()
            if not state:
                progress.text = ("&red✘&r Failed to log-in &bright&blue" + session.name + " " + str(err))
                await asyncio.sleep(3)
                return False
        
            async with session.client:
                if len(session.name) > biggest_user_name:
                    biggest_user_name = len(session.name)
                
                for name, script in scripts.items():
                    script_tab = webpanel.add_tab(name)
                    user_tab = script_tab.add_user(session.name)
                    progress.text = ("Loading: &bright&cyan" + name + " &rfor &bright&blue" + session.name)
                    module = await script.start(session, user_tab) # example.py
                    modules.append(module)
                
                return True
        
        login_tasks = []
        if len(scripts) != 0:
            for sessions in splitted_sessions:
                login_tasks.clear()
                for session in sessions:
                    if self.allowed_sessions == "" or session.name in self.allowed_sessions:
                        login_tasks.append(
                            prepare_session(session)
                        )
                        
                await asyncio.gather(*login_tasks)
        
        else:
            return "empty"
            
        for module in modules:
            module: _example_script_module
            module.logger.sns = biggest_script_name
            module.logger.uns = biggest_user_name
            tasks.append(
                asyncio.Task(module.start())
            )
            
        progress.stop("")
        self.output = "&greenScripts are gonna start shortly. {}".format(
            ("(restaring in %s hours)" % restart_every_hrs) if restart_every_hrs > 0
            else "&red(restarting is disabled, not recommended)"
        )
        await self.show()
        
        async def restart_timer_func():
            date_now = datetime.now()
            date_now = date_now - timedelta(microseconds=date_now.microsecond)
            if not webpanel.active_time:
                webpanel.active_time = date_now
            webpanel.restarting_in = (date_now + timedelta(hours=restart_every_hrs)) if restart_every_hrs > 0 else None
            
            webpanel.restart_button.disabled = False
            webpanel.stop_button.disabled = False
            
            while (webpanel.restarting_in is None or webpanel.restarting_in > datetime.now()) and not webpanel.stop_requested:
                await asyncio.sleep(0.5)
            
            webpanel.restart_amount += 1
            cancel_tasks = []
            for module in modules: # ending tasks softly, so no problems appears
                cancel_tasks.append(
                    module.cancel()
                )
            await asyncio.gather(*cancel_tasks)
            
            timeout_date = datetime.now() + timedelta(seconds=30)
            while date_now < timeout_date:
                date_now = datetime.now()
                webpanel.restarting_in = "Forced restart coming in: " + str(timeout_date - date_now).split(".")[0]
                await asyncio.sleep(0.5)
            
            for task in running_tasks:
                try:
                    task.cancel()
                except:
                    pass
        
        try:
            running_tasks = await asyncio.gather(*tasks, restart_timer_func())
            print("running tasks")
        except Exception or asyncio.CancelledError:
            pass
        
        for sessions in splitted_sessions:
            for session in sessions:
                session: telegram_session
                if session.client.is_connected:
                    await session.client.disconnect()
            
        await (database("_", "_")).close()
        
        if webpanel.stop_requested:
            webpanel.sidebar.clear()
            webpanel.main_area.clear()
            await asyncio.sleep(0.1)
            return "stop"
        
        return True
        
    async def check_sessions(self) -> None:
        valid = 0
        invalid = 0
        progress = terminal.loading("")
        
        sessions = get_sessions()
        for session in sessions:
            progress.text = "Checking &bright&blue" + session.name + " &raccount"
            state, err = await session.check()
            if state:
                valid += 1
            else:
                invalid += 1
        progress.stop()
        
        self.output = "Valid: &green" + str(valid) + " &r&gray|&r Invalid: &red" + str(invalid)
        
    async def make_session(self) -> None:
        session_name = terminal.input("Input session name &gray> ")
        if session_name.replace(" ", "") == "":
            self.output = "&redAborted."
            return
        session = telegram_session(session_name)
        await session.remove()
        state, err = await session.check()
        if state:
            self.output = "&green✔&r &bright&blue " + str(session.account_data.username or session.account_data.first_name if session.account_data else session.name)
        else:
            self.output = "&red✘&r Account&bright&blue " + str(session.cache_data.username or session.name if session.cache_data else session.name) + " &r: " + err
        