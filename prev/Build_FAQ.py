import csv
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from tqdm import tqdm

# =======================
# CONFIG
# =======================
CHAT_PATH = Path("whatsapp_chat_history_clean.csv")
OUT_ALL = Path("data/all_questions_tagged.csv")
OUT_TOP = Path("top_questions_clusters.csv")

SIM_THRESHOLD = 0.88
MIN_LEN = 6
TOP_CLUSTERS = 150
MAX_EXAMPLES = 5

# Bucketing controls (tune if needed)
LEN_BUCKET = 12          # group by length//LEN_BUCKET
PREFIX_TOKENS = 4        # first N tokens for bucket key
MAX_BUCKET_SIZE = 900    # safety cap: if bucket too large, split further
# =======================


# -----------------------
# Text normalize
# -----------------------
def normalize_text(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"http\S+|www\.\S+", " ", s)
    s = re.sub(r"\b\d{7,}\b", " ", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = s.replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"[^0-9a-z\u0600-\u06FF\s؟]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokens(s: str) -> list[str]:
    return re.findall(r"[0-9a-z\u0600-\u06FF]+", s)

# -----------------------
# Noise filtering
# -----------------------
GREETINGS = {
    "السلام عليكم", "وعليكم السلام", "السلام", "مرحبا", "اهلا", "أهلا", "هلا", "هاي",
    "صباح الخير", "مساء الخير", "hello", "hi"
}
ACKS = {
    "تمام", "طيب", "اوكي", "اوك", "اوكيه", "شكرا", "شكرًا", "يسلمو", "ممتاز",
    "ok", "okay", "thanks", "thx"
}

def is_noise(norm: str) -> bool:
    if not norm:
        return True
    if norm in GREETINGS or norm in ACKS:
        return True
    if len(norm) < MIN_LEN:
        if norm in {"السعر", "السعر؟", "بكم", "كم", "وين", "فين", "متوفر", "فيه", "شحن", "توصيل", "ضمان"}:
            return False
        return True
    if re.fullmatch(r"(.)\1{4,}", norm):
        return True
    return False

# -----------------------
# Question detection
# -----------------------
QUESTION_HINTS = (
    "سعر", "بكم", "كم سعر", "price", "cost",
    "متوفر", "توفر", "موجود", "available", "stock",
    "شحن", "توصيل", "يوصل", "مدة", "delivery", "shipping",
    "لون", "الوان", "ألوان", "color", "colour",
    "ضمان", "كفاله", "warranty",
    "استرجاع", "استبدال", "return", "refund", "exchange",
    "تقسيط", "tabby", "tamara", "payment",
    "موقع", "عنوان", "فرع", "location", "address"
)

def looks_like_question(raw: str, norm: str) -> bool:
    if is_noise(norm):
        return False
    if "؟" in raw or "?" in raw:
        return True
    return any(h in norm for h in QUESTION_HINTS)

# -----------------------
# Intent classification
# -----------------------
INTENT_RULES = [
    ("price", ["سعر", "بكم", "كم سعر", "price", "cost"]),
    ("availability", ["متوفر", "توفر", "موجود", "available", "stock", "فيه"]),
    ("shipping", ["شحن", "توصيل", "delivery", "shipping", "يوصل", "مدة"]),
    ("color", ["لون", "الوان", "ألوان", "color", "colour", "black", "white", "gray", "grey"]),
    ("warranty", ["ضمان", "كفاله", "كفالة", "warranty", "guarantee"]),
    ("returns", ["استرجاع", "استبدال", "ارجاع", "return", "refund", "exchange"]),
    ("payment", ["تقسيط", "تمارا", "تابي", "tabby", "tamara", "installment", "payment", "مدى", "فيزا", "ماستر"]),
    ("location", ["موقع", "عنوان", "فرع", "location", "address", "branch"]),
]

def detect_intent(norm: str) -> str:
    for intent, keys in INTENT_RULES:
        if any(k in norm for k in keys):
            return intent
    return "other"

# -----------------------
# Similarity
# -----------------------
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

# -----------------------
# Fast bucketing key
# -----------------------
def bucket_key(norm: str) -> tuple:
    tk = tokens(norm)
    pref = tuple(tk[:PREFIX_TOKENS])
    lbin = len(norm) // LEN_BUCKET
    return (pref, lbin)

def secondary_split_key(norm: str) -> tuple:
    # used if a bucket gets too big; adds one more token + last token
    tk = tokens(norm)
    pref2 = tuple(tk[:PREFIX_TOKENS + 1])
    last = tk[-1] if tk else ""
    return (pref2, last, len(norm) // LEN_BUCKET)

# -----------------------
# Main
# -----------------------
def main():
    if not CHAT_PATH.exists():
        raise FileNotFoundError(CHAT_PATH)

    with CHAT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Only incoming
    incoming = [r for r in rows if (r.get("Type") or "").strip() == "Incoming"]
    print(f"Incoming messages: {len(incoming)}")

    # Extract questions
    all_q = []
    for r in tqdm(incoming, desc="Scanning messages"):
        raw = (r.get("Text") or "").strip()
        norm = normalize_text(raw)
        if looks_like_question(raw, norm):
            all_q.append((raw, norm, detect_intent(norm)))

    print(f"Detected questions: {len(all_q)}")

    # Save all tagged questions
    with OUT_ALL.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_message", "normalized", "intent"])
        for raw, norm, intent in all_q:
            w.writerow([raw, norm, intent])

    # Build buckets
    buckets = defaultdict(list)
    for i, (_, norm, _) in enumerate(all_q):
        buckets[bucket_key(norm)].append(i)

    # Split overly-large buckets
    buckets2 = defaultdict(list)
    for k, idxs in buckets.items():
        if len(idxs) <= MAX_BUCKET_SIZE:
            buckets2[k] = idxs
        else:
            for i in idxs:
                buckets2[secondary_split_key(all_q[i][1])].append(i)

    bucket_items = list(buckets2.items())
    print(f"Buckets: {len(bucket_items)}")

    # Cluster within buckets only (fast)
    used = set()
    clusters = []

    for _, idxs in tqdm(bucket_items, desc="Clustering buckets"):
        # local clustering
        for ii in idxs:
            if ii in used:
                continue
            used.add(ii)
            group = [ii]
            base = all_q[ii][1]

            for jj in idxs:
                if jj in used:
                    continue
                # quick length guard
                if abs(len(base) - len(all_q[jj][1])) > 40:
                    continue
                if similarity(base, all_q[jj][1]) >= SIM_THRESHOLD:
                    used.add(jj)
                    group.append(jj)

            clusters.append(group)

    clusters.sort(key=len, reverse=True)

    # Save clusters
    with OUT_TOP.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["count", "intent", "representative", "examples"])

        for group in clusters[:TOP_CLUSTERS]:
            examples = [all_q[k][0] for k in group][:MAX_EXAMPLES]
            norms_group = [all_q[k][1] for k in group]
            intents = [all_q[k][2] for k in group]

            rep = min(set(norms_group), key=len)
            intent = Counter(intents).most_common(1)[0][0]

            w.writerow([len(group), intent, rep, " | ".join(examples)])

    print(f"Saved: {OUT_ALL}")
    print(f"Saved: {OUT_TOP}")
    print("✅ Done.")


if __name__ == "__main__":
    main()
