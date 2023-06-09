# Copyright 2022 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import NamedTuple
from kfp.v2.dsl import Dataset, Output, component
from pathlib import Path


@component(
    base_image="python:3.7",
    packages_to_install=["google-cloud-bigquery==2.30.0"],
    output_component_file=str(Path(__file__).with_suffix(".yaml")),
)
def extract_bq_to_dataset(
    bq_client_project_id: str,
    source_project_id: str,
    dataset_id: str,
    table_name: str,
    dataset: Output[Dataset],
    dataset_location: str = "EU",
    extract_job_config: dict = None,
    file_pattern: str = None,
) -> NamedTuple("Outputs", [("dataset_gcs_prefix", str), ("dataset_gcs_uri", list)]):
    """
    Extract BQ table in GCS.
    Args:
        bq_client_project_id (str): project id that will be used by the bq client
        source_project_id (str): project id from where BQ table will be extracted
        dataset_id (str): dataset id from where BQ table will be extracted
        table_name (str): table name (without project id and dataset id)
        dataset (Output[Dataset]): output dataset artifact generated by the operation,
            this parameter will be passed automatically by the orchestrator
        dataset_location (str): bq dataset location. Defaults to "EU".
        extract_job_config (dict): dict containing optional parameters
            required by the bq extract operation. Defaults to None.
            See available parameters here
            https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.job.ExtractJobConfig.html # noqa
        file_pattern (str): Exporting data into one or more files. If empty, then table data
            is exported to a single file. For multiple files and allowed pattern, see:
            https://cloud.google.com/bigquery/docs/exporting-data#exporting_data_into_one_or_more_files # noqa

    Returns:
        Outputs (NamedTuple (str, list)): Output dataset directory and its  GCS uri.
    """

    import logging
    import os
    from google.cloud.exceptions import GoogleCloudError
    from google.cloud import bigquery

    full_table_id = f"{source_project_id}.{dataset_id}.{table_name}"

    if extract_job_config is None:
        extract_job_config = {}

    table = bigquery.table.Table(table_ref=full_table_id)
    job_config = bigquery.job.ExtractJobConfig(**extract_job_config)
    client = bigquery.client.Client(
        project=bq_client_project_id, location=dataset_location
    )

    # if file_pattern is provided, join dataset.uri with file_pattern
    dataset_uri = dataset.uri
    if file_pattern:
        dataset_uri = os.path.join(dataset.uri, file_pattern)
    dataset_directory = os.path.dirname(dataset_uri)

    logging.info(f"Extract table {table} to {dataset_uri}")
    extract_job = client.extract_table(
        table,
        dataset_uri,
        job_config=job_config,
    )

    try:
        result = extract_job.result()
        logging.info("Table extracted, result: {}".format(result))
    except GoogleCloudError as e:
        logging.error(e)
        logging.error(extract_job.error_result)
        logging.error(extract_job.errors)
        raise e

    return (dataset_directory, [dataset_uri])
