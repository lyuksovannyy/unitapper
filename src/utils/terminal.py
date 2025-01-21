import os
import sys
import asyncio
import colorama
from datetime import datetime
from colorama import Fore, Back, Style

from ..webpanel.panel import WebUserTab, webpanel

class _LoadingAnimation:
    def __init__(self, color_handler, speed: int, animation: list) -> None:
        self._text = ""
        self._color_handler = color_handler
        self.last_len = 0
        self.line_index = None
        self.animation = animation
        self.speed = speed
        self._stop = False
    
    @property
    def text(self) -> str:
        return self._text
    
    @text.setter
    def text(self, value) -> None:
        self._text = self._color_handler(value + "&r")
    
    async def _animate(self) -> None:
        i = 0
        while True:
            if self._stop:
                break
            
            frame = self.animation[i % len(self.animation)]
            sys.stdout.write(f"\r{frame} {self._text}" + " "*self.last_len)
            sys.stdout.write(f"\r{frame} {self._text}")
            self.last_len = len(frame + " " + self._text)
            sys.stdout.flush()
            i += 1
            await asyncio.sleep(self.speed)
    
    def _start(self) -> None:
        self._stop = False
        asyncio.create_task(self._animate())

    def stop(self, text: str = None) -> None:
        if text:
            self.text = text
        sys.stdout.write("\r" + " "*self.last_len)
        sys.stdout.write("\r" + self._text + "\n")
        self._stop = True
            
class terminal:
    def __init__(self) -> None:
        '''terminal with ability to\n
        change colors and make animations without\n
        yielding the main code
        '''
        self.timeout = 30
        self.loading_animation = [
                "○——", "—○—", "——○", "—○—"]
        self.loading_speed = 0.2
        
        self._replacers = {
            "|": "&r&gray|&r"
        }
        self._colors = {
            "WHITE": Fore.WHITE,
            "BLACK": Fore.BLACK,
            "BLUE": Fore.BLUE,
            "CYAN": Fore.CYAN,
            "GREEN": Fore.GREEN,
            "RED": Fore.RED,
            "YELLOW": Fore.YELLOW,
            "PURPLE": Fore.MAGENTA,
            "MAGENTA": Fore.MAGENTA,
            
            "REALLYWHITE": Fore.LIGHTWHITE_EX,
            "GRAY": Fore.LIGHTBLACK_EX,
        }
        self._backgrounds = {
            "BGWHITE": Back.WHITE,
            "BGBLACK": Back.BLACK,
            "BGBLUE": Back.BLUE,
            "BGCYAN": Back.CYAN,
            "BGGREEN": Back.GREEN,
            "BGRED": Back.RED,
            "BGYELLOW": Back.YELLOW,
            "BGPURPLE": Back.MAGENTA,
            "BGMAGENTA": Back.MAGENTA,
            
            "BGREALLYWHITE": Back.LIGHTWHITE_EX,
            "BGGRAY": Back.LIGHTBLACK_EX,
        }
        self._styles = {
            "NORMAL": Style.NORMAL,
            "DIM": Style.DIM,
            "DARK": Style.DIM,
            "BRIGHT": Style.BRIGHT,
            "RESET": Style.RESET_ALL,
            "R": Style.RESET_ALL,
            "_R": Style.RESET_ALL
        }
        self._allinone = {}
        self._allinone.update(self._colors)
        self._allinone.update(self._backgrounds)
        self._allinone.update(self._styles)
        
        colorama.init()
        
    def _color_handler(self, raw_text: str, custom_replacers: dict = {}) -> str:
        '''handler for colors in terminal text
        '''
        replacers = self._replacers.copy()
        replacers.update(custom_replacers)
        
        for key, value in replacers.items():
            raw_text = raw_text.replace(key, value)
        
        splitted_text = raw_text.split("&")
        formatted_text = ""
        
        num = 0
        for part in splitted_text:
            num += 1
            found = False
            for name, color in self._allinone.items():
                if part.upper().startswith(name):
                    found = True
                    formatted_text += color + part[len(name):]
                    break
                
            if not found:
                formatted_text += ("&" if num != 1 else "") + part
                    
        return formatted_text
        
    def _remove_colors(self, raw_text: str) -> str:
        splitted_text = raw_text.split("&")
        formatted_text = ""
        
        for part in splitted_text:
            for name, color in self._allinone.items():
                if part.upper().startswith(name):
                    part = part[len(name):]
                
                formatted_text += part
                    
        return formatted_text
        
    def write(self, *args, prefix: str = "", suffix: str = "\n", spacing: str = " ", custom_replacers: dict = {}) -> None:
        '''print-like function\n
        **\*args**: converting to 'str'\n
        '''
        
        raw_text = str(spacing.join([
            str(arg)
            for arg in args
        ]))
        
        text = self._color_handler(raw_text, custom_replacers)
        
        sys.stdout.write(prefix + text + Style.RESET_ALL + suffix)

    def loading(self, message: str) -> _LoadingAnimation:
        '''print-like function
        - **ignores self.timeout rule**\n
        at start of the text loading animation are gonna be shown\n
        to end loading animation, call returned value with no arguments\n
        or add any arguments to change text
        '''
        loading_animation = _LoadingAnimation(self._color_handler, self.loading_speed, self.loading_animation)
        loading_animation.text = message
        loading_animation._start()
        return loading_animation

    def input(self, *args, forced_input: str = None) -> str:
        '''input-like function
        '''
        forced_input = str(forced_input) if forced_input else None
        self.write(*args, suffix = "")
        return forced_input or input()
    
    def clear(self):
        '''clear console
        '''
        os.system("cls")

class logger:
    def __init__(self, script_name: str, user_name: str, color: str = "&bgwhite&black", user_tab: WebUserTab = None) -> None:
        self.sn = script_name # script_name
        self.un = user_name   # user_name
        self.color = color
        self._sns = 0 # script_name_spacing
        self._uns = 0 # user_name_spacing
        
        self.time_format = "%H:%M:%S %d.%m.%y"
        
        self.user_tab = user_tab

    @property
    def _start_str(self) -> str:
        return str(self._time() + "&_r &gray|&_r " + self.color + " " + self.sn + " "*(self._sns) + " &_r &gray|&_r &bright&blue" + self.un + " "*self._uns + " &_r&gray|&r")

    @property
    def sns(self):
        return self._sns
    
    @property
    def uns(self):
        return self._uns
    
    @sns.setter
    def sns(self, value):
        self._sns = value - len(self.sn)
    
    @uns.setter
    def uns(self, value):
        self._uns = value - len(self.un)
    
    def _handle_args(self, *args):
        raw = []
        for arg in args:
            if isinstance(arg, Exception):
                raw.append(type(arg).__name__ + " - " + str(arg))
                continue
            
            raw.append(str(arg))
            
        return " ".join(raw)
    
    def _time(self) -> str:
        return str(datetime.now().strftime(self.time_format))
    
    def debug(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args), custom_replacers={"&r": "&_r&dim&yellow"})
        terminal.write(string)
        
        #webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.debug(*args, custom_replacers={"&r": "&_r&dim&yellow"})
        
    def info(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args))
        terminal.write(string)
        
        webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.info(*args)
        
    def warn(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args), custom_replacers={"&r": "&_r&yellow"})
        terminal.write(string)
        
        webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.warn(*args, custom_replacers={"&r": "&_r&yellow"})
        
    def error(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args), custom_replacers={"&r": "&_r&red"})
        terminal.write(string)
        
        webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.error(*args, custom_replacers={"&r": "&_r&red"})
    
    # Some misc
    def background(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args), custom_replacers={"&r": "&_r&gray"})
        terminal.write(string)
        
        #webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.background(*args, custom_replacers={"&r": "&_r&gray"})
        
    def success(self, *args) -> None:
        string = terminal._color_handler(self._handle_args(self._start_str, *args), custom_replacers={"&r": "&_r&green"})
        terminal.write(string)
        
        webpanel.write(string + Style.RESET_ALL)
        if self.user_tab:
            self.user_tab.success(*args, custom_replacers={"&r": "&_r&green"})
        
terminal = terminal()