import os
import re
import email
import imaplib
import requests
import dateparser.search
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from email.header import decode_header

# Environment Variables
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")
URGENCY_THRESHOLD = int(os.getenv("URGENCY_THRESHOLD", "50"))

# Constants
IMAP_SERVER = "imap.gmail.com"

# Heuristics Configuration
KEYWORD_WEIGHTS = {
    r"\binterview\b": 40,
    r"\boffer\b": 40,
    r"\bshortlisted\b": 40,
    r"\bselected\b": 40,
    r"\baction required\b": 30,
    r"\bdeadline\b": 30,
    r"\burgent\b": 30,
    r"\basap\b": 30,
    r"\bnext steps\b": 20,
    r"\bdocument(s)?\b": 20,
    r"\breminder\b": 20,
    r"\bstatus\b": 10,
    r"\bupdate\b": 10,
    r"\bapplication\b": 10
}

NEGATIVE_WEIGHTS = {
    r"\bunsubscribe\b": -50,
    r"\bnewsletter\b": -50,
    r"\bapply now\b": -40,
    r"\bpromotions\b": -30,
    r"unstop": -50,
    r"\bhackathon\b": -20,
    r"\bwebinar\b": -30,
    r"\bmarketing\b": -30
}

DOMAIN_WEIGHTS = {
    r"\.edu$": 20,
    r"workday\.com$": 20,
    r"greenhouse\.io$": 20,
    r"lever\.co$": 20,
    r"icims\.com$": 20
}

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
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    return soup.get_text(separator=" ", strip=True)

def parse_email_body(msg):
    body = ""
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
                            text = clean_html(text)
                        body += " " + text
                except Exception as e:
                    print(f"Failed to parse part: {e}")
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="ignore")
                if msg.get_content_type() == "text/html":
                    text = clean_html(text)
                body = text
        except Exception as e:
            print(f"Failed to parse body: {e}")
            
    # Clean up whitespace
    return re.sub(r'\s+', ' ', body).strip()

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
        f.write("\n".join(list(ids)[-1000:]))

def split_sentences(text):
    # Basic sentence splitter
    return re.split(r'(?<=[.!?]) +', text)

def evaluate_urgency(sender, subject, body):
    score = 0
    domain = extract_domain(sender)
    
    # Evaluate domain
    for pattern, weight in DOMAIN_WEIGHTS.items():
        if re.search(pattern, domain):
            score += weight
            break
            
    # Evaluate subject
    for pattern, weight in KEYWORD_WEIGHTS.items():
        if re.search(pattern, subject, re.IGNORECASE):
            score += (weight // 2) # Half weight for subject matches
    for pattern, weight in NEGATIVE_WEIGHTS.items():
        if re.search(pattern, subject, re.IGNORECASE):
            score += weight
            
    # Evaluate body by sentence to find context
    sentences = split_sentences(body)
    max_sentence_score = 0
    best_sentence = ""
    
    for sentence in sentences:
        sentence_score = 0
        for pattern, weight in KEYWORD_WEIGHTS.items():
            if re.search(pattern, sentence, re.IGNORECASE):
                sentence_score += weight
        for pattern, weight in NEGATIVE_WEIGHTS.items():
            if re.search(pattern, sentence, re.IGNORECASE):
                sentence_score += weight
                
        if sentence_score > max_sentence_score:
            max_sentence_score = sentence_score
            best_sentence = sentence
            
    score += max_sentence_score
    
    # Check for deadlines within 72 hours
    if max_sentence_score > 0: # Only check dates if there's already some relevance to save compute
        dates = dateparser.search.search_dates(best_sentence, languages=['en'])
        if dates:
            now = datetime.now(timezone.utc)
            for _, date_obj in dates:
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
                if now <= date_obj <= now + timedelta(hours=72):
                    score += 30
                    break

    return score, best_sentence.strip()

def process_inbox():
    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NTFY_TOPIC]):
        print("Missing required environment variables. Please configure GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and NTFY_TOPIC.")
        return

    try:
        # Connect and authenticate
        print("Connecting to Gmail IMAP...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        # Search for unread emails within the last 2 days
        print("Searching for recent unread emails...")
        status, messages = mail.uid("SEARCH", None, "UNSEEN", "X-GM-RAW", "newer_than:2d")
        
        if status != "OK":
            print("Failed to search emails.")
            return

        email_ids = messages[0].split()
        if not email_ids:
            print("No new emails to process.")
            return

        processed_ids = load_processed_ids()

        for e_id in email_ids:
            uid_str = e_id.decode()
            if uid_str in processed_ids:
                continue
                
            try:
                # Fetch BODY.PEEK[] (to avoid marking as read) and X-GM-THRID for deep linking
                res, msg_data = mail.uid("FETCH", e_id, "(BODY.PEEK[] X-GM-THRID)")
                if res != "OK":
                    continue
                
                raw_email = None
                thread_id = None
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        # The server responds with BODY[] when BODY.PEEK[] is requested
                        if b"BODY[" in response_part[0] or b"RFC822" in response_part[0]:
                            raw_email = response_part[1]
                        
                        # Extract thread ID from the fetch response line
                        match = re.search(b'X-GM-THRID (\d+)', response_part[0])
                        if match:
                            # Convert to hex because Gmail URLs use hex thread IDs
                            thread_id = hex(int(match.group(1)))[2:]

                if not raw_email:
                    continue

                msg = email.message_from_bytes(raw_email)
                subject = decode_mime_words(msg.get("Subject", ""))
                sender = decode_mime_words(msg.get("From", ""))
                body = parse_email_body(msg)

                print(f"Evaluating: {subject} from {sender}")
                score, context = evaluate_urgency(sender, subject, body)
                
                print(f"Score: {score}")

                if score >= URGENCY_THRESHOLD:
                    print("--> High urgency detected! Sending notification...")
                    # Prepare ntfy.sh notification
                    # Use a fallback text if context is empty
                    msg_body = context if context else subject
                    # Truncate if too long
                    if len(msg_body) > 200:
                        msg_body = msg_body[:197] + "..."
                        
                    headers = {
                        "X-Title": f"Urgent: {sender.split('<')[0].strip()}",
                        "X-Priority": "5",
                        "X-Tags": "rotating_light,email",
                    }
                    
                    if thread_id:
                        # Use Android Intent scheme to force open the Gmail app instead of the browser
                        headers["X-Click"] = f"intent://mail.google.com/mail/u/0/#inbox/{thread_id}#Intent;package=com.google.android.gm;scheme=https;end"

                    requests.post(
                        f"https://ntfy.sh/{NTFY_TOPIC}",
                        data=msg_body.encode('utf-8'),
                        headers=headers
                    )

                # Mark as processed in our local state so we don't process it again
                processed_ids.add(uid_str)
                
            except Exception as e:
                print(f"Error processing email UID {uid_str}: {e}")

        save_processed_ids(processed_ids)
        mail.logout()
        print("Processing complete.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    process_inbox()
