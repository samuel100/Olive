# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
from pathlib import Path
from test.unit_test.utils import create_dummy_dataloader, get_pytorch_model_dummy_input, pytorch_model_loader
from unittest.mock import MagicMock, patch

import pytest

from olive.data.component.load_dataset import dummy_dataset
from olive.data.config import DataComponentConfig, DataConfig
from olive.data.registry import Registry
from olive.resource_path import create_resource_path
from olive.workflows import run as olive_run

# pylint: disable=redefined-outer-name


@Registry.register_post_process()
def post_processing_func_for_test(output):
    return output.argmax(axis=1)


def get_dataloader_config():
    return {
        "input_model": {
            "type": "PyTorchModel",
            "config": {
                "model_loader": pytorch_model_loader,
                "dummy_inputs_func": get_pytorch_model_dummy_input,
                "io_config": {"input_names": ["input"], "output_names": ["output"], "input_shapes": [(1, 1)]},
            },
        },
        "data_configs": [
            {
                "name": "test_data_config",
                "type": "DummyDataContainer",
                "load_dataset_config": {
                    "type": "dummy_dataset",
                    "params": {"data_dir": "data", "input_shapes": [(1, 1)], "max_samples": 1},
                },
            }
        ],
        "evaluators": {
            "common_evaluator": {
                "metrics": [
                    {
                        "name": "accuracy",
                        "type": "accuracy",
                        "sub_types": [
                            {
                                "name": "accuracy_score",
                                "priority": 1,
                                "metric_config": {"num_classes": 10, "task": "multiclass"},
                            }
                        ],
                        "data_config": "test_data_config",
                        "user_config": {
                            "post_processing_func": post_processing_func_for_test,
                        },
                    }
                ]
            }
        },
        "passes": {
            "onnx_conversion": {"type": "OnnxConversion", "config": {"target_opset": 13}},
            "perf_tuning": {
                "type": "OrtPerfTuning",
                "config": {
                    "dataloader_func": create_dummy_dataloader,
                    "batch_size": 16,
                    "data_dir": "data",
                },
            },
        },
        "engine": {
            "search_strategy": {"execution_order": "joint", "search_algorithm": "exhaustive"},
            "evaluator": "common_evaluator",
            "clean_cache": True,
            "output_dir": "./cache",
            "cache_dir": "./cache",
        },
    }


def get_data_config():
    return {
        "input_model": {
            "type": "PyTorchModel",
            "config": {
                "model_loader": pytorch_model_loader,
                "dummy_inputs_func": get_pytorch_model_dummy_input,
                "io_config": {"input_names": ["input"], "output_names": ["output"], "input_shapes": [(1, 1)]},
            },
        },
        "data_configs": [
            {
                "name": "test_data_config",
                "type": "DummyDataContainer",
                "load_dataset_config": {
                    "type": "dummy_dataset",
                    "params": {"data_dir": "data", "input_shapes": [(1, 1)], "max_samples": 1},
                },
                "post_process_data_config": {"type": "post_processing_func_for_test"},
            }
        ],
        "evaluators": {
            "common_evaluator": {
                "metrics": [
                    {
                        "name": "accuracy",
                        "type": "accuracy",
                        "sub_types": [
                            {
                                "name": "accuracy_score",
                                "priority": 1,
                                "metric_config": {"num_classes": 10, "task": "multiclass"},
                            }
                        ],
                        # reference to data_config defined in global data_configs
                        "data_config": "test_data_config",
                    }
                ]
            }
        },
        "passes": {
            "onnx_conversion": {"type": "OnnxConversion", "config": {"target_opset": 13}},
            "perf_tuning": {
                "type": "OrtPerfTuning",
                "config": {
                    # "data_config": "test_data_config"
                    # This is just demo purpose to show how to use data_config in passes
                    "data_config": DataConfig(
                        name="test_data_config_inlined",
                        type="DummyDataContainer",
                        load_dataset_config=DataComponentConfig(
                            type="dummy_dataset",
                            params={"data_dir": "perfdata", "input_shapes": [(1, 1)], "max_samples": 1},
                        ),
                        post_process_data_config=DataComponentConfig(type="post_processing_func_for_test"),
                    )
                },
            },
        },
        "engine": {
            "search_strategy": {"execution_order": "joint", "search_algorithm": "exhaustive"},
            "evaluator": "common_evaluator",
            "clean_cache": True,
            "output_dir": "./cache",
            "cache_dir": "./cache",
        },
    }


def concat_data_dir(data_root, data_dir):
    if data_root is None:
        pass
    elif data_root.startswith("azureml://"):
        data_dir = data_root + "/" + data_dir
    else:
        data_dir = str(Path(data_root) / data_dir)

    return data_dir


@pytest.fixture(params=[None, "azureml://CIFAR-10/1", "local"])
def config(tmpdir, request):
    config_obj = get_dataloader_config()

    data_root = request.param
    if data_root is not None:
        if data_root == "local":
            tmpdir.mkdir("data")
            data_root = str(tmpdir)
        config_obj["data_root"] = data_root

    return config_obj


@patch("olive.cache.get_local_path")
@pytest.mark.parametrize("is_cmdline", [True, False])
def test_data_root_for_dataloader_func(mock_get_local_path, config, is_cmdline):
    mock_get_local_path.side_effect = lambda x, cache_dir: x.get_path()
    if is_cmdline:
        data_root = config.pop("data_root", None)
        best = olive_run(config, data_root=data_root)
    else:
        data_root = config.get("data_root")
        best = olive_run(config)

    data_dir = concat_data_dir(data_root, "data")
    mock_get_local_path.assert_called_with(create_resource_path(data_dir), ".olive-cache")
    assert best is not None


@pytest.fixture(params=[None, "azureml://CIFAR-10/1", "local"])
def data_config(tmpdir, request):
    config_obj = get_data_config()

    data_root = request.param
    if data_root is not None:
        if data_root == "local":
            tmpdir.mkdir("data")
            tmpdir.mkdir("perfdata")
            data_root = str(tmpdir)
        config_obj["data_root"] = data_root

    return config_obj


@patch("olive.data.registry.inspect")
@patch("olive.cache.get_local_path")
def test_data_root_for_dataset(mock_get_local_path, mock_inspect, data_config):
    mock_get_local_path.side_effect = lambda x, cache_dir: x.get_path()

    # Mock inspect.getfile and inspect.getsourcelines to return dummy values
    mock_inspect.getfile = MagicMock(return_value="dummy")
    mock_inspect.getsourcelines = MagicMock(return_value=("dummy", 1))

    config_obj = data_config
    data_root = config_obj.get("data_root")

    mock = MagicMock(side_effect=dummy_dataset)
    Registry.register_dataset("dummy_dataset")(mock)
    best = olive_run(config_obj)
    mock.assert_called_with(data_dir=concat_data_dir(data_root, "data"), input_shapes=[(1, 1)], max_samples=1)
    if data_root is None:
        mock.assert_any_call(
            data_dir=concat_data_dir(data_root, "perfdata"),
            input_shapes=[(1, 1)],
            input_names=None,
            input_types=None,
            max_samples=1,
        )
    else:
        mock.assert_any_call(data_dir=concat_data_dir(data_root, "perfdata"), input_shapes=[(1, 1)], max_samples=1)
    assert best is not None
