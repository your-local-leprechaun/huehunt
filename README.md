# HueHunt

[![Python](https://img.shields.io/badge/python-3.12-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.1-black?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![Cloud Run](https://img.shields.io/badge/deployed%20on-cloud%20run-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)

---

Each day a new color is generated — seeded by date so every user sees the same one. Snap a photo of something that matches, submit it, and see what the community found. The app tracks your streak for consecutive days of submissions and lets you browse an archive of past challenges.

[Live Site](https://huehunt-1083245261928.us-west2.run.app/)

---

## Features

- Daily color challenge seeded by date (same color for all users)
- Photo submission with in-browser camera capture
- Community gallery for each day's challenge
- User streaks and submission history
- Archive of all past challenges
- Google OAuth + email/password sign-in

---

## Stack

| Layer         | Technology                                |
| ------------- | ----------------------------------------- |
| Backend       | Python / Flask                            |
| Database      | Google Cloud Firestore                    |
| Image storage | Google Cloud Storage                      |
| Auth          | Email/password + Google OAuth via Authlib |
| Deployment    | Docker + Google Cloud Run                 |

---

## Getting started

### Prerequisites

- A [Google Cloud](https://cloud.google.com/) project with **Firestore** and **Cloud Storage** enabled
- A GCP service account with read/write access to both, key downloaded as `db-creds.json`
- Google OAuth 2.0 credentials from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### 1. Configure environment variables

```bash
cp .env.example .env
```

Then fill in `.env`:

```env
SECRET_KEY=change-me-to-a-long-random-string
GCP_PROJECT=your-gcp-project-id
GCS_BUCKET=your-gcs-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=../db-creds.json
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

| Variable                         | Description                                                                                         |
| -------------------------------- | --------------------------------------------------------------------------------------------------- |
| `SECRET_KEY`                     | Flask session secret — generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GCP_PROJECT`                    | Your GCP project ID                                                                                 |
| `GCS_BUCKET`                     | GCS bucket where photos will be stored                                                              |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your service account key JSON                                                               |
| `GOOGLE_CLIENT_ID`               | Google OAuth client ID                                                                              |
| `GOOGLE_CLIENT_SECRET`           | Google OAuth client secret                                                                          |

Place your service account key at the path specified by `GOOGLE_APPLICATION_CREDENTIALS` (default: `db-creds.json` in the project root).

### 2. Run locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python src/app.py
```

Visit `http://localhost:8080`.

### 3. Run with Docker

```bash
make build
make run-docker
```

### 4. Deploy to Cloud Run

```bash
make deploy
```

Builds the image, pushes it to Docker Hub, and deploys to Google Cloud Run. Requires `gcloud` CLI authenticated and Docker Hub access configured in the Makefile.

---

## Forking this project

Before deploying your own version, update the hardcoded values in `Makefile`:

```makefile
IMAGE   := wulfl/huehunt      # change to your-dockerhub-username/your-image-name
SERVICE ?= huehunt             # Cloud Run service name — change to whatever you want
REGION  ?= us-west2            # GCP region to deploy to
```

Also update the service account name in the `deploy` target:

```makefile
--service-account huehunt-runner@$(GCP_PROJECT).iam.gserviceaccount.com
```

Replace `huehunt-runner` with the name of the service account you created in your GCP project.
