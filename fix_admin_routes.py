import re

with open("pickaladder/admin/routes.py", "r") as f:
    content = f.read()

content = content.replace('        return redirect(url_for(".dashboard"))', '        flash("Faker module is not installed.", "danger")\n        return redirect(url_for(".dashboard"))')

with open("pickaladder/admin/routes.py", "w") as f:
    f.write(content)
