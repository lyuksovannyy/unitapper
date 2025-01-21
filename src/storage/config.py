import os
import json
from typing import Any

class config:
    def __init__(self, config_name: str) -> None:
        self.config_name = config_name
        self.path = "./configs/" + self.config_name + ".json"
        self.data = {}
        self._prepare()
        
    def _prepare(self) -> None:
        if not os.path.exists("./configs/"):
            os.makedirs("./configs/")
        
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("{}")
        
    def get(self, key: str, default: Any = None) -> Any:
        self._prepare()
        if key not in self.data:
            self.data[key] = default
        return self.data[key]
        
    def load(self) -> dict:
        self._prepare()
        with open(self.path, "r", encoding="utf-8") as file:
            self.data = json.load(file)
        return self.data
    
    def save(self) -> None:
        self._prepare()
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=3)
