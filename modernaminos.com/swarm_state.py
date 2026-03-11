import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

class SwarmState:
    def __init__(self, db_path="products.db"):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def init_db(self):
        with self.get_db() as db:
            # Augment products table if it exists
            columns_to_add = [
                "moa TEXT",
                "half_life TEXT",
                "side_effects TEXT",
                "leverage_score TEXT",
                "justification TEXT"
            ]
            for col in columns_to_add:
                try:
                    db.execute(f"ALTER TABLE products ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # State tracking tables
            db.execute('''
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    url_id INTEGER,
                    sub_agent TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error TEXT,
                    FOREIGN KEY(plan_id) REFERENCES plans(id)
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    artifact_key TEXT,
                    artifact_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )
            ''')

    def create_plan(self, description: str) -> int:
        with self.get_db() as db:
            cursor = db.execute(
                "INSERT INTO plans (description, status) VALUES (?, ?)", 
                (description, 'pending')
            )
            return cursor.lastrowid

    def update_plan_status(self, plan_id: int, status: str):
        completed_at = datetime.now() if status in ('completed', 'failed') else None
        with self.get_db() as db:
            db.execute(
                "UPDATE plans SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, plan_id)
            )

    def create_task(self, plan_id: int, url_id: int, sub_agent: str) -> int:
        with self.get_db() as db:
            cursor = db.execute(
                "INSERT INTO tasks (plan_id, url_id, sub_agent, status) VALUES (?, ?, ?, ?)",
                (plan_id, url_id, sub_agent, 'pending')
            )
            return cursor.lastrowid

    def update_task_status(self, task_id: int, status: str, error: str = None):
        completed_at = datetime.now() if status in ('completed', 'failed') else None
        with self.get_db() as db:
            db.execute(
                "UPDATE tasks SET status = ?, completed_at = ?, error = ? WHERE id = ?",
                (status, completed_at, error, task_id)
            )

    def save_artifact(self, task_id: int, key: str, value: str) -> int:
        with self.get_db() as db:
            cursor = db.execute(
                "INSERT INTO artifacts (task_id, artifact_key, artifact_value) VALUES (?, ?, ?)",
                (task_id, key, value)
            )
            return cursor.lastrowid
            
    def get_pending_urls(self):
        with self.get_db() as db:
            # Return URLs that haven't been successfully processed or are missing leverage_score
            return db.execute("SELECT * FROM products WHERE leverage_score IS NULL").fetchall()
