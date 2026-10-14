"""Writes db/taxi_dump.sql: schema + lookup tables + zone boundaries + trips.

A full dump of the trip table is about a gigabyte, too big for a submission zip, so by
default only an evenly spaced sample of trips is included. Use --all for everything.

    python pipeline/dump_db.py               # roughly 20,000 trips (evenly spaced)
    python pipeline/dump_db.py --rows 50000  # roughly 50,000 trips
    python pipeline/dump_db.py --all         # every trip

Restore with:   sqlite3 new.db < db/taxi_dump.sql
"""
import argparse
import sqlite3

DB = "db/taxi.db"
OUT = "db/taxi_dump.sql"

# Parent tables first so foreign keys always point at rows that already exist
SMALL_TABLES = ["borough", "zone", "zone_boundary", "payment_type", "rate_code"]


def dump_rows(conn, out, table, where=""):
    """Write one INSERT per row. SQLite's quote() handles escaping for every data type."""
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    quoted = ", ".join(f"quote({c})" for c in cols)
    col_list = ", ".join(cols)
    count = 0
    for row in conn.execute(f"SELECT {quoted} FROM {table} {where}"):
        out.write(f"INSERT INTO {table} ({col_list}) VALUES ({', '.join(row)});\n")
        count += 1
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20000, help="how many trips to include")
    ap.add_argument("--all", action="store_true", help="include every trip")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    with open(OUT, "w", encoding="utf-8", newline="\n") as out:
        out.write("-- NYC taxi database dump (SQLite)\nPRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n\n")

        # Table definitions, exactly as stored in the database
        for (sql,) in conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
                "AND name NOT LIKE 'sqlite_%' ORDER BY rowid"):
            out.write(sql + ";\n")
        out.write("\n")

        for table in SMALL_TABLES:
            n = dump_rows(conn, out, table)
            print(f"{table}: {n} rows")

        total = conn.execute("SELECT COUNT(*) FROM trip").fetchone()[0]
        if args.all or args.rows >= total:
            where = ""
        else:
            step = max(total // args.rows, 1)          # keep every step-th trip: spread over the month
            where = f"WHERE trip_id % {step} = 0"
        n = dump_rows(conn, out, "trip", where)
        print(f"trip: {n:,} of {total:,} rows")

        # Indexes, so a restored database performs the same as the original
        out.write("\n")
        for (sql,) in conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"):
            out.write(sql + ";\n")
        out.write("\nCOMMIT;\n")
    conn.close()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()