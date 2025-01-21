import panel as pn
from datetime import datetime
from colorama import Fore, Back, Style
import asyncio

from ..storage import config

# abit shitcodded :)

pn.extension("terminal", sizing_mode="stretch_width", template="fast")

class WebUserTab:
    def __init__(self, parent, name: str) -> None:
        self._parent = parent
        self._name = name
        self._terminal = pn.widgets.Terminal(
            "",
            options=dict(
                cursorBlink=False
            )
        )
        self._text_labels = pn.Row()
        self._created_labels = {}
        
        # terminal related
        self.time_format = "%H:%M:%S %d.%m.%y"
        
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
        
        self.levels = {
            "DEBUG": "&dim&yellowDEBUG     ",
            "INFO":  "&blueINFO      ",
            "WARN":  "&yellowWARN      ",
            "ERROR": "&rERROR     ",
            "BACKG": "&grayBACKGROUND",
            "SUCCS": "&greenSUCCSESS  "
        }

        self.layout = pn.Column(
            self._text_labels,
            self._terminal
        )
        self.layout.visible = False
        
    def add_text_label(self, id: int, text: str = "Info panel - Initalizing") -> pn.pane.Markdown:
        '''https://panel.holoviz.org/reference/panes/Markdown.html'''
        created = self._created_labels.get(id)
        if created:
            return created
        markdown = pn.pane.Markdown(str(text))
        self._created_labels.update({id: markdown})
        self._text_labels.append(markdown)
        return markdown
        
    # terminal related
    def _handle_args(self, *args):
        raw = []
        for arg in args:
            if isinstance(arg, Exception):
                raw.append(type(arg).__name__ + " - " + str(arg))
                continue
            
            raw.append(str(arg))
            
        return " ".join(raw) + "\n"
    
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
                    
        return formatted_text + Style.RESET_ALL
    
    def _start_str(self, level: str) -> str:
        return str(self._time + " | " + level + " | &r")

    @property
    def _time(self) -> str:
        return str(datetime.now().strftime(self.time_format))
    
    def debug(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["DEBUG"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)
    
    def info(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["INFO"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)
    
    def warn(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["WARN"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)
        
    def error(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["ERROR"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)
        
    def background(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["BACKG"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)
        
    def success(self, *args, custom_replacers = {}) -> None:
        text = self._color_handler(self._start_str(self.levels["SUCCS"]) + self._handle_args(*args), custom_replacers)
        self._terminal.write(text)

class WebTab:
    def __init__(self, parent, name: str) -> None:
        self._parent = parent
        self._layout = self._parent.layout
        self._name = name
        
        self._config = config(name)
        self._config_objs = {}
        
        self._users = {}
        
        self._text_labels = pn.Row()
        
        # sidebar button
        self._tab_button = pn.widgets.Button(
            name=self._name, 
            button_type="primary"
        )
        
        # tab's layout
        # Overview
        self._account_selector = pn.widgets.Select(name="Account list", options=[])
        self._active_account_page = pn.Column()
        
        # Config
        self._config_editor = pn.widgets.JSONEditor(mode="form")
        
        # event listeners
        def _select_this_tab(event):
            self._parent.main_layout.visible = False
            for k, v in self._parent._tabs.items():
                v.layout.visible = self._name == k
            
        self._tab_button.on_click(_select_this_tab)
        
        def _select_user_tab(event):
            if event.new in self._users:
                for k, v in self._users.items():
                    v.layout.visible = k == event.new
        
        def _update_config(event):
            self._config.data = event.new
            self._config.save()
        
        self._account_selector.param.watch(_select_user_tab, "value")
        self._config_editor.param.watch(_update_config, "value")
        
        self._overview_page = pn.Column(
            pn.Row(self._account_selector),
            self._active_account_page
        )
        self._layout_tabs = pn.Tabs(
            ("Overview", self._overview_page),
            ("Config", self._config_page)
        )
        
        self.layout = pn.Column(
            pn.pane.Markdown("# **" + self._name + "**"),
            self._text_labels,
            self._layout_tabs,
            name=self._name
        )
        self.layout.visible = False
        
    @property
    def _config_page(self) -> pn.Column:
        self._config.load()
        self._config_editor.value = self._config.data
        return self._config_editor
    
    def add_user(self, name: str) -> WebUserTab:
        created = self._users.get(name)
        if created:
            return created
        
        user_tab = WebUserTab(self, name)
        
        if len(self._account_selector.options) == 0:
            self._account_selector.value = name
            user_tab.layout.visible = True
            
        self._active_account_page.append(user_tab.layout)
        self._account_selector.options = self._account_selector.options + [name]
        self._users.update({name: user_tab})
        
        return user_tab

class WebPanel:
    def __init__(self, port: int = 8888, dev: bool = False) -> None:
        self._port = port
        self._dev = dev

        self._background = "#1d1d1d"
        self._accent = "#942cd0"

        self._reserved_tabs = [
            "General"
        ]

        self._main_tab_button = pn.widgets.Button(
            name="General", 
            button_type="primary"
        )
        def _select_this_tab(event):
            self.main_layout.visible = True
            for v in self._tabs.values():
                v.layout.visible = False
            
        self._main_tab_button.on_click(_select_this_tab)

        self.main_terminal = pn.widgets.Terminal(
            "",
            options=dict(
                cursorBlink=False
            )
        )
        
        self.stop_requested = False
        self.active_time = None
        self.restart_amount = 0
        self.restarting_in = None
        self.info_placeholders = "Active for: {active_time}\nRestarts amount: {restart_amount}\nRestarting in: {restarting_in}"
        self.info_label = pn.pane.Markdown("Initalizing...")
        self.restart_button = pn.widgets.Button(name="Restart", button_type="primary")
        self.stop_button = pn.widgets.Button(name="Stop", button_type="primary")
        self.restart_button.disabled = True
        self.stop_button.disabled = True
    
        def restart_callback(event = None):
            self.restart_button.disabled = True
            self.stop_button.disabled = True
            self.restarting_in = datetime.now()
        def stop_callback(event = None):
            self.stop_requested = True
            restart_callback()
    
        self.restart_button.on_click(restart_callback)
        self.stop_button.on_click(stop_callback)
    
        self.main_layout = pn.Column(
            pn.pane.Markdown("# **General**"),
            pn.Row(self.info_label, pn.Row(self.restart_button, self.stop_button)),
            self.main_terminal
        )

        self.sidebar = pn.Column(
            self._main_tab_button
        )
        self.main_area = pn.Column(
            self.main_layout
        )

        self.layout = pn.template.FastListTemplate(
            title="UNITAPPER",
            sidebar=[self.sidebar],
            main=[self.main_area],
            theme_toggle=False,
            theme=pn.template.DarkTheme,
            accent=self._accent,
        )
        
        self._tabs = {}
        
        self._served_instance = None

    async def main_page_handler(self) -> None:
        try:
            used_instance = self._served_instance
            while self._served_instance == used_instance:
                if self.active_time:
                    date_now = datetime.now()
                    
                    if not self.restarting_in:
                        restarting_in = "disabled"
                    
                    if isinstance(self.restarting_in, str):
                        restarting_in = self.restarting_in
                    
                    elif self.restarting_in < date_now:
                            restarting_in = "Stopping scripts..."
                    else:
                        restarting_in = str(self.restarting_in - date_now).split(".")[0]
                        
                    self.info_label.object = (
                        self.info_placeholders.format(
                            active_time=str(date_now - self.active_time).split(".")[0],
                            restart_amount=self.restart_amount,
                            restarting_in=restarting_in
                        )
                    )
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    def write(self, text: str) -> None:
        self.main_terminal.write(text + "\n")

    def start(self, show: bool = False) -> None:
        self._served_instance = pn.serve(
            self.layout,
            port=self._port,
            admin=self._dev,
            show=show,
            address="0.0.0.0",
            allow_websocket_origin=["*"],
            threaded=True,
            start=True,
            title="UNITAPPER",
        )
        try:
            asyncio.gather(self.main_page_handler())
        except asyncio.CancelledError:
            pass
    
    def stop(self) -> None:
        if self._served_instance:
            self._served_instance.stop()
            self._served_instance = None
            
    def restart(self) -> None:
        self.restart_button.disabled = True
        self.stop_button.disabled = True
        self.stop()
        self.start()
        
    def add_tab(self, name: str) -> WebTab:
        created = self._tabs.get(name)
        if created:
            return created
        
        web_tab = WebTab(self, name)
            
        self.sidebar.append(web_tab._tab_button)
        self.main_area.append(web_tab.layout)
        self._tabs.update({name: web_tab})
        
        return web_tab

webpanel = WebPanel(8888)