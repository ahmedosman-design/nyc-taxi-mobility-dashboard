import sqlite3

c = sqlite3.connect("db/taxi.db")
print("trips:", c.execute("SELECT COUNT(*) FROM trip").fetchone()[0])
print("zones:", c.execute("SELECT COUNT(*) FROM zone").fetchone()[0])
for r in c.execute("""
    SELECT b.name, COUNT(*) FROM trip t
    JOIN zone z ON t.pu_zone_id = z.location_id
    JOIN borough b ON z.borough_id = b.borough_id
    GROUP BY b.name ORDER BY 2 DESC"""):
    print(r)