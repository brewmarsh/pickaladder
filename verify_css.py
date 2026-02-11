import os

required_files = [
    'static/css/layout-utils.css',
    'static/css/buttons.css',
    'static/css/avatars.css',
    'static/css/cards.css',
    'static/css/data-displays.css'
]

# 1. Check for physical files
for f in required_files:
    path = os.path.join('pickaladder', f)
    if not os.path.exists(path):
        print(f"❌ ERROR: {f} is missing!")
    else:
        print(f"✅ FOUND: {f} ({os.path.getsize(path)} bytes)")

# 2. Check Layout Template for correct links
with open('pickaladder/templates/layout.html', 'r') as f:
    content = f.read()
    if 'components.css' in content:
        print("❌ ERROR: layout.html still references components.css")
    else:
        print("✅ SUCCESS: layout.html no longer references components.css")
    for css_file in ['layout-utils.css', 'buttons.css', 'avatars.css', 'cards.css', 'data-displays.css']:
        if css_file not in content:
            print(f"❌ ERROR: layout.html is missing link to {css_file}")
        else:
            print(f"✅ SUCCESS: layout.html has link to {css_file}")
