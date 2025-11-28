import os

def user_code(stage: str):
    pass # Implement your user code here

def main(stage: str):

    experiment_name = os.path.basename(os.path.dirname(__file__))
    print(f"Stage: {stage}, Experiment: {experiment_name}")
    user_code(stage)