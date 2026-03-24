import sqlite3
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

# Resolve the absolute path to the DB file so this class works
# regardless of which directory the server is launched from.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(_BASE_DIR, 'ecobim_materials.db')

class MaterialDatabaseManager:
    """
    Manages read access to the canonical SQLite materials library.

    The database file and its schema are owned by lab/setup_db.py.
    This class is purely a read layer — it does not create or seed
    any tables so that the two responsibilities stay cleanly separated.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Materials database not found at '{self.db_path}'. "
                "Run 'python lab/setup_db.py' to create it first."
            )

        # check_same_thread=False is required because FastAPI runs async
        # handlers on a thread pool and SQLite connections are not thread-safe
        # by default.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        logger.info(f"MaterialDatabaseManager connected to: {self.db_path}")

    def get_all_materials_as_dataframe(self) -> pd.DataFrame:
        """
        Loads the full materials table into a Pandas DataFrame for
        in-memory use by the LCA engine and ML recommender.
        """
        return pd.read_sql_query("SELECT * FROM materials", self.conn)

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("DB connection closed.")