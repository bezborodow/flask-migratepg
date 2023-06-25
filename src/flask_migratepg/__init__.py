from flask import Blueprint, current_app
import psycopg
import importlib.util
import os


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
    spec.loader.exec_module(module)

    with psycopg.ClientCursor(conn) as cur:
        if not begin(cur, e.name):
            return
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

    def init(self, app):
        bp = Blueprint('migrate', __name__)

        @bp.cli.command('execute')
        def execute():
            conninfo = current_app.config.get('PSYCOPG_CONNINFO')
            with psycopg.connect(conninfo) as conn:
                init(conn)

                migrations = os.path.join(os.path.dirname(__file__), '../database/migrations/')
                with os.scandir(migrations) as d:
                    l = list(d)
                    l.sort(key = lambda e: e.name)
                    for e in l:
                        if not e.is_file():
                            continue
                        if e.name.startswith('.'):
                            continue
                        if e.name.endswith('.sql'):
                            migrate_sql(conn, e)
                        if e.name.endswith('.py'):
                            migrate_py(conn, e)

            print('Done.')

        app.register_blueprint(bp)
