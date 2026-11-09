import yaml
import os


def load_yaml(path):

    # Cloud platforms can point the application at an injected secret file
    # without changing the source tree.
    if path == "config.yaml":
        path = os.getenv("JOB_RADAR_CONFIG_PATH", path)

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return yaml.safe_load(f)
