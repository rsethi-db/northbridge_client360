"""Run SQL against the demo's Lakebase endpoint as the current CLI user. Usage: python scripts/pg.py "<sql>" [profile]"""
import json, subprocess, sys

import psycopg

PROFILE = sys.argv[2] if len(sys.argv) > 2 else "fevm-richasethi-febar"
EP = "projects/northbridge-client360/branches/production/endpoints/primary"
cli = lambda *a: json.loads(subprocess.check_output(["databricks", *a, "--profile", PROFILE, "-o", "json"]))
host = cli("postgres", "get-endpoint", EP)["status"]["hosts"]["host"]
token = cli("postgres", "generate-database-credential", EP)["token"]
user = cli("current-user", "me")["userName"]
with psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=token, sslmode="require", autocommit=True) as c:
    cur = c.execute(sys.argv[1])
    if cur.description:
        print("\t".join(d.name for d in cur.description))
        for r in cur.fetchall():
            print("\t".join(str(x) for x in r))
    else:
        print("OK", cur.statusmessage)
