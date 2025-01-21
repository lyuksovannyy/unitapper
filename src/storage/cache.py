from typing import Any

cached_data = {}
class cache:
    def __init__(self, name: str, session_name: str) -> None:
        self.name = name + "-" + session_name
        if not self.name in cached_data:
            cached_data[self.name] = {}
        
    def set(self, key: str, value: Any) -> None:
        cached_data[self.name][key] = value
        
    def add(self, key: str, value: int | float) -> None:
        cached_data[self.name][key] += value
        
    def get(self, key: str, default: Any = None) -> Any:
        if key not in cached_data[self.name]:
            cached_data[self.name][key] = default
            
        return cached_data[self.name][key]

    def __getattr__(self, value) -> Any:
        return cached_data[self.name][value]
    
    def __str__(self) -> dict:
        return str(cached_data[self.name])