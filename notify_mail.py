import os
import re
import email
import imaplib
import requests
import dateparser.search
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from email.header import decode_header

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")
URGENCY_THRESHOLD = int(os.getenv("URGENCY_THRESHOLD", "50"))

# Constants
IMAP_SERVER = "imap.gmail.com"

# ---------------------------------------------------------------------------
# Layer 2: Trusted Sender Domain Map
# Domains that are inherently trustworthy for urgent email (ATS, academic, bank)
# ---------------------------------------------------------------------------
TRUSTED_DOMAINS = {
    # --- Job ATS & Recruitment Platforms ---
    r"workday\.com$": 25,
    r"myworkdayjobs\.com$": 25,
    r"greenhouse\.io$": 25,
    r"lever\.co$": 25,
    r"icims\.com$": 25,
    r"taleo\.net$": 25,
    r"jobvite\.com$": 25,
    r"smartrecruiters\.com$": 25,
    r"brassring\.com$": 25,
    r"successfactors\.com$": 25,
    r"bamboohr\.com$": 20,
    r"zohorecruit\.com$": 20,
    r"keka\.com$": 20,
    r"darwinbox\.in$": 20,
    # --- Indian Job Platforms ---
    r"naukri\.com$": 15,
    r"internshala\.com$": 15,
    r"hirist\.com$": 15,
    r"shine\.com$": 15,
    r"foundit\.in$": 15,
    # --- Academic / Government ---
    r"\.edu$": 20,
    r"\.ac\.in$": 20,
    r"\.gov\.in$": 20,
    r"\.nic\.in$": 20,
    r"nta\.ac\.in$": 25,
    r"ugc\.ac\.in$": 25,
    # --- Banks & Financial Institutions (India) ---
    r"hdfcbank\.com$": 20,
    r"sbi\.co\.in$": 20,
    r"icicibank\.com$": 20,
    r"axisbank\.com$": 20,
    r"kotak\.com$": 20,
    r"yesbank\.in$": 20,
    r"pnbindia\.in$": 20,
    r"bankofbaroda\.in$": 20,
    r"paytm\.com$": 15,
    r"razorpay\.com$": 15,
    r"phonepe\.com$": 15,
}

# ---------------------------------------------------------------------------
# Layer 3: Tiered Keyword Matrix
# Completely rebuilt with 6 urgency tiers covering all major student scenarios
# ---------------------------------------------------------------------------

# Tier 1 — Critical (50 pts): Direct confirmation/offer/rejection language
TIER1_KEYWORDS = [
    r"\boffer letter\b",
    r"\bjob offer\b",
    r"\bappointment letter\b",
    r"\byou have been selected\b",
    r"\bpleased to offer\b",
    r"\bwe are happy to inform\b",
    r"\bconditional offer\b",
    r"\bselected for the (position|role|internship)\b",
    r"\byour (application has been|candidature has been) (accepted|shortlisted|approved)\b",
    r"\bregret to inform\b",  # rejection is also important to know ASAP
    r"\bwe regret\b",
    r"\bnot (moving forward|proceed)\b",
]

# Tier 2 — High (35 pts): Interview & application pipeline events
TIER2_KEYWORDS = [
    r"\binterview (scheduled|invitation|slot|link|details)\b",
    r"\bschedule (your|the) interview\b",
    r"\binterview\b",
    r"\bshortlisted\b",
    r"\bassessment (link|test|scheduled)\b",
    r"\bcoding (challenge|test|round)\b",
    r"\btechnical (round|test|interview)\b",
    r"\bhr round\b",
    r"\bfinal round\b",
    r"\bonline test\b",
    r"\bpre-placement\b",
    r"\bcampus placement\b",
    r"\bjoin us\b",
    r"\bonboarding\b",
    r"\bjoining (date|formalities|letter|process)\b",
]

# Tier 3 — Action Required (30 pts): Time-sensitive direct calls to action
TIER3_KEYWORDS = [
    r"\baction required\b",
    r"\bresponse required\b",
    r"\brevert (asap|immediately|at the earliest|within)\b",
    r"\breply (by|before|asap|within)\b",
    r"\bconfirm (by|before|your|availability)\b",
    r"\bdeadline\b",
    r"\blast (date|day|chance)\b",
    r"\bexpires? (today|soon|on|by|on)\b",
    r"\bexpir(e|es|ed|ing)\b",       # catches 'expire', 'expiring', 'expired'
    r"\brenew(al)?\b",               # domain/subscription renewal
    r"\bsubscription (expired|expiring|due|renewal)\b",
    r"\bdomain (expir|renew)\w*\b",  # "domain expiring", "domain renewal"
    r"\bhosting (expir|renew)\w*\b",
    r"\btime.sensitive\b",
    r"\bimmediately\b",
    r"\basap\b",
    r"\bwithin \d+ (hour|day)s?\b",
    r"\bby (end of day|eod|eob|tonight|tomorrow)\b",
    r"\burgent(ly)?\b",
    r"\bdon.t miss\b",
    r"\bfinal (reminder|notice|warning|call)\b",
    r"\blast (reminder|opportunity|warning)\b",
    r"\bdiscarded\b",
    r"\bsuspended\b",
    r"\bdeactivated\b",
]

# Tier 4 — Academic & Official (25 pts): Exams, college, government
TIER4_KEYWORDS = [
    r"\badmit card\b",
    r"\bhall ticket\b",
    r"\bexam (schedule|date|form|centre|center|roll number)\b",
    r"\bresult (declared|announced|out)\b",
    r"\bfee (due|deadline|payment|pending|overdue)\b",
    r"\bregistration (deadline|last date|closes)\b",
    r"\bsemester (registration|exam|fee)\b",
    r"\bback(log|paper)\b",
    r"\bkyc\b",
    r"\bdocument verification\b",
    r"\bmark.?sheet\b",
    r"\bscholarship\b",
    r"\bvisitng (committee|officer)\b",
    r"\bno.?objection certificate\b",
    r"\bnoc\b",
    r"\bverification (of|pending)\b",
    r"\bclearance (required|pending|certificate)\b",
]

# Tier 5 — Financial & Security Alerts (25 pts)
TIER5_KEYWORDS = [
    r"\baccount (debited|credited|blocked|suspended|frozen)\b",
    r"\btransaction (alert|failed|declined|of)\b",
    r"\bsuspicious (activity|login|transaction)\b",
    r"\bunauthorized (access|transaction|login)\b",
    r"\bpayment (failed|declined|due|overdue|pending)\b",
    r"\bemi (due|missed|overdue)\b",
    r"\botp\b",
    r"\bone.time password\b",
    r"\bfailed (login|attempt)\b",
    r"\bpassword (changed|reset|compromised)\b",
    r"\bfraud (alert|detected)\b",
    r"\bblock(ed)? (card|account)\b",
    r"\bcvv\b",
    r"\bdebit (card|alert)\b",
    r"\bnetbanking\b",
]

# Tier 6 — Soft Contextual Signals (10 pts): Directness & follow-up patterns
TIER6_KEYWORDS = [
    r"\bplease confirm\b",
    r"\bkindly (revert|confirm|respond|update)\b",
    r"\bawaiting your (response|reply|confirmation)\b",
    r"\bdo (let|inform) (us|me) know\b",
    r"\bfollow.?up\b",
    r"\byour (availability|response|reply|confirmation|decision)\b",
    r"\bget back to (us|me)\b",
    r"\breminder\b",
    r"\bpending (from your|your) (end|side)\b",
    r"\bon priority\b",
]

KEYWORD_TIERS = [
    (TIER1_KEYWORDS, 50),
    (TIER2_KEYWORDS, 35),
    (TIER3_KEYWORDS, 30),
    (TIER4_KEYWORDS, 25),
    (TIER5_KEYWORDS, 25),
    (TIER6_KEYWORDS, 10),
]

# ---------------------------------------------------------------------------
# Layer 5: Negative Signal Patterns (Promotional / Spam)
# ---------------------------------------------------------------------------
NEGATIVE_SUBJECT_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bnewsletter\b",
    r"\bweekly (digest|update|roundup)\b",
    r"\bmonthly (digest|update|newsletter)\b",
    r"(\d+%?\s*off\b|\bsale\b|\bfree trial\b|\bwin big\b|\bprize\b|\blucky draw\b)",
    r"\blimited time (offer|deal)\b",
    r"\bclick here\b",
    r"\bexclusive (offer|deal)\b",
    r"\bapply (now|today) to \d+",   # "Apply now to 50 jobs" style promos
    r"\bjobs? (for you|you might like|recommended)\b",
]

NEGATIVE_BODY_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bview (in browser|online version)\b",
    r"\bthis is an automated (email|message|notification)\b",
    r"\byou are receiving this (because|email) (you|as)\b",
    r"\bmanage (your )?(preferences|subscription|alerts)\b",
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def decode_mime_words(s):
    if not s:
        return ""
    decoded_words = decode_header(s)
    result = ""
    for word, charset in decoded_words:
        if isinstance(word, bytes):
            result += word.decode(charset or "utf-8", errors="ignore")
        else:
            result += word
    return result

def clean_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.extract()
    return soup.get_text(separator=" ", strip=True), len(soup.find_all("a"))

def parse_email_body(msg):
    body = ""
    link_count = 0
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="ignore")
                        if content_type == "text/html":
                            text, links = clean_html(text)
                            link_count += links
                        body += " " + text
                except Exception as e:
                    print(f"  [warn] Failed to parse part: {e}")
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="ignore")
                if msg.get_content_type() == "text/html":
                    text, links = clean_html(text)
                    link_count += links
                body = text
        except Exception as e:
            print(f"  [warn] Failed to parse body: {e}")
    return re.sub(r'\s+', ' ', body).strip(), link_count

def extract_domain(from_address):
    match = re.search(r"@([\w.-]+)", from_address)
    return match.group(1).lower() if match else ""

def load_processed_ids():
    if os.path.exists("processed_ids.txt"):
        with open("processed_ids.txt", "r") as f:
            return set(f.read().splitlines())
    return set()

def save_processed_ids(ids):
    with open("processed_ids.txt", "w") as f:
        f.write("\n".join(list(ids)[-2000:]))

def split_sentences(text):
    return re.split(r'(?<=[.!?]) +', text)

def score_text_against_tiers(text):
    """Score a block of text against all keyword tiers. Returns total score and the best matching sentence."""
    sentences = split_sentences(text)
    max_sentence_score = 0
    best_sentence = ""

    for sentence in sentences:
        sentence_score = 0
        for tier_keywords, tier_weight in KEYWORD_TIERS:
            for pattern in tier_keywords:
                if re.search(pattern, sentence, re.IGNORECASE):
                    sentence_score += tier_weight
                    break  # Only count each tier once per sentence

        if sentence_score > max_sentence_score:
            max_sentence_score = sentence_score
            best_sentence = sentence

    return max_sentence_score, best_sentence


# ---------------------------------------------------------------------------
# Core Evaluation: evaluate_urgency
# ---------------------------------------------------------------------------

def evaluate_urgency(sender, subject, body, link_count=0, headers_dict=None):
    score = 0
    signals = []
    domain = extract_domain(sender)

    # --- Layer 5a: Hard disqualifier — List-Unsubscribe header ---
    if headers_dict and headers_dict.get("List-Unsubscribe"):
        score -= 60
        signals.append("[-60] Has List-Unsubscribe header (mailing list)")
        # Still continue scoring — some transactional mail adds this header too

    # --- Layer 5b: Too many links = promotional ---
    if link_count > 5:
        penalty = min(link_count * 3, 30)
        score -= penalty
        signals.append(f"[-{penalty}] High link count ({link_count} links)")

    # --- Layer 5c: Negative subject patterns ---
    for pattern in NEGATIVE_SUBJECT_PATTERNS:
        if re.search(pattern, subject, re.IGNORECASE):
            score -= 40
            signals.append(f"[-40] Negative subject pattern: {pattern}")
            break

    # --- Layer 5d: Negative body patterns ---
    for pattern in NEGATIVE_BODY_PATTERNS:
        if re.search(pattern, body, re.IGNORECASE):
            score -= 20
            signals.append(f"[-20] Negative body pattern: {pattern}")
            break

    # --- Layer 2: Trusted sender domain ---
    for pattern, weight in TRUSTED_DOMAINS.items():
        if re.search(pattern, domain):
            score += weight
            signals.append(f"[+{weight}] Trusted domain: {domain}")
            break

    # --- Layer 3: Subject keyword scoring (half-weight) ---
    subject_score = 0
    for tier_keywords, tier_weight in KEYWORD_TIERS:
        for pattern in tier_keywords:
            if re.search(pattern, subject, re.IGNORECASE):
                subject_score += (tier_weight // 2)
                signals.append(f"[+{tier_weight // 2}] Subject keyword (Tier {KEYWORD_TIERS.index((tier_keywords, tier_weight)) + 1}): matched '{pattern}'")
                break  # Only one match per tier per field

    score += subject_score

    # --- Layer 3: Body keyword scoring ---
    body_score, best_sentence = score_text_against_tiers(body)
    score += body_score
    if body_score > 0:
        signals.append(f"[+{body_score}] Body keyword match")

    # --- Layer 4a: Tiered deadline proximity boost ---
    # Searches best_sentence AND full body for date-like strings to catch renewals
    search_text = best_sentence if best_sentence else body[:500]
    try:
        dates = dateparser.search.search_dates(search_text, languages=['en'],
                                               settings={'PREFER_DATES_FROM': 'future'})
        if dates:
            now = datetime.now(timezone.utc)
            for _, date_obj in dates:
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
                diff = date_obj - now
                if timedelta(0) <= diff <= timedelta(hours=24):
                    score += 40
                    signals.append(f"[+40] Deadline within 24 hours: {date_obj.date()}")
                    break
                elif timedelta(0) <= diff <= timedelta(hours=72):
                    score += 30
                    signals.append(f"[+30] Deadline within 72 hours: {date_obj.date()}")
                    break
                elif timedelta(0) <= diff <= timedelta(days=14):
                    score += 15
                    signals.append(f"[+15] Deadline within 14 days: {date_obj.date()}")
                    break
    except Exception:
        pass

    # --- Layer 4b: ALL-CAPS urgency words ---
    caps_words = re.findall(r'\b[A-Z]{3,}\b', subject + " " + body)
    caps_stopwords = {"THE", "AND", "FOR", "WITH", "YOUR", "FROM", "THAT", "THIS",
                      "ARE", "HAS", "HAVE", "NOT", "CAN", "WILL", "YOU", "WAS",
                      "ONE", "ALL", "ITS", "OUR", "NEW", "GET", "USE", "NOW"}
    meaningful_caps = [w for w in caps_words if w not in caps_stopwords]
    if len(meaningful_caps) >= 2:
        boost = min(len(meaningful_caps) * 5, 20)
        score += boost
        signals.append(f"[+{boost}] {len(meaningful_caps)} ALL-CAPS urgency words: {meaningful_caps[:5]}")

    return score, best_sentence.strip(), signals


# ---------------------------------------------------------------------------
# Main Processing Loop
# ---------------------------------------------------------------------------

def process_inbox():
    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NTFY_TOPIC]):
        print("ERROR: Missing required environment variables.")
        return

    try:
        print("Connecting to Gmail IMAP...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        # Layer 1: Primary inbox only, unread, within 2 days
        # The X-GM-RAW value must be double-quoted as an IMAP string literal (spaces inside)
        print("Searching for recent unread emails in Primary inbox...")
        status, messages = mail.uid("SEARCH", "UNSEEN",
                                    "X-GM-RAW", '"newer_than:2d category:primary"')

        if status != "OK":
            print("Failed to search emails.")
            return

        email_ids = messages[0].split()
        if not email_ids:
            print("No new emails to process.")
            return

        print(f"Found {len(email_ids)} candidate(s).")
        processed_ids = load_processed_ids()

        for e_id in email_ids:
            uid_str = e_id.decode()
            if uid_str in processed_ids:
                continue

            try:
                res, msg_data = mail.uid("FETCH", e_id, "(BODY.PEEK[] X-GM-THRID)")
                if res != "OK":
                    continue

                raw_email = None
                thread_id = None

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        if b"BODY[" in response_part[0] or b"RFC822" in response_part[0]:
                            raw_email = response_part[1]
                        match = re.search(rb'X-GM-THRID (\d+)', response_part[0])
                        if match:
                            thread_id = hex(int(match.group(1)))[2:]

                if not raw_email:
                    continue

                msg = email.message_from_bytes(raw_email)
                subject = decode_mime_words(msg.get("Subject", ""))
                sender = decode_mime_words(msg.get("From", ""))

                # Collect all headers for negative signal checks
                headers_dict = dict(msg.items())

                body, link_count = parse_email_body(msg)

                print(f"\nEvaluating: '{subject}' from {sender}")
                score, context, signals = evaluate_urgency(sender, subject, body,
                                                           link_count, headers_dict)

                print(f"  Score: {score}")
                for s in signals:
                    print(f"  Signal: {s}")

                if score >= URGENCY_THRESHOLD:
                    print("  --> High urgency! Sending notification...")
                    msg_body = context if context else subject
                    if len(msg_body) > 200:
                        msg_body = msg_body[:197] + "..."

                    sender_name = sender.split('<')[0].strip()
                    headers = {
                        "X-Title": f"Urgent Mail: {sender_name}",
                        "X-Priority": "5",
                        "X-Tags": "rotating_light,email",
                    }
                    if thread_id:
                        # googlegmail:// is Gmail's own registered URI scheme on Android.
                        # ntfy opens this directly via ACTION_VIEW, which Android hands off
                        # to the Gmail app. Falls back to https:// for iOS/browser.
                        headers["X-Click"] = f"googlegmail://mail/u/0/#inbox/{thread_id}"

                    requests.post(
                        f"https://ntfy.sh/{NTFY_TOPIC}",
                        data=msg_body.encode("utf-8"),
                        headers=headers
                    )

                processed_ids.add(uid_str)

            except Exception as e:
                print(f"  [error] UID {uid_str}: {e}")

        save_processed_ids(processed_ids)
        mail.logout()
        print("\nProcessing complete.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    process_inbox()
