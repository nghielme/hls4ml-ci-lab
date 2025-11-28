import argparse
import os
from pathlib import Path
import sys

# Add repo root to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))


from common.script import main as common_main
from pre_script import main as pre_main
from post_script import main as post_main



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=str, required=True)
    args = parser.parse_args()

    experiment_name = os.path.basename(os.path.dirname(__file__))
    print(f"Stage: {args.stage}, Experiment: {experiment_name}")

    pre_main(args.stage, experiment_name)
    common_main(args.stage, experiment_name)
    post_main(args.stage, experiment_name)

if __name__ == "__main__":
    main()