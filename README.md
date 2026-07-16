# NotifyMail: Zero-Cost Email Triage & Notification Automation

An open-source, deployable Python automation tool that securely monitors your Gmail inbox for highly urgent emails (job interview updates, document requests, academic deadlines), evaluates them using a fast deterministic heuristic engine, and delivers actionable push notifications directly to your mobile device via `ntfy.sh`. 

This runs entirely on GitHub Actions, requiring **no paid cloud servers, no AI API keys, and zero financial cost**.

## Key Features

- **Serverless Execution:** Runs 24/7 on GitHub Actions' free tier.
- **Privacy-First:** Reads your emails securely using IMAP. No data is sent to OpenAI or other third parties.
- **Smart Idempotency:** Marks processed emails with a `Starred` flag (`\Flagged`) so you never get double-notified, and unread emails are preserved.
- **Zero-Cost Push Notifications:** Uses `ntfy.sh` to send priority alerts straight to your phone, bypassing silent modes for critical emails.
- **Actionable Alerts:** Tap the notification to instantly open the exact email in your Gmail app via deep links.

---

## 🚀 Setup Guide (5 Minutes)

### 1. Fork this Repository
Click the **Fork** button in the top right corner of this GitHub repository to create your own private copy.

### 2. Generate Google App Password
Since you cannot use your regular Gmail password for IMAP:
1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. Search for "App passwords" in the search bar.
4. Create a new App Password (e.g., name it "NotifyMail") and copy the 16-character code.

### 3. Setup `ntfy.sh` (Free Push Notifications)
1. Download the **ntfy** app on [iOS](https://apps.apple.com/us/app/ntfy/id1625396347) or [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Open the app and tap the **+** icon to subscribe to a new topic.
3. Invent a uniquely random, secret topic name (e.g., `john_doe_alerts_99x`). Do not use something common like `test` or anyone could see your alerts.
4. Subscribe to it.

### 4. Configure GitHub Secrets
In your forked GitHub repository, go to **Settings > Secrets and variables > Actions**:

Add the following **Secrets**:
- `GMAIL_ADDRESS`: Your standard Gmail address (e.g., `yourname@gmail.com`).
- `GMAIL_APP_PASSWORD`: The 16-character code from Step 2.
- `NTFY_TOPIC`: The secret topic name you created in Step 3.

Add the following **Variable** (Optional):
- `URGENCY_THRESHOLD`: Set to `50` by default. Increase it if you get too many notifications, or decrease it if the filter is missing things.

### 5. Activate the Automation
GitHub Actions scheduled workflows are disabled by default on forks. To kickstart it:
1. Go to the **Actions** tab in your repository.
2. Click **I understand my workflows, go ahead and enable them**.
3. Select **Email Triage Automation** on the left.
4. Click **Run workflow** -> **Run workflow** on the main branch.

The system will now run automatically at 17 minutes past the hour, every hour, forever.

> **Note on 60-Day Inactivity:** GitHub automatically pauses scheduled workflows in repositories with no commit activity for 60 days. If your alerts suddenly stop, simply return to the Actions tab and click **Run workflow** again to reactivate the schedule.
