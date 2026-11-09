import yaml


all_boards = {}


for file_name in [

    "greenhouse_verified.yaml",

    "lever_verified.yaml",

    "ashby_verified.yaml"

]:

    try:

        with open(
            file_name,
            "r"
        ) as f:

            data = yaml.safe_load(
                f
            )

            all_boards.update(
                data
            )

    except:

        pass


with open(
    "verified_boards.yaml",
    "w"
) as f:

    yaml.dump(
        all_boards,
        f,
        sort_keys=False
    )


print(
    "verified_boards.yaml created"
)