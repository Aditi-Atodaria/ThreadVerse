# Google Sign-In Setup

Follow these steps to enable the **Sign in with Google** button.

---

## 1. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click **New Project** → name it (e.g. `ThreadVerse`)
3. Select the new project

---

## 2. Enable the OAuth API

1. Go to **APIs & Services → Library**
2. Search for **Google Identity** (or "People API") → **Enable**

---

## 3. Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in:
   - App name: `ThreadVerse`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue** through the remaining steps
5. Add yourself as a **Test User** (while in development)

---

## 4. Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: `ThreadVerse Web`
5. Under **Authorised redirect URIs** add:
   ```
   http://localhost:5000/login/google/callback
   ```
   (Add your production URL too when deploying)
6. Click **Create**
7. Copy your **Client ID** and **Client Secret**

---

## 5. Set Environment Variables

Before running `app.py`, export these variables in your terminal:

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
export SECRET_KEY="a-long-random-string-for-sessions"
```

Or create a `.env` file and load it with `python-dotenv`:

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=a-long-random-string-for-sessions
```

---

## 6. Add `google_id` Column to MySQL

Run this migration if your `users` table doesn't have the column yet:

```sql
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS google_id VARCHAR(120) DEFAULT NULL;
```

The full `schema.sql` already includes this column.

---

## 7. Run the App

```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000/login` — the **Continue with Google** button will now work.

---

## How it works

- Clicking **Continue with Google** sends the user to Google's consent screen.
- After approval, Google redirects to `/login/google/callback` with an auth token.
- ThreadVerse looks up the user by `google_id`; if not found, checks by `email`
  (to link existing accounts); if still not found, creates a new customer account.
- The session is populated exactly like a normal login.

---

## Password Hashing

All passwords are now hashed with **Werkzeug's PBKDF2-SHA256** before storage.
Existing plain-text passwords in the DB still work (automatic fallback during login),
and they are **not** automatically re-hashed — users simply need to change their
password once, or you can run a one-time migration script.
