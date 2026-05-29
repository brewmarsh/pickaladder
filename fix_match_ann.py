import re


def process_file(filepath, replacements) -> None:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for old, new in replacements:
        new_content = re.sub(old, new, new_content)

    if content != new_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)


# pickaladder/match/models.py
process_file(
    "pickaladder/match/models.py",
    [
        (r"user: Any", "user: object"),
        (r"-> Any:", "-> object:"),
        (r"default: Any = None", "default: object = None"),
    ],
)

# pickaladder/match/routes.py
process_file(
    "pickaladder/match/routes.py",
    [
        (r"-> Any:", '-> "Response":'),
    ],
)

# pickaladder/match/services/calculator.py
process_file(
    "pickaladder/match/services/calculator.py",
    [
        (r"default: Any\) -> Any:", "default: float) -> float:"),
    ],
)

# pickaladder/match/services/command.py
process_file(
    "pickaladder/match/services/command.py",
    [
        (r"date_input: Any", "date_input: str | datetime.datetime"),
        (r"s1_raw: Any, s2_raw: Any", "s1_raw: str | int, s2_raw: str | int"),
    ],
)

# pickaladder/match/services/record_service.py
process_file(
    "pickaladder/match/services/record_service.py",
    [
        (r"player_ref: Any", 'player_ref: "firestore.DocumentReference"'),
    ],
)
