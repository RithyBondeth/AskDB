"""Create a small table in a disposable database for the live connection tests.

    uv run python tests/seed_live_db.py "$ASKDB_TEST_POSTGRES_URL"

CI runs this against its Postgres and MySQL service containers. It writes, so it
connects without AskDB's read-only settings; never point it at real data.
"""

from __future__ import annotations

import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

DRIVERS = {"postgres": "postgresql+psycopg", "postgresql": "postgresql+psycopg",
           "mysql": "mysql+pymysql", "mariadb": "mariadb+pymysql"}  # fmt: skip


def main(url: str) -> None:
    parsed = make_url(url)
    engine = create_engine(parsed.set(drivername=DRIVERS[parsed.get_backend_name()]))
    for attempt in range(30):  # a fresh container may still be starting
        try:
            engine.connect().close()
            break
        except OperationalError:
            if attempt == 29:
                raise
            time.sleep(2)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS customer"))
        conn.execute(
            text(
                "CREATE TABLE customer (id INT PRIMARY KEY, name VARCHAR(50), country VARCHAR(20))"
            )
        )
        conn.execute(text("INSERT INTO customer VALUES (1, 'Ada', 'UK'), (2, 'Linus', 'FI')"))
    engine.dispose()
    print(f"Seeded {parsed.render_as_string(hide_password=True)}")


if __name__ == "__main__":
    main(sys.argv[1])
