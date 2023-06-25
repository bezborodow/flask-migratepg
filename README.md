# `flask-migratepg`: Database Migrations for Flask and PostgreSQL with Psycopg

This is a simple migrations tool for Flask and Psycopg.

Setup in application:

````python
from flask import Flask
from flask_migratepg import MigratePg
import os

app = Flask(__name__)
app.config.from_mapping(
    MIGRATIONS_PATH=os.path.abspath('database/migrations'),
    PSYCOPG_CONNINFO="dbname=example host=localhost user=example password=secret"
)
MigratePg(app)
````

Then to run migrations:

```
. venv/bin/activate
flask migrate execute
```

This will run migrations in alphabetical order and track them in a migrations table.

Migrations should be under `database/migrations` as either an **SQL** or **Python** file
(that is, with an `.sql` or `.py` filename extension resepectively.)

A Python migration must implement a method `migrate(conn)`. An example of this:

````python
def migrate(conn):
    cur = conn.cursor()
    # ...
    cur.execute('commit')
````
