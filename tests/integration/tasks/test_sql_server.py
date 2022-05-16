import json
import logging
import inspect
import types
from viadot.tasks import SQLServerCreateTable
from viadot.tasks.azure_key_vault import AzureKeyVaultSecret
from prefect.tasks.secrets import PrefectSecret

SCHEMA = "sandbox"
TABLE = "test"


def test_sql_server_create_table_init():
    instance = SQLServerCreateTable()
    name = instance.__dict__["name"]
    assert inspect.isclass(SQLServerCreateTable)
    assert isinstance(instance, SQLServerCreateTable)
    assert name == "sql_server_create_table"


def test_sql_server_create_table(caplog):

    credentials_secret = PrefectSecret(
        "AZURE_DEFAULT_SQLDB_SERVICE_PRINCIPAL_SECRET"
    ).run()
    vault_name = PrefectSecret("AZURE_DEFAULT_KEYVAULT").run()
    azure_secret_task = AzureKeyVaultSecret()
    credentials_str = azure_secret_task.run(
        secret=credentials_secret, vault_name=vault_name
    )

    dtypes = {
        "date": "DATE",
        "name": "VARCHAR(255)",
        "id": "VARCHAR(255)",
        "weather": "FLOAT(24)",
        "rain": "FLOAT(24)",
        "temp": "FLOAT(24)",
        "summary": "VARCHAR(255)",
    }

    create_table_task = SQLServerCreateTable()
    with caplog.at_level(logging.INFO):
        create_table_task.run(
            schema=SCHEMA,
            table=TABLE,
            dtypes=dtypes,
            if_exists="replace",
            credentials=json.loads(credentials_str),
        )
        assert "Successfully created table" in caplog.text
