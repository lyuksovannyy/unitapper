import aiosqlite
from .cache import cache

# Global database connector variable
_db = cache("__database__", "__root__")

class database:
    def __init__(self, table_name, session_name):
        self.table_name = table_name
        self.session_name = session_name

    async def _connect_db(self):
        global _db
        if _db.get("connector") is None:
            _db.set("connector", (await aiosqlite.connect('database.db')))
        return _db.get("connector")

    async def _ensure_table_and_column(self, column_name):
        try:
            db = await self._connect_db()
            await db.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT UNIQUE
                )
            ''')
            cursor = await db.execute(f"PRAGMA table_info({self.table_name})")
            columns = [col[1] for col in await cursor.fetchall()]
            if column_name not in columns:
                await db.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {column_name} TEXT")
            await db.commit()
        except:
            pass

    async def insert(self, column_name, new_value):
        await self._ensure_table_and_column(column_name)
        db = await self._connect_db()

        await db.execute(f'''
            INSERT INTO {self.table_name} (session_name, {column_name})
            VALUES (?, ?)
        ''', (self.session_name, new_value))
        await db.commit()

    async def get(self, column_name, default=None):
        await self._ensure_table_and_column(column_name)
        db = await self._connect_db()

        async with db.execute(f'''
            SELECT {column_name} FROM {self.table_name}
            WHERE session_name = ?
        ''', (self.session_name,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await self.insert(column_name, default)
            return default
            
        elif row[0] is None and default is not None:
            await self.update(column_name, default)
            return default
        
        return row[0]

    async def update(self, column_name, new_value):
        await self._ensure_table_and_column(column_name)
        db = await self._connect_db()

        await db.execute(f'''
            UPDATE {self.table_name}
            SET {column_name} = ?
            WHERE session_name = ?
        ''', (new_value, self.session_name,))
        await db.commit()

    async def close(self):
        global _db
        if _db.get("connector") is not None:
            await (_db.get("connector")).close()
            _db.set("connector", None)
