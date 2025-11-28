import argparse
import os
from common.script import main as common_main
from pre_script import main as pre_main
from post_script import main as post_main


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=str, required=True)
    args = parser.parse_args()

    experiment_name = os.path.basename(os.path.dirname(__file__))
    print(f"Stage: {args.stage}, Experiment: {experiment_name}")

    pre_main(args.stage)
    common_main(args.stage)
    post_main(args.stage)