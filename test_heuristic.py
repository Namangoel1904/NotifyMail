import re
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import notify_mail

def run_test(label, sender, subject, body, link_count=0, headers_dict=None):
    body_clean = re.sub(r'\s+', ' ', body).strip()
    score, context, signals = notify_mail.evaluate_urgency(sender, subject, body_clean, link_count, headers_dict)
    threshold = notify_mail.URGENCY_THRESHOLD
    result = "NOTIFY" if score >= threshold else "SKIP"
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"From: {sender}")
    print(f"Subject: {subject}")
    print(f"Score: {score} (Threshold: {threshold}) => [{result}]")
    print(f"Context: {context[:120]}..." if len(context) > 120 else f"Context: {context}")
    print("Signals:")
    for s in signals:
        print(f"  {s}")
    print('='*60)

# --- Test 1: VidIQ meeting (should NOTIFY) ---
run_test(
    label="1. VidIQ Meeting (urgent mention)",
    sender="Deepak <deepak@example.com>",
    subject="Test meeting",
    body="""Hey Naman We have an urgent meeting scheduled by a company "VidIQ" to understand their
policy regarding YouTube, Would you be able to join it tomorrow at 7PM?
I will share the meeting link, just let me know your availability. Thank You. Regards, Deepak"""
)

# --- Test 2: Application shortlisted (should NOTIFY) ---
run_test(
    label="2. Application Shortlisted Email",
    sender="Devil Goel <devilgoel04@gmail.com>",
    subject="Regarding your application",
    body="""Greetings Naman! A gentle reminder that your application has been shortlisted
and if you are interested to continue then revert to this email ASAP or your application
would be considered as rejected! Thank you."""
)

# --- Test 3: Promotional email from Unstop (should SKIP) ---
run_test(
    label="3. Promotional Email from Unstop (should be skipped)",
    sender="Unstop <noreply@unstop.com>",
    subject="Apply now to 20 new jobs matching your profile!",
    body="""Hi Naman, we found 20 jobs matching your skills. Apply now and boost your profile!
This week's top companies are hiring. Don't miss out. Unsubscribe from these alerts.
View in browser. Manage your subscription preferences.""",
    link_count=12,
    headers_dict={"List-Unsubscribe": "<mailto:unsub@unstop.com>"}
)

# --- Test 4: Bank transaction alert (should NOTIFY) ---
run_test(
    label="4. Bank Transaction Alert",
    sender="HDFC Bank <alerts@hdfcbank.com>",
    subject="ALERT: Transaction of Rs.15000 on your account",
    body="""Dear Customer, your HDFC Bank account has been debited Rs.15000 on 22-Jul-2026.
If you did not authorize this transaction, please call our 24x7 helpline immediately or
block your card via NetBanking."""
)

# --- Test 5: University exam fee reminder (should NOTIFY) ---
run_test(
    label="5. University Fee Deadline",
    sender="Academics Section <academics@university.ac.in>",
    subject="Last date for semester fee payment",
    body="""Dear Students, this is a final reminder that the last date for payment of semester fee
is 25-July-2026. Students who fail to pay before the deadline will not be permitted to appear
for the examinations. Please ensure payment at the earliest."""
)

# --- Test 6: Offer letter from company (should NOTIFY, high score) ---
run_test(
    label="6. Offer Letter Email",
    sender="HR Team <hr@techcorp.workday.com>",
    subject="Offer Letter - Software Engineer",
    body="""Dear Naman, we are pleased to offer you the position of Software Engineer at TechCorp.
Please find the offer letter attached. Kindly confirm your acceptance by 24th July 2026 (EOD).
Contact hr@techcorp.com for any queries."""
)
