import pandas as pd

def load_whatsapp_csv(path):
    return pd.read_csv(path)

def extract_qa_pairs(df):
    pairs = []
    for i in range(len(df) - 1):
        if df.iloc[i]["Type"] == "incoming" and df.iloc[i+1]["Type"] == "outgoing":
            pairs.append({
                "question": df.iloc[i]["Message"],
                "answer": df.iloc[i+1]["Message"]
            })
    return pd.DataFrame(pairs)
