"""
db/ — AgriFlow Postgres/Supabase data layer.

Import guard: this package is importable even without DATABASE_URL set.
Actual DB connections are deferred to db_loader.load_all().
"""
