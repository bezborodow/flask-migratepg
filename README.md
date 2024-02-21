# PostgreSQL Database Migrations for Flask with Psycopg

## Synopsis

`flask-migratepg` is a simple migrations tool for Flask and [Psycopg 3](https://www.psycopg.org/psycopg3/).

 1. Install and setup the Flask extension.
 2. Place SQL migrations under the subdirectory `database/migrations/`.
 3. Execute migrations with the command **`flask migrate execute`**.

## Installation

```
$ pip install flask-migratepg
```

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

## Usage

Create a new migration SQL file:

```
$ flask migrate --help
$ flask migrate new --help
$ flask migrate new migration_name
```

Then to run migrations:

```
$ flask migrate execute --help
$ flask migrate execute
```

This will run migrations in alphabetical order and track them in a migrations table.

If there is a failure, the transaction will be rolled back.

### Migration Files

Migrations are placed under `database/migrations/` as either an **SQL** or **Python** file
(that is, with an `.sql` or `.py` filename extension respectively.)

The recommended filename format is `YYMMDD_NNN_migration_name.sql`, for example, `20240219_001_add_table_accounts.sql`.

#### SQL (`.sql`) Migrations

An SQL migration file will be executed. Statements are separated as per standard SQL conventions with a semicolon.

These are just plain-text standard SQL files. Comments (lines beginning with `-- `) will be ignored. 

#### Python (`.py`) Migrations

A Python file will be executed.

An optional method `migrate(conn)` is available. If this method is
present, it will be called with a database connection handle as the parameter; otherwise,
the Python script will be executed normally.

An example of the method:

````python
def migrate(conn):
    cur = conn.cursor()
    # ...
````
