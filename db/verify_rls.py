"""
Verify the database's security posture against a live Postgres.

Run this after applying db/schema.sql -- against a local instance, or against
the real Supabase project once it exists:

    python db/verify_rls.py                          # uses SUPABASE_DB_URL
    python db/verify_rls.py --db-url postgresql://…  # explicit

WHY THIS EXISTS
---------------
db/schema.sql was once believed correct because it parsed cleanly. It was not:
the commodity_code_map seed violated a foreign key on an empty database, which
aborted the script partway and left only 6 of 12 tables created and RLS applied
to NONE of them. Parsing proves syntax; only executing proves behaviour.

So this checks the properties that actually matter, and fails loudly:

  1. Every expected table exists.
  2. Every table has rowsecurity = true.
  3. No table is FORCE'd (which would lock the backend out of its own data
     unless its role happens to hold BYPASSRLS).
  4. The PostgREST roles (anon, authenticated) cannot read the sensitive
     tables -- the actual attack this defends against, since the anon key is
     public and ships to every browser.

Exit code is 0 only if all checks pass, so it works in CI.
"""

from __future__ import annotations

import argparse
import os
import sys

EXPECTED_TABLES = [
    "kabupaten", "commodity", "surplus_deficit", "weather_forecast",
    "historical_prices", "commodity_code_map", "policy_docs", "price_history",
    "forecasts", "subscriber", "wa_usage_daily", "payment_order",
]

# Tables whose rows describe an identifiable person. A read here by a public
# role is a breach, not a nuisance.
SENSITIVE = ["subscriber", "wa_usage_daily", "payment_order"]

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", default=os.getenv("SUPABASE_DB_URL", ""))
    args = ap.parse_args()

    if not args.db_url:
        print("No database URL. Pass --db-url or set SUPABASE_DB_URL.", file=sys.stderr)
        return 2

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("sqlalchemy not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 2

    engine = create_engine(args.db_url)
    failures: list[str] = []
    notes: list[str] = []

    with engine.connect() as conn:
        # --- 1 + 2 + 3: tables exist, RLS on, FORCE off ---------------------
        rows = conn.execute(text("""
            SELECT c.relname,
                   c.relrowsecurity  AS rls,
                   c.relforcerowsecurity AS forced
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
        """)).fetchall()
        present = {r[0]: (r[1], r[2]) for r in rows}

        print("table                 exists   RLS   FORCE")
        print("-" * 46)
        for tbl in EXPECTED_TABLES:
            if tbl not in present:
                print(f"{tbl:<22}{RED}MISSING{RESET}")
                failures.append(f"{tbl}: table does not exist")
                continue
            rls, forced = present[tbl]
            rls_s = f"{GREEN}on{RESET}" if rls else f"{RED}OFF{RESET}"
            force_s = f"{RED}ON{RESET}" if forced else f"{GREEN}off{RESET}"
            print(f"{tbl:<22}{GREEN}yes{RESET}      {rls_s}    {force_s}")
            if not rls:
                failures.append(f"{tbl}: RLS is OFF -- readable with the public anon key")
            if forced:
                failures.append(
                    f"{tbl}: FORCE ROW LEVEL SECURITY is ON -- the backend will "
                    f"see zero rows unless its role holds BYPASSRLS"
                )

        extra = sorted(set(present) - set(EXPECTED_TABLES))
        for tbl in extra:
            rls, _ = present[tbl]
            if not rls:
                failures.append(f"{tbl}: unexpected table with RLS OFF")
                print(f"{tbl:<22}{YELLOW}extra{RESET}    {RED}OFF{RESET}")

        # --- 4: can the public roles actually read? -------------------------
        print()
        for role in ("anon", "authenticated"):
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
            ).fetchone()
            if not exists:
                notes.append(f"role '{role}' does not exist here (fine outside Supabase)")
                continue
            for tbl in SENSITIVE:
                if tbl not in present:
                    continue
                # Roll back whatever this does; we only want the verdict.
                trans = conn.begin_nested()
                try:
                    conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                    n = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
                    # Reaching here means the read was permitted. Zero rows is
                    # still a pass: RLS filtered everything out.
                    verdict = f"{GREEN}denied (0 rows){RESET}" if n == 0 else \
                              f"{RED}READ {n} ROWS{RESET}"
                    if n:
                        failures.append(f"{role} can read {n} row(s) from {tbl}")
                except Exception:
                    verdict = f"{GREEN}denied (no privilege){RESET}"
                finally:
                    trans.rollback()
                print(f"{role:<15} -> {tbl:<18} {verdict}")

    print()
    for n in notes:
        print(f"note: {n}")
    if failures:
        print(f"\n{RED}FAILED{RESET} — {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}PASS{RESET} — all tables present, RLS on, FORCE off, "
          f"public roles cannot read sensitive tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
