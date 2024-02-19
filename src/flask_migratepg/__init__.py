import os
import re
import click
import psycopg
import importlib.util
from flask import Blueprint, current_app
from datetime import datetime


def migrate_sql(conn, e):
    with open(e.path) as f:
        with psycopg.ClientCursor(conn) as cur:
            if not begin(cur, e.name):
                return
            cur.execute(f.read())
            finalise(cur, e.name)


def migrate_py(conn, e):
    module_name = os.path.splitext(e.name)[0]
    spec = importlib.util.spec_from_file_location(module_name, e.path)
    module = importlib.util.module_from_spec(spec)

    with psycopg.ClientCursor(conn) as cur:
        if not begin(cur, e.name):
            return
        spec.loader.exec_module(module)
        if hasattr(module, 'migrate'):
            module.migrate(conn)
        finalise(cur, e.name)


def begin(cur, name):
    cur.execute('select true from migrations where filename = %s',
                [ name ])
    if (cur.fetchone()):
        return False

    print(name)
    cur.execute('begin')
    return True


def finalise(cur, name):
    cur.execute('insert into migrations (filename) values (%s)',
                [ name ])
    cur.execute('commit')


def init(conn):
    table = '''
    create table if not exists migrations (
        migration_id serial not null,
        filename char(120) not null,
        migrated_at timestamp not null default current_timestamp,
        constraint migrations_primary primary key (migration_id),
        unique (filename)
    )
    '''
    cur = conn.cursor()
    cur.execute('begin')
    cur.execute(table)
    cur.execute('commit')


class MigratePg:
    def __init__(self, app=None):
        if app is not None:
            self.init(app)


    # Establish connection to the database.
    def connect(self):
        return psycopg.connect(
                current_app.config.get('PSYCOPG_CONNINFO'))


    # Where the migrations files are stored.
    def migrations_path(self):
        return current_app.config.get(
                'MIGRATIONS_PATH',
                os.path.join(current_app.root_path, 'database/migrations'))

    # Register command blueprints with Flask.
    def init(self, app):
        bp = Blueprint('migrate', __name__)


        @bp.cli.command('execute', help='Run migrations.')
        def execute():
            migrations_path = self.migrations_path()

            with self.connect() as conn:
                init(conn)

                # Check for new migrations files.
                with os.scandir(migrations_path) as d:
                    ls = list(d)
                    ls.sort(key = lambda e: e.name)
                    for e in ls:
                        if not e.is_file() or e.name.startswith('.'):
                            continue # Ignored file.

                        # SQL migration.
                        if e.name.endswith('.sql'):
                            migrate_sql(conn, e)

                        # Python migration.
                        if e.name.endswith('.py'):
                            migrate_py(conn, e)

            print('Done.')


        @bp.cli.command('new', help='Create a new migration file.')
        @click.argument('name')
        @click.option('--utc', is_flag=True, default=False, show_default=True,
                      help='Datestamp in UTC instead of local time.')
        @click.option('--py', is_flag=True, default=False, show_default=True,
                      help='Create a Python file instead of an SQL file.')
        def new(name, utc, py):
            # Directory.
            migrations_path = self.migrations_path()

            # Datestamp.
            if utc:
                now = datetime.utcnow()
            else:
                now = datetime.now()
            datestamp = now.date().strftime('%Y%m%d')

            # Order number.
            i = 1
            for f in os.listdir(migrations_path):
                if m := re.match(r'^([0-9]{8})_([0-9]{3})_(\w+)\.(sql|py)', f):
                    if datestamp == m.group(1):
                        i = int(m.group(2)) + 1 # Next daily number.
            number = str(i).rjust(3, '0')

            # Name
            name = re.sub(r'\W', '_', name) # Sanitize
            extension = 'py' if py else 'sql'

            # Create file.
            filename = f'{datestamp}_{number}_{name}.{extension}'
            filepath = f'{migrations_path}/{filename}'
            open(filepath, 'a').close()

            print(f'New file: {filepath}')


        app.register_blueprint(bp)
