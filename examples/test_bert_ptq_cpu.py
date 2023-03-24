# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
import json
import os
import platform
from pathlib import Path

import pytest


@pytest.fixture()
def example_dir():
    return str(Path(__file__).resolve().parent / "bert_ptq_cpu")


@pytest.fixture(autouse=True)
def setup(example_dir):
    """setup any state specific to the execution of the given module."""
    cur_dir = str(Path(__file__).resolve().parent)
    os.chdir(example_dir)
    yield
    os.chdir(cur_dir)


def check_output(metrics):
    assert metrics is not None
    assert all([value > 0 for value in metrics])


@pytest.mark.parametrize("search_algorithm", ["tpe"])
@pytest.mark.parametrize("execution_order", ["joint"])
@pytest.mark.parametrize("system", ["local_system", "aml_system", "docker_system"])
@pytest.mark.parametrize("olive_json", ["bert_config.json"])
def test_bert(search_algorithm, execution_order, system, olive_json):
    if system == "docker_system" and platform.system() == "Windows":
        pytest.skip("Skip Linux containers on Windows host test case.")
    if system == "aml_system":
        pytest.skip("Skip AzureML test case.")
    if system == "docker_system":
        pytest.skip("Skip Docker test case until OSS done.")

    # TODO simplify the import structure for workflows.run
    from olive.workflows.run.run import run as olive_run

    olive_config = None
    with open(olive_json, "r") as fin:
        olive_config = json.load(fin)

    # update search strategy
    olive_config["engine"]["search_strategy"]["search_algorithm"] = search_algorithm
    olive_config["engine"]["search_strategy"]["execution_order"] = execution_order

    # set aml_system as dev
    olive_config["systems"]["aml_system"]["config"]["is_dev"] = True

    # update host and target
    olive_config["engine"]["host"] = system if system != "docker_system" else "local_system"
    olive_config["evaluators"]["common_evaluator"]["target"] = system

    best_execution = olive_run(olive_config)
    check_output(best_execution["metric"])
