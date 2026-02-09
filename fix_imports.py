path = "pickaladder/group/routes.py"
lines = open(path).readlines()
# Remove all lines from 30 to 40 if they contain utils
new_lines = []
skip = False
for line in lines:
    if "from .utils import" in line:
        skip = True
        continue
    if skip and ")" in line:
        skip = False
        continue
    if not skip:
        new_lines.append(line)

# Now insert the correct import at line 30
import_block = "from .utils import (\n    friend_group_members,\n    get_random_joke,\n    get_user_group_stats,\n    send_invite_email_background,\n)\n"
new_lines.insert(29, import_block)

with open(path, "w") as f:
    f.writelines(new_lines)
