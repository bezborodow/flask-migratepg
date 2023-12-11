from flask import Blueprint, current_app
import psycopg
import importlib.util
import os
import json


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

    def connect(self):
        return psycopg.connect(
                current_app.config.get('PSYCOPG_CONNINFO'))

    def init(self, app):
        bp = Blueprint('migrate', __name__)

        @bp.cli.command('execute')
        def execute():
            migrations_path = current_app.config.get(
                    'MIGRATIONS_PATH',
                    os.path.join(current_app.root_path, 'database/migrations'))

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

        app.register_blueprint(bp)
