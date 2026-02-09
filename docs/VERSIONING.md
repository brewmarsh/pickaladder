# Version Synchronization System

This document explains how version tags in GitHub are synchronized with the version displayed in the app footer.

## Overview

The Pick-A-Ladder application uses a synchronized versioning system where:
- **GitHub release tags** (e.g., `v0.9.0`) trigger deployments
- **VERSION file** in the repository root stores the current version
- **App footer** displays the version from the VERSION file or environment variable

## How It Works

### 1. Version Display in the App

The version is displayed in the footer of every page (`pickaladder/templates/footer.html`):
```html
v{{ app_version }}
```

The `app_version` variable is injected by the context processor in `pickaladder/__init__.py` with the following priority:

1. **APP_VERSION** environment variable (set during deployment)
2. **GITHUB_RUN_NUMBER** (GitHub Actions build number)
3. **RENDER_GIT_COMMIT** or **HEROKU_SLUG_COMMIT** (Git hash from hosting platforms)
4. **VERSION file** in the repository root
5. Fallback to `"dev"` for local development

### 2. Creating a New Release

To create a new release and synchronize the version:

#### Step 1: Create and Push a Tag
```bash
# Create a new version tag (e.g., v0.9.0)
git tag v0.9.0

# Push the tag to GitHub
git push origin v0.9.0
```

#### Step 2: Automatic Synchronization
When you push a tag matching the pattern `v[0-9]+.[0-9]+.[0-9]+`, two workflows are triggered:

1. **Update Version File** (`.github/workflows/update-version.yml`):
   - Extracts the version number from the tag (removes 'v' prefix)
   - Updates the VERSION file in the main branch
   - Commits and pushes the change with `[skip ci]` to avoid triggering other workflows

2. **Release** (`.github/workflows/release.yml`):
   - Builds and pushes a Docker image
   - Deploys to the production server
   - Sets the `APP_VERSION` environment variable to the tag name

### 3. Version Tag Format

The system supports two tag formats:

- **Production releases**: `v0.9.0`, `v1.0.0`, `v1.2.3`
  - Pattern: `v[MAJOR].[MINOR].[PATCH]`

- **Beta releases**: `v0.9.0-beta.1`, `v1.0.0-beta.2`
  - Pattern: `v[MAJOR].[MINOR].[PATCH]-beta.[INCREMENT]`

### 4. Current Version

The current version is: **0.9.0**

This is stored in:
- `VERSION` file in the repository root
- Displayed in the app footer as `v0.9.0`

## Workflows

### Update Version File Workflow
**File**: `.github/workflows/update-version.yml`

**Triggers**: When a tag matching `v*.*.*` or `v*.*.*-beta.*` is pushed

**Actions**:
1. Checks out the main branch
2. Extracts version from tag (removes 'v' prefix)
3. Updates the VERSION file
4. Commits and pushes to main branch

### Release Workflow
**File**: `.github/workflows/release.yml`

**Triggers**: When a tag matching `v*.*.*` or `v*.*.*-beta.*` is pushed

**Actions**:
1. Builds Docker image
2. Deploys to production server
3. Sets `APP_VERSION` environment variable to tag name

## Examples

### Creating Version 0.9.0
```bash
git tag v0.9.0
git push origin v0.9.0
```

Result:
- VERSION file updated to `0.9.0`
- App footer displays `v0.9.0`
- Production deployment with version `v0.9.0`

### Creating Version 1.0.0-beta.1
```bash
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

Result:
- VERSION file updated to `1.0.0-beta.1`
- App footer displays `v1.0.0-beta.1`
- Beta deployment with version `v1.0.0-beta.1`

## Local Development

During local development:
- The VERSION file is read and displayed in the footer
- If the VERSION file is missing or unreadable, `"dev"` is displayed
- No environment variables are typically set

## Troubleshooting

### Version not updating in the app
1. Check if the VERSION file was updated in the main branch
2. Verify the deployment set the `APP_VERSION` environment variable
3. Check the app logs for any errors reading the VERSION file

### Workflow not triggering
1. Ensure the tag follows the correct pattern: `v[0-9]+.[0-9]+.[0-9]+`
2. Verify the `PAT_TOKEN` secret is configured in GitHub repository settings
3. Check the Actions tab in GitHub for workflow execution status

### VERSION file not committed
1. Ensure the `PAT_TOKEN` has write permissions to the repository
2. Check if there were any git conflicts
3. Verify the workflow completed successfully in the Actions tab
