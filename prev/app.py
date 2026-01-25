from flask import Flask, request, jsonify

from rules import rule_based_reply
from faq_engine import get_faq_answer
from ai_fallback import ai_reply
from chat_cli import smart_style  # reuse same cleaning rules

app = Flask(__name__)

@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()

    if not user_text:
        return jsonify({"reply": smart_style("ما وصلتني رسالة 🙂 اكتبها مرة ثانية.")})

    # 0) Rule-based reply
    rule_reply = rule_based_reply(user_text)
    if rule_reply:
        return jsonify({"reply": smart_style(rule_reply)})

    # 1) FAQ
    answer = get_faq_answer(user_text)
    if answer:
        return jsonify({"reply": smart_style(str(answer).strip())})

    # 2) AI fallback
    return jsonify({"reply": smart_style(ai_reply(user_text))})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
