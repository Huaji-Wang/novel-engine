import sqlite3

conn = sqlite3.connect(r"E:\projects\novel-engine\data\novel_engine.db")
for name, sql in conn.execute(
    "select name, sql from sqlite_master where type='table'"
):
    print(f"=== {name} ===")
    print(sql)
    print()
