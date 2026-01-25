import pandas as pd

# ---------- SETTINGS ----------
CSV_PATH = "whatsapp_chat_history_clean.csv"
SHOW_ROWS = 500  # how many outgoing messages to display
# -----------------------------

# Load CSV safely
try:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
except UnicodeDecodeError:
    df = pd.read_csv(CSV_PATH, encoding="latin1")

# Make output readable
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 2000)
pd.set_option("display.max_colwidth", None)

# Convert dates safely
df["Message Date"] = pd.to_datetime(df["Message Date"], errors="coerce")
df["Sent Date"] = pd.to_datetime(df["Sent Date"], errors="coerce")

# ---------- OUTGOING MESSAGES ----------
# Outgoing messages usually have NO Sender ID
outgoing_df = df[df["Sender ID"].isna()].copy()

# Remove empty / system rows
outgoing_df = outgoing_df[
    outgoing_df["Text"].notna() &
    (outgoing_df["Text"].astype(str).str.strip() != "")
]

# Sort chronologically
outgoing_df = outgoing_df.sort_values("Message Date")

# ---------- OUTPUT ----------
print(f"Total messages: {len(df):,}")
print(f"Outgoing messages: {len(outgoing_df):,}\n")

cols_to_show = [
    "Message Date",
    "Text",
    "Status",
    "Attachment",
    "Attachment type"
]

print(outgoing_df[cols_to_show].head(SHOW_ROWS))

# ---------- SAVE OPTIONAL ----------
outgoing_df.to_csv(
    "outgoing_messages_only.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nSaved file: outgoing_messages_only.csv")
