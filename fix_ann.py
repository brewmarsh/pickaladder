import os
import re


def process_file(filepath) -> None:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content = content
    # Replace db: Any -> db: "firestore.Client"
    new_content = re.sub(r"db: Any", 'db: "firestore.Client"', new_content)
    # Replace *args: Any -> *args: object
    new_content = re.sub(r"\*args: Any", "*args: object", new_content)
    # Replace **kwargs: Any -> **kwargs: object
    new_content = re.sub(r"\*\*kwargs: Any", "**kwargs: object", new_content)
    # Replace user_doc: Any -> user_doc: "firestore.DocumentSnapshot"
    new_content = re.sub(
        r"user_doc: Any",
        'user_doc: "firestore.DocumentSnapshot"',
        new_content,
    )
    # Replace e: Exception) -> Any -> e: Exception) -> None
    new_content = re.sub(r"e: Exception\) -> Any", "e: Exception) -> None", new_content)

    if content != new_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)


for root, _, files in os.walk("pickaladder"):
    for file in files:
        if file.endswith(".py"):
            process_file(os.path.join(root, file))
