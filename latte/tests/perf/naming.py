import frappe
from gevent import greenlet
import latte
import random, string, pymysql, gevent
from time import perf_counter
from pymysql import cursors

def get_size(table):
    frappe.db.sql(f'analyze table {table}')
    return frappe.db.sql(f'''
        SELECT
            round((data_length / 1024 / 1024), 2) `data_mb:Float:100`,
            round((index_length / 1024 / 1024), 2) `index_mb:Float:100`,
            round(((data_length + index_length) / 1024 / 1024), 2) `mb:Float:100`
        FROM
            information_schema.TABLES
        WHERE
            table_name = "{table}"
    ''', as_simple_dict=True)[0]

def create_tables():
    frappe.db.sql(f'''
        create or replace table test_redis
        (
            id varchar(240)
        )
    ''')

@frappe.whitelist()
def load_and_run(threads, runs):
    from werkzeug.wrappers import Response
    threads = int(threads)
    runs = int(runs)
    ins_str = ''.join(random.choice(string.ascii_lowercase) for i in range(10000))
    engines = (
        'innodb',
        'myisam',
        # 'aria',
        'rocksdb',
    )
    query = 'insert into {table}(data) values ("{data}")'
    query_map = {
        engine: query.format(table=f'test_{engine}', data=ins_str)
        for engine in engines
    }
    for engine in query_map:
        create_table(engine)

    def run(conn1, conn2, runs, query):
        start = perf_counter()
        greenlet = gevent.spawn(test_second_load, conn2)
        cursor = conn1.cursor()
        for i in range(runs):
            cursor._query(query)

        greenlet.kill(exception=StopIteration)
        greenlet.join()
        reads = greenlet.value
        conn1.close()

        return reads, ((perf_counter() - start) / runs)

    def test_second_load(conn):
        reads = 0
        cursor = conn.cursor()
        start = perf_counter()
        try:
            while True:
                cursor._query('select SQL_NO_CACHE * from `tabNote`')
                reads += 1
        except StopIteration:
            conn.close()
            return reads / (perf_counter() - start)

    def test(workers, runs, query):
        greenlets = []
        for i in range(workers):
            conn1 = pymysql.connect( host=frappe.db.host, user=frappe.db.user, password=frappe.db.password,
                port=int(frappe.db.port), charset='utf8mb4', use_unicode=True,
                conv=latte.database_utils.connection_pool.conversions, db=frappe.db.db_name, autocommit=1,
            )
            conn2 = pymysql.connect( host=frappe.db.host, user=frappe.db.user, password=frappe.db.password,
                port=int(frappe.db.port), charset='utf8mb4', use_unicode=True,
                conv=latte.database_utils.connection_pool.conversions, db=frappe.db.db_name, autocommit=1,
            )
            greenlets.append(gevent.spawn(run, conn1, conn2, runs, query))

        for g in greenlets:
            g.join()

        return {
            'per_insert_ms': (sum(g.value[1] for g in greenlets) / workers) * 1000,
            'reads_per_ms': sum(g.value[0] for g in greenlets) / 1000,
        }

    res = Response()
    data = frappe.as_json({
        engine: {**{
            'throughput': test(threads, runs, query_map[engine])
        }, **get_size(f'test_{engine}')}

        for engine, query in query_map.items()
    })
    print(data)
    res.data = data
    return res