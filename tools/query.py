"""Query only the approved container mount; scripts are fixed exercises."""

import sys
from pathlib import Path

import duckdb

sql = "SELECT * FROM '/dataset/data.parquet' LIMIT 20"
if len(sys.argv) > 1:
    sql = Path(sys.argv[1]).read_text()
with duckdb.connect() as conn:
    conn.sql(sql).show()
