Here is a Product Requirements Document (PRD) based on the zero-cost, AI-free architecture we discussed.

# Product Requirements Document: Zero-Cost Email Triage & Notification Automation

## 1. Product Overview

**Objective:** To build an open-source, deployable automation tool that securely monitors a user's Gmail inbox, identifies highly urgent emails (such as job interview updates, document requests, or academic deadlines), and delivers actionable push notifications directly to their mobile device.
**Key Constraints:** The system must incur zero financial cost, require no third-party API keys for artificial intelligence (e.g., OpenAI, Gemini), preserve absolute data privacy by keeping operations strictly personal, and run continuously without relying on local hardware uptime.

## 2. Target Audience

College students, recent graduates, and active job seekers who receive high volumes of low-priority email (newsletters, university updates) and frequently miss time-sensitive, career-critical communications due to disabled or muted email notifications.

## 3. Core Requirements

### 3.1. Serverless Execution Environment

* **Requirement:** The script must run autonomously 24/7 without a paid cloud server or local machine.
* **Solution:** Utilize GitHub Actions' free tier, which provides 2,000 minutes of compute time per month for private repositories.


* **Scheduling:** The automation will use a cron trigger. To avoid GitHub's known delays at the top of the hour, the cron schedule will be offset (e.g., `17 * * * *` to run at 17 minutes past the hour).



### 3.2. Secure & Private Email Authentication

* **Requirement:** Because major email providers deprecated legacy "less secure app" password access, the system must authenticate securely without requiring the user to pass a complex OAuth 2.0 verification audit.


* **Solution:** The system will use Google App Passwords—a 16-character code generated from the user's Google Security settings (requires 2FA). The script will connect to `imap.gmail.com` securely over port 993 using Python's `imaplib`.



### 3.3. Efficient Data Ingestion & State Management

* **Requirement:** The script must not download the entire inbox or notify the user about the same email twice.
* **Solution:**
* **Targeted Fetching:** Use Google's `X-GM-RAW` IMAP extension to query only fresh, unread messages (e.g., `newer_than:1d`).


* **Idempotency:** Once an email is evaluated, the script will apply a custom IMAP label (e.g., `System/Processed`). Subsequent IMAP queries will exclude this label so previously processed emails are ignored.





### 3.4. Deterministic Heuristic Engine (AI-Free Parsing)

* **Requirement:** The system must identify urgency and extract a one-liner context sentence using standard code, not AI.
* **Solution:**
* **Sanitization:** Use `BeautifulSoup` to strip raw HTML tags, `<script>`, and `<style>` elements to extract clean, readable text.


* **Keyword Scoring:** Apply a weighted Regular Expression (Regex) matrix. Using word boundaries (e.g., `\binterview\b`), the system will assign points for domains (e.g., `.edu`, `workday.com`) and urgent terms (e.g., "action required", "deadline").


* **Date Proximity:** Utilize the `dateparser` Python library to extract dates/deadlines from the raw text and boost the urgency score if the deadline is within 72 hours.


* **Context Extraction:** Extract the specific sentence containing the highest-weighted keyword to serve as the notification body.





### 3.5. Zero-Cost Push Notifications & Deep Linking

* **Requirement:** Notifications must be delivered instantly to iOS or Android without account creation, API limits, or subscription fees.
* **Solution:**
* **Gateway:** Use `ntfy.sh`, a free, accountless publish-subscribe service.


* **Delivery:** The Python script will send an HTTP POST request to a unique, secret topic created by the user.


* **Rich Formatting:** Utilize HTTP headers to bypass silent modes (`X-Priority: 5`), add visual cues (`X-Tags: rotating_light`), and inject the sender's name into the title (`X-Title`).


* **Actionable Links:** Use the `X-Click` header paired with the Gmail deep link structure: `[https://mail.google.com/mail/u/0/#inbox/](https://mail.google.com/mail/u/0/#inbox/){thread_id}`. Tapping the notification on the phone will immediately launch the native Gmail app and open that specific email.





## 4. User Onboarding Flow

1. **Clone/Fork:** User forks the public GitHub repository containing the Python script and `.github/workflows/` YAML file.
2. **Generate Credentials:** User turns on 2FA in Google, creates an App Password, and creates a unique topic name in the `ntfy` mobile app.


3. **Add Secrets:** User pastes their Email, App Password, and `ntfy` Topic into their GitHub repository's "Secrets" tab.
4. **Activate:** User manually triggers the GitHub Action once to kickstart the cron schedule. The system runs silently in the background forever.

5. Technical Workflow & State Management
Fetching Strategy: The Python script connects securely to imap.gmail.com using the imaplib library. It utilizes targeted queries to retrieve only new messages.

Idempotency (Tracking Processed Emails): To prevent duplicate notifications without the friction of creating custom labels, the system utilizes the standard IMAP \Flagged attribute (which appears as the "Starred" status in Gmail). The script will exclusively query for unread, unstarred emails. Once an email is evaluated, it is flagged (starred), ensuring it is never processed by the script again.

Date Parsing Optimization: The dateparser library is strictly configured to default to English (languages=['en']). By bypassing the resource-heavy automatic language detection phase, the script executes significantly faster, preserving the user's free compute minutes.

6. User Configuration & Environment Variables
Users will manage the system's behavior entirely through GitHub Secrets and Variables, meaning they never have to edit the underlying Python code:

GMAIL_ADDRESS (Secret): The user's standard email address.

GMAIL_APP_PASSWORD (Secret): The 16-character Google App Password used for secure IMAP access.

NTFY_TOPIC (Secret): The randomly generated, unique string the user created in the ntfy app to route their alerts.

URGENCY_THRESHOLD (Variable): The configurable score limit defaulting to 50 points. Users can increase this number if they receive too many false-positive alerts, or decrease it if the filter is too strict.

7. Deployment & Maintenance Constraints
The 60-Day Inactivity Rule: GitHub automatically pauses scheduled cron workflows in repositories that have seen no commit activity for 60 days. To mitigate this, the deployment includes a workflow_dispatch trigger in the YAML file. If the schedule is paused, the user simply clicks a "Run workflow" button in their repository to instantly reactivate it.

Notification Rate Limiting: The free tier of the public ntfy.sh server permits 250 daily messages. Because the heuristic engine is designed to filter out the vast majority of emails and only flag urgent ones, users will naturally stay well below this limit.