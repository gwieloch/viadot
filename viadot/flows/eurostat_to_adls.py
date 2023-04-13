import os
from pathlib import Path
from typing import Any, Dict, List

import pendulum
from prefect import Flow
from prefect.backend import set_key_value
from prefect.utilities import logging

from ..task_utils import (
    add_ingestion_metadata_task,
    df_get_data_types_task,
    df_map_mixed_dtypes_for_parquet,
    df_to_csv,
    df_to_parquet,
    dtypes_to_json_task,
    update_dtypes_dict,
)

from ..tasks import AzureDataLakeUpload, EurostatToDF

file_to_adls_task = AzureDataLakeUpload()
json_to_adls_task = AzureDataLakeUpload()

logger = logging.get_logger(__name__)


class EurostatToADLS(Flow):
    """Flow for downloading data from the Eurostat platform via HTTPS REST to a CSV or Parquet file.
    Then upload it to Azure Data Lake.
    """

    def __init__(
        self,
        name: str,
        dataset_code: str,
        params: dict = None,
        needed_columns: list = None,
        output_file_extension: str = ".parquet",
        adls_dir_path: str = None,
        local_file_path: str = None,
        adls_file_name: str = None,
        adls_sp_credentials_secret: str = None,
        overwrite_adls: bool = False,
        if_exists: str = "replace",
        *args: List[Any],
        **kwargs: Dict[str, Any],
    ):
        """
        Args:
            name (str): The name of the flow.
            dataset_code(str): The code of eurostat dataset that has to be upload - REQUIRED
            params (dict, optional):
                A dictionary with optional URL parameters. The key represents the parameter id, while the value is the code
                for a specific parameter, for example 'params = {'unit': 'EUR'}' where "unit" is the parameter that you would like to set
                and "EUR" is the code of the specific parameter. You can add more than one parameter, but only one code per parameter!
                So you CAN NOT provide list of codes as in example 'params = {'unit': ['EUR', 'USD', 'PLN']}'
                This parameter is REQUIRED in most cases to pull a specific dataset from the API.
                Both parameter and code has to provided as a string!
                Defaults to None.
            nedeed_columns (list): List of columns that are needed from DataFrame - works as filter,
                because we are pulling data frame with most of the colums.

            output_file_extension (str, optional): Output file extension - to allow selection of .csv for data
                    which is not easy to handle with parquet. Defaults to ".parquet".
            adls_dir_path (str, optional): Azure Data Lake destination folder/catalog path. Defaults to None.
            local_file_path (str, optional): Local destination path. Defaults to None.
            adls_file_name (str, optional): Name of file in ADLS. Defaults to None.
            adls_sp_credentials_secret (str, optional): The name of the Azure Key Vault secret containing a dictionary with
                ACCOUNT_NAME and Service Principal credentials (TENANT_ID, CLIENT_ID, CLIENT_SECRET) for the Azure Data Lake.
                Defaults to None.
            overwrite_adls (bool, optional): Whether to overwrite files in the lake. Defaults to False.
            if_exists (str, optional): What to do if the file exists. Defaults to "replace".
        """

        # EurostatToDF
        self.dataset_code = dataset_code
        self.params = params
        self.needed_columns = needed_columns

        # AzureDataLakeUpload
        self.overwrite = overwrite_adls
        self.adls_sp_credentials_secret = adls_sp_credentials_secret
        self.if_exists = if_exists
        self.output_file_extension = output_file_extension
        self.now = str(pendulum.now("utc"))

        self.local_file_path = (
            local_file_path or self.slugify(name) + self.output_file_extension
        )
        self.local_json_path = self.slugify(name) + ".json"
        self.adls_dir_path = adls_dir_path

        if adls_file_name is not None:
            self.adls_file_path = os.path.join(adls_dir_path, adls_file_name)
            self.adls_schema_file_dir_file = os.path.join(
                adls_dir_path, "schema", Path(adls_file_name).stem + ".json"
            )
        else:
            self.adls_file_path = os.path.join(
                adls_dir_path, self.now + self.output_file_extension
            )
            self.adls_schema_file_dir_file = os.path.join(
                adls_dir_path, "schema", self.now + ".json"
            )

        super().__init__(name=name, *args, **kwargs)

        self.gen_flow()

    @staticmethod
    def slugify(name):
        return name.replace(" ", "_").lower()

    def gen_flow(self) -> Flow:
        data_frame = EurostatToDF(
            dataset_code=self.dataset_code,
            params=self.params,
            needed_columns=self.needed_columns,
        )

        data_frame = data_frame.bind(flow=self)

        df_with_metadata = add_ingestion_metadata_task.bind(data_frame, flow=self)
        dtypes_dict = df_get_data_types_task.bind(df_with_metadata, flow=self)

        if self.output_file_extension == ".parquet":
            df_to_be_loaded = df_map_mixed_dtypes_for_parquet(
                df_with_metadata, dtypes_dict, flow=self
            )
            df_to_file = df_to_parquet.bind(
                df=df_to_be_loaded,
                path=self.local_file_path,
                if_exists=self.if_exists,
                flow=self,
            )
        else:
            df_to_file = df_to_csv.bind(
                df=df_with_metadata,
                path=self.local_file_path,
                if_exists=self.if_exists,
                flow=self,
            )

        file_to_adls_task.bind(
            from_path=self.local_file_path,
            to_path=self.adls_file_path,
            overwrite=self.overwrite,
            sp_credentials_secret=self.adls_sp_credentials_secret,
            flow=self,
        )

        dtypes_updated = update_dtypes_dict(dtypes_dict, flow=self)
        dtypes_to_json_task.bind(
            dtypes_dict=dtypes_updated, local_json_path=self.local_json_path, flow=self
        )

        json_to_adls_task.bind(
            from_path=self.local_json_path,
            to_path=self.adls_schema_file_dir_file,
            overwrite=self.overwrite,
            sp_credentials_secret=self.adls_sp_credentials_secret,
            flow=self,
        )

        file_to_adls_task.set_upstream(df_to_file, flow=self)
        json_to_adls_task.set_upstream(dtypes_to_json_task, flow=self)
        set_key_value(key=self.adls_dir_path, value=self.adls_file_path)
