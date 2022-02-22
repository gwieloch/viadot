from prefect import Task
from ..sources import ASELite
from typing import Any, Dict, List
from prefect.tasks.secrets import PrefectSecret
from .azure_key_vault import AzureKeyVaultSecret
from viadot.config import local_config
import json
from viadot.sources.azure_sql import AzureSQL


class ASELiteToDF(Task):
    def __init__(
        self, credentials: Dict[str, Any] = None, db_name: str = None, query: str =None, *args, **kwargs
    ):
        self.credentials = credentials
        self.db_name = db_name
        self.query = query

        super().__init__(
            name="aselite",
            *args,
            **kwargs,
        )

    def __call__(self, *args, **kwargs):
        """Download aselite to df"""
        return super().__call__(*args, **kwargs)

    def run(
        self,
        credentials: Dict[str, Any] = None,
        db_name: str = None,
        query: str = None,
        if_empty: str = None,
        credentials_secret: str = None,
        vault_name: str = None,
    ):

        if not credentials_secret:
            try:
                credentials_secret = PrefectSecret("xxxxxxxxxxxxxxxxxxxxxxxx").run()
            except ValueError:
                pass

        if credentials_secret:
            credentials_str = AzureKeyVaultSecret(
                credentials_secret, vault_name=vault_name
            ).run()
            credentials = json.loads(credentials_str)
        else:
            credentials = local_config.get("ASLite_SQL")

        ase = AzureSQL(credentials=credentials)
        ase.conn_str
        ase.con
        final_df = ase.to_df(self.query)
        return final_df
