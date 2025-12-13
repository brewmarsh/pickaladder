from playwright.sync_api import expect


def test_user_journey(app_server, page_with_firebase, mock_db):
    page = page_with_firebase
    base_url = app_server

    # Auto-accept dialogs (alerts, confirms)
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. Account creation (Admin)
    page.goto(f"{base_url}/auth/login")

    if "/auth/install" in page.url:
        page.fill("input[name='username']", "admin")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        page.fill("input[name='name']", "Admin User")
        page.click("input[value='Create Admin']")

        expect(page.locator("h2")).to_contain_text("Login")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        page.click("input[value='Login']")

    expect(page.locator("h3:has-text('Profile Information')")).to_be_visible(timeout=10000)

    # Logout
    page.click(".dropbtn")
    page.click("text=Logout")
    expect(page.locator("h2")).to_contain_text("Login")

    # 2. Register User 2
    page.click("text=Register")
    page.wait_for_url("**/auth/register")
    page.fill("input[name='username']", "user2")
    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    page.fill("input[name='confirm_password']", "MyPassword123")
    page.fill("input[name='name']", "User Two")
    page.fill("input[name='dupr_rating']", "3.5")
    page.click("input[value='Register']")

    # Now login as User Two
    expect(page.locator("h2")).to_contain_text("Login")
    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    page.click("input[value='Login']")

    expect(page.locator("h3:has-text('Profile Information')")).to_be_visible(timeout=10000)

    # 3. Add Friend (User 2 invites Admin)
    page.click("text=Friends")
    page.click("text=Find New Friends")

    page.fill("input[name='search']", "admin")
    page.click("input[value='Search']")

    # Click Add Friend for Admin User
    page.click("button:has-text('Add Friend')")
    expect(page.locator("button:has-text('Friend Request Sent')")).to_be_visible(timeout=5000)

    # Logout User 2, Login Admin
    page.click(".dropbtn")
    page.click("text=Logout")

    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    page.click("input[value='Login']")

    # Accept Friend Request
    page.click("text=Friends")
    expect(page.locator("text=user2")).to_be_visible()
    page.click("button:has-text('Accept')")
    expect(page.locator("text=user2")).to_be_visible()

    # 4. Create Group
    page.click("text=Groups")
    page.click("text=Create New Group")
    page.fill("input[name='name']", "Pickleballers")
    page.fill("input[name='location']", "Test Court")
    page.click("input[value='Create Group']")

    expect(page.locator("h1")).to_contain_text("Pickleballers")

    # 5. Invite Friend to Group
    page.select_option("select[name='friend']", value="user2")
    page.click("input[value='Invite Friend']")

    # Verify User 2 is added (Logout Admin, Login User 2)
    page.click(".dropbtn")
    page.click("text=Logout")

    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    page.click("input[value='Login']")

    # User 2 should see the group
    page.click("text=Groups")
    expect(page.locator("text=Pickleballers")).to_be_visible()

    # 6. Score Individual Game (User 2 vs Admin)
    page.goto(f"{base_url}/match/record")
    page.select_option("select[name='match_type']", value="singles")
    page.select_option("select[name='player2']", value="admin")
    page.fill("input[name='player1_score']", "11")
    page.fill("input[name='player2_score']", "9")
    page.click("input[value='Record Match']")

    # Check flash message
    expect(page.locator(".alert-success")).to_contain_text("Match recorded successfully")

    # 7. Score Group Game
    page.click("text=Groups")
    page.click("text=Pickleballers")
    page.click("a:has-text('Record a Match')")
    page.select_option("select[name='player2']", value="admin")
    page.fill("input[name='player1_score']", "5")
    page.fill("input[name='player2_score']", "11")
    page.click("input[value='Record Match']")

    expect(page.locator("h1")).to_contain_text("Pickleballers")
    expect(page.locator(".alert-success")).to_contain_text("Match recorded successfully")

    # Check Global Leaderboard (Req: "see the leaderboard")
    page.click("text=Leaderboard")
    expect(page.locator("h1")).to_contain_text("Leaderboard")
    # Verify players are listed
    expect(page.locator("td", has_text="Admin User")).to_be_visible()
    expect(page.locator("td", has_text="User Two")).to_be_visible()

    # 8. Delete Group Game & 9. Delete Individual Game
    # Needs Admin access
    page.click(".dropbtn")
    page.click("text=Logout")

    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    page.click("input[value='Login']")

    page.goto(f"{base_url}/admin/matches")
    # Delete match involving user2 (first one)
    page.click("button:has-text('Delete')")
    expect(page.locator(".alert-success")).to_contain_text("Match deleted successfully")

    # Delete second match
    page.click("button:has-text('Delete')")
    expect(page.locator(".alert-success")).to_contain_text("Match deleted successfully")

    # 10. Update Group Details (Login as Admin - already logged in)
    page.click("text=Groups")
    page.click("text=Pickleballers")
    page.click("text=Edit Group")
    page.fill("input[name='location']", "New Court")
    page.click("input[value='Update Group']")
    expect(page.locator("text=New Court")).to_be_visible()

    # 11. Invite Email to Group
    page.fill("form[action*='group'] input[name='name']", "New Guy")
    page.fill("form[action*='group'] input[name='email']", "newguy@example.com")
    page.click("input[value='Send Invite']")
    expect(page.locator(".alert-toast, .alert-success, .toast-body")).to_contain_text("Invitation is being sent")

    # Verify invite token was created
    invites = list(mock_db.collection('group_invites').stream())
    invite_token = None
    for inv in invites:
        if inv.to_dict().get('email') == 'newguy@example.com':
            invite_token = inv.id
            break
    assert invite_token is not None
