from pathlib import Path

from duckdb import BinderException
import pandas as pd
import pytest
from viadot.sources.duckdb import DuckDB


TABLE = "test_table"
SCHEMA = "test_schema"
TABLE_MULTIPLE_PARQUETS = "test_multiple_parquets"
DATABASE_PATH = "test_db_123.duckdb"


@pytest.fixture(scope="module")
def duckdb():
    duckdb = DuckDB(credentials={"database": DATABASE_PATH, "read_only": False})
    yield duckdb
    Path(DATABASE_PATH).unlink()


def test_create_table_from_parquet(duckdb, TEST_PARQUET_FILE_PATH):
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH
    )
    df = duckdb.to_df(f"SELECT * FROM {SCHEMA}.{TABLE}")  # noqa: S608
    assert df.shape[0] == 3
    duckdb.drop_table(TABLE, schema=SCHEMA)
    duckdb.run_query(f"DROP SCHEMA {SCHEMA}")


def test_create_table_from_parquet_append(duckdb, TEST_PARQUET_FILE_PATH):
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH
    )
    df = duckdb.to_df(f"SELECT * FROM {SCHEMA}.{TABLE}")  # noqa: S608
    assert df.shape[0] == 3

    # now append
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH, if_exists="append"
    )
    df = duckdb.to_df(f"SELECT * FROM {SCHEMA}.{TABLE}")  # noqa: S608
    assert df.shape[0] == 6

    duckdb.drop_table(TABLE, schema=SCHEMA)
    duckdb.run_query(f"DROP SCHEMA {SCHEMA}")


def test_create_table_from_parquet_delete(duckdb, TEST_PARQUET_FILE_PATH):
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH
    )
    df = duckdb.to_df(f"SELECT * FROM {SCHEMA}.{TABLE}")  # noqa: S608
    assert df.shape[0] == 3

    df = pd.DataFrame.from_dict(
        data={
            "country": ["italy", "germany", "spain"],
            "sales": [100, 50, 80],
            "color": ["red", "blue", "grren"],
        }
    )

    df.to_parquet("test_parquet.parquet")
    with pytest.raises(BinderException):
        duckdb.create_table_from_parquet(
            schema=SCHEMA, table=TABLE, path="test_parquet.parquet", if_exists="delete"
        )

    duckdb.drop_table(TABLE, schema=SCHEMA)
    duckdb.run_query(f"DROP SCHEMA {SCHEMA}")
    Path("test_parquet.parquet").unlink()


def test_create_table_from_multiple_parquet(duckdb):
    # we use the two Parquet files generated by fixtures in conftest
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE_MULTIPLE_PARQUETS, path="*.parquet"
    )
    df = duckdb.to_df(f"SELECT * FROM {SCHEMA}.{TABLE_MULTIPLE_PARQUETS}")  # noqa: S608
    assert df.shape[0] == 6
    duckdb.drop_table(TABLE_MULTIPLE_PARQUETS, schema=SCHEMA)
    duckdb.run_query(f"DROP SCHEMA {SCHEMA}")


def test_check_if_table_exists(duckdb, TEST_PARQUET_FILE_PATH):
    assert not duckdb._check_if_table_exists(table=TABLE, schema=SCHEMA)
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH
    )
    assert duckdb._check_if_table_exists(TABLE, schema=SCHEMA)
    duckdb.drop_table(TABLE, schema=SCHEMA)


def test_run_query_query_with_comments(duckdb, TEST_PARQUET_FILE_PATH):
    duckdb.create_table_from_parquet(
        schema=SCHEMA, table=TABLE, path=TEST_PARQUET_FILE_PATH
    )
    output1 = duckdb.run_query(
        query=f"""
        --test
    SELECT * FROM {SCHEMA}.{TABLE}
    """,  # noqa: S608
        fetch_type="dataframe",
    )
    assert isinstance(output1, pd.DataFrame)

    output2 = duckdb.run_query(
        query=f"""
    SELECT * FROM {SCHEMA}.{TABLE}
    WHERE country = 'italy'
    """,  # noqa: S608
        fetch_type="dataframe",
    )
    assert isinstance(output2, pd.DataFrame)

    output3 = duckdb.run_query(
        query=f"""
    SELECT * FROM {SCHEMA}.{TABLE}
        ---test
    """,  # noqa: S608
        fetch_type="dataframe",
    )
    assert isinstance(output3, pd.DataFrame)

    duckdb.drop_table(TABLE, schema=SCHEMA)
