# Version Synchronization - Quick Reference

## ✅ What Was Implemented

### 1. Updated VERSION File
- Changed from `0.1.0` to `0.9.0`
- Located at: `/VERSION`

### 2. Created Auto-Update Workflow
- File: `.github/workflows/update-version.yml`
- **Purpose**: Automatically updates the VERSION file when you push a new release tag
- **Triggers**: When you push tags like `v0.9.0`, `v1.0.0`, `v1.0.0-beta.1`, etc.

### 3. Created Documentation
- File: `docs/VERSIONING.md`
- Comprehensive guide on how the versioning system works

### 4. Created Initial Tag
- Tag `v0.9.0` has been created and pushed to GitHub
- This will trigger both:
  - The release workflow (deployment)
  - The update-version workflow (VERSION file sync)

## 🚀 How to Create Future Releases

### For Production Releases:
```bash
# Example: Creating version 1.0.0
git tag v1.0.0
git push origin v1.0.0
```

### For Beta Releases:
```bash
# Example: Creating beta version 1.0.0-beta.1
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

## 🔄 What Happens Automatically

When you push a tag (e.g., `v0.9.0`):

1. **Update Version Workflow** runs:
   - Extracts version from tag → `0.9.0`
   - Updates VERSION file
   - Commits to main branch with message: `chore: update VERSION to 0.9.0 [skip ci]`

2. **Release Workflow** runs:
   - Builds Docker image
   - Deploys to production
   - Sets `APP_VERSION=v0.9.0` environment variable

3. **App Footer** displays:
   - `v0.9.0` (from VERSION file or APP_VERSION env var)

## 📍 Where Version is Displayed

The version appears in the footer of every page:
```
© 2026 Pick-A-Ladder | v0.9.0
```

Template: `pickaladder/templates/footer.html`

## 🔍 Version Priority

The app checks for version in this order:
1. `APP_VERSION` environment variable (production)
2. `GITHUB_RUN_NUMBER` (CI builds)
3. `RENDER_GIT_COMMIT` or `HEROKU_SLUG_COMMIT` (git hash)
4. `VERSION` file (local development)
5. `"dev"` (fallback)

## ✨ Benefits

- **Single Source of Truth**: VERSION file is automatically updated
- **No Manual Work**: Just push a tag, everything syncs automatically
- **Consistent Versioning**: GitHub releases match app footer version
- **Beta Support**: Can create beta releases with `-beta.X` suffix

## 📝 Next Steps

1. Monitor the GitHub Actions to ensure workflows complete successfully
2. Verify the VERSION file was updated on the main branch
3. Check the deployed app footer shows `v0.9.0`
4. For future releases, just create and push tags following the pattern above

## 🛠️ Troubleshooting

If the VERSION file doesn't update automatically:
- Check GitHub Actions tab for workflow status
- Ensure `PAT_TOKEN` secret is configured in repository settings
- Verify the token has write permissions to the repository

For detailed information, see `docs/VERSIONING.md`
