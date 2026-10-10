"""
database/db_connector.py
────────────────────────
Python ETL orchestrator to initialize DB schema and execute SQL cleaning pipelines.
"""

from pathlib import Path
from database.db_manager import DBManager
from utils.logger import get_logger

log = get_logger(__name__)

class DBConnector:
    def __init__(self):
        self.db = DBManager()
        self.base_dir = Path(__file__).resolve().parent

    def initialize_schema(self):
        schema_path = self.base_dir / "schema.sql"
        log.info(f"Applying DB Schema from {schema_path}...")
        self._execute_sql_file(schema_path)

    def run_cleaning_pipeline(self):
        cleaning_path = self.base_dir / "cleaning.sql"
        log.info(f"Executing ELT Cleaning pipeline from {cleaning_path}...")
        self._execute_sql_file(cleaning_path)

    def _execute_sql_file(self, filepath: Path):
        with open(filepath, "r", encoding="utf-8") as f:
            sql_content = f.read()

        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            conn.commit()
            log.info(f"Executed {filepath.name} successfully.")
        except Exception as e:
            conn.rollback()
            log.error(f"Error executing SQL file {filepath.name}: {e}")
            raise e
        finally:
            conn.close()

if __name__ == "__main__":
    connector = DBConnector()
    connector.initialize_schema()
    connector.run_cleaning_pipeline()