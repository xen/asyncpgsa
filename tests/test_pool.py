import asyncpgsa
import pytest
import sqlalchemy as sa

from . import HOST, PORT, USER, PASS, DB_NAME


@pytest.fixture(scope='function')
def pool(event_loop):
    _pool = event_loop.run_until_complete(
        asyncpgsa.create_pool(
            host=HOST,
            port=PORT,
            database=DB_NAME,
            user=USER,
            password=PASS,
            min_size=1,
            max_size=10
        )
    )
    yield _pool


async def test_pool_basic(pool):
    con = await pool.acquire()
    result = await con.fetch('SELECT * FROM sqrt(16)')
    assert result[0]['sqrt'] == 4.0
    await pool.release(con)


async def test_pool_connection_transaction_context_manager(pool):
    async with pool.transaction() as conn:
        result = await conn.fetch('SELECT * FROM sqrt(16)')

    assert result[0]['sqrt'] == 4.0


async def test_use_sqlalchemy_with_escaped_params(pool):
    """
    Use sqlalchemy with escaped params
    Make sure that the escaped parameters get used in the right order
    :return:
    """
    query = sa.select('*') \
        .select_from(sa.text('sqrt(:num) as a')) \
        .select_from(sa.text('sqrt(:a2) as b')) \
        .select_from(sa.text('sqrt(:z3) as c')) \
        .params(num=16, a2=36, z3=25)
    async with pool.transaction() as conn:
        result = await conn.fetch(query)

    row = result[0]
    assert row['a'] == 4.0
    assert row['b'] == 6.0
    assert row['c'] == 5.0


async def test_use_sa_core_objects(pool):
    pg_tables = sa.Table(
        'pg_tables', sa.MetaData(),
        sa.Column('schemaname'),
        sa.Column('tablename'),
        sa.Column('tableowner'),
        sa.Column('tablespace'),
        sa.Column('hasindexes')
    )

    query = pg_tables.select().where(pg_tables.c.schemaname == 'pg_catalog')
    async with pool.transaction() as conn:
        result = await conn.fetch(query)

    for row in result:
        # just making sure none of these throw KeyError exceptions
        assert isinstance(row['schemaname'], str)
        assert 'tablename' in row
        assert 'tableowner' in row
        assert 'tablespace' in row
        assert 'hasindexes' in row


async def test_with_without_async_should_throw_exception(pool):
    try:
        with pool.transaction() as conn:
            result = await conn.fetch('SELECT * FROM sqrt(16)')

        raise Exception('Should have thrown RuntimeError')
    except RuntimeError as e:
        assert str(e) == 'Must use "async with" for a transaction'


async def test_falsyness_of_rows_on_fetch(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM pg_stat_activity '
                                'WHERE pid=400')
        assert bool(rows) == False
