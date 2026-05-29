import os

required_files = [
    "static/css/layout-utils.css",
    "static/css/buttons.css",
    "static/css/avatars.css",
    "static/css/cards.css",
    "static/css/data-displays.css",
]

# 1. Check for physical files
for rel_path in required_files:
    path = os.path.join("pickaladder", rel_path)
    if not os.path.exists(path):
        pass
    else:
        pass

# 2. Check Layout Template for correct links
with open("pickaladder/templates/layout.html") as f:
    content = f.read()
    if "components.css" in content:
        pass
    else:
        pass

    css_files = [
        "layout-utils.css",
        "buttons.css",
        "avatars.css",
        "cards.css",
        "data-displays.css",
    ]
    for css_file in css_files:
        if css_file not in content:
            pass
        else:
            pass
