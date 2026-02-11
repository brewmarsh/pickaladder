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
        print(f"❌ ERROR: {rel_path} is missing!")
    else:
        print(f"✅ FOUND: {rel_path} ({os.path.getsize(path)} bytes)")

# 2. Check Layout Template for correct links
with open("pickaladder/templates/layout.html") as f:
    content = f.read()
    if "components.css" in content:
        print("❌ ERROR: layout.html still references components.css")
    else:
        print("✅ SUCCESS: layout.html no longer references components.css")

    css_files = [
        "layout-utils.css",
        "buttons.css",
        "avatars.css",
        "cards.css",
        "data-displays.css",
    ]
    for css_file in css_files:
        if css_file not in content:
            print(f"❌ ERROR: layout.html is missing link to {css_file}")
        else:
            print(f"✅ SUCCESS: layout.html has link to {css_file}")
