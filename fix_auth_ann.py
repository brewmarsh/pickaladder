import re


def process_file(filepath):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content = content
    # Replace -> Any: with -> "Response":
    new_content = re.sub(r"-> Any:", '-> "Response":', new_content)

    if content != new_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {filepath}")


process_file("pickaladder/auth/routes.py")
process_file("pickaladder/auth/decorators.py")
