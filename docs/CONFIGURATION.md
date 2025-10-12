# Application Configuration

This document outlines the steps required to configure the Pick-a-Ladder application to run with your own Firebase project.

## Firebase Credentials Setup

To connect the application to your Firebase project, you need to provide it with a service account credentials file and your project ID.

There are two main scenarios for running the app:

### 1. For Local Development (using Docker)

You will use your downloaded Firebase service account key (a JSON file).

1.  **Get Your Credentials File:**
    *   Go to your project in the [Firebase Console](https://console.firebase.google.com/).
    *   Click the gear icon next to "Project Overview" and go to **Project settings**.
    *   Go to the **Service accounts** tab.
    *   Click the **"Generate new private key"** button. This will download a JSON file containing your credentials.

2.  **Place the File in the Project:**
    *   Rename the downloaded file to `firebase-credentials.json`.
    *   Move this file into the root directory of the project (the same folder where `docker-compose.yml` is located). The `.gitignore` file is already set up to ignore this file, so it won't be committed to your repository.

3.  **Set Your Project ID:**
    *   Open the `docker-compose.yml` file.
    *   In the `environment` section for the `web` service, find the line that says `FIREBASE_PROJECT_ID=your-firebase-project-id`.
    *   Replace `your-firebase-project-id` with your actual Firebase Project ID.

Now, when you run `docker compose up`, the application will have the necessary credentials to connect to your Firebase project.

### 2. For Production Deployment (using GitHub Actions)

For deployment, you should use GitHub Secrets to store your credentials securely.

1.  **Go to Your Repository Settings on GitHub:**
    *   Navigate to your repository's page on GitHub.
    *   Click on **Settings** > **Secrets and variables** > **Actions**.

2.  **Create the Credentials Secret:**
    *   Click the **"New repository secret"** button.
    *   For the **Name**, enter `FIREBASE_CREDENTIALS_JSON`.
    *   For the **Value**, open the `firebase-credentials.json` file you downloaded earlier, copy its entire content, and paste it into this field.

3.  **Create the Project ID Secret:**
    *   Click **"New repository secret"** again.
    *   For the **Name**, enter `FIREBASE_PROJECT_ID`.
    *   For the **Value**, enter your Firebase Project ID.

Once these secrets are saved, the deployment workflow defined in `.github/workflows/deploy.yml` will automatically use them to configure your application when it deploys.