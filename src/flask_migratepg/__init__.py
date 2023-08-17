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

        @bp.cli.command('schema')
        def schema():
            schema_path = current_app.config.get(
                    'MIGRATEPG_SCHEMA_PATH',
                    os.path.join(current_app.root_path, 'database/schema'))

            if not os.path.exists(schema_path):
                os.mkdir(schema_path)

            with self.connect() as conn:
                cur = conn.cursor()
                cur.row_factory = psycopg.rows.dict_row
                query = '''
                    select t.table_name,
                            json_agg(c) as columns
                    from information_schema.tables t
                    inner join (
                        select cl.table_name, cl.column_name, cl.udt_name
                        from information_schema.columns cl
                    ) c (table_name,column_name,udt_name) on (c.table_name = t.table_name)
                    where t.table_type = 'BASE TABLE'
                    and t.table_schema NOT IN ('pg_catalog', 'information_schema')
                    and t.table_catalog = current_database()
                    group by t.table_name
                '''

                cur.execute(query)
                while row := cur.fetchone():
                    schema_file = os.path.join(schema_path, row['table_name'] + '.json')
                    with open(schema_file, 'w') as f:
                         json.dump(row, f, indent=2)

            print('Done.')

        app.register_blueprint(bp)
