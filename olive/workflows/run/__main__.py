# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
import argparse
import sys

from olive.common.utils import set_tempdir
from olive.workflows import run
from olive.workflows.run.config import OliveConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Olive Workflow: Custom Run")
    parser.add_argument(
        "--olive-config",
        type=str,
        required=False,
        help=(
            "For advanced users. Path to optional Olive (json) config file "
            "with location of individual pass implementation and corresponding dependencies."
            "Configuration can also include user owned/proprietary pass implementations."
        ),
    )
    parser.add_argument("--run-config", "--config", type=str, help="Path to json config file", required=True)
    parser.add_argument("--setup", help="Whether run environment setup", action="store_true")
    parser.add_argument("--data-root", "--data_root", help="The data root path for optimization", required=False)
    parser.add_argument("--tempdir", type=str, help="Root directory for tempfile directories and files", required=False)

    args = parser.parse_args()

    if "--config" in sys.argv:
        print(  # noqa:T201
            "WARNING: Option '--config' is deprecated and will be removed in future versions. "
            "Use '--run-config' instead."
        )
    if "--data_root" in sys.argv:
        print(  # noqa:T201
            "WARNING: Option '--data_root' is deprecated and will be removed in future versions. "
            "Use '--data-root' instead."
        )

    set_tempdir(args.tempdir)

    if not args.olive_config:
        args.olive_config = OliveConfig.get_default_config_path()

    var_args = vars(args)
    del var_args["tempdir"]

    run(**var_args)
