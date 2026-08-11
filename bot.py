
import os
import re
import threading
import time
import requests
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi")

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# Hozircha namunaviy testlar.
# Keyin 8-11-sinf darsliklaridagi testlarni shu yerga qo'shamiz.
QUESTIONS = {
    1: {
        "1": "O‘zbekiston Respublikasining poytaxti qaysi?",
        "2": "Konstitutsiya kuni qachon nishonlanadi?",
        "3": "O‘zbekiston Respublikasining davlat tili qaysi?",
        "4": "Fuqarolarning asosiy huquqlari qayerda belgilangan?",
        "5": "O‘zbekiston Respublikasi Konstitutsiyasi nima?"
    }
}

# To'g'ri javoblar
ANSWERS = {
    1: {
        1: "b",
        2: "a",
        3: "c",
        4: "a",
        5: "b"
    }
}


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def get_updates(offset=None):
    params = {
        "timeout": 25,
        "allowed_updates": ["message"]
    }

    if offset:
        params["offset"] = offset

    response = requests.get(
        f"{API}/getUpdates",
        params=params,
        timeout=35
    )

    return response.json()


def check_answers(text):
    """
    Masalan:
    1*1a2b3c4d5a

    formatini qabul qiladi.
    """

    match = re.match(r"^(\d+)\*(.*)$", text.strip().lower())

    if not match:
        return None

    test_number = int(match.group(1))
    answers_text = match.group(2)

    pairs = re.findall(r"(\d+)([abcd])", answers_text)

    if not pairs:
        return None

    correct_answers = ANSWERS.get(test_number)

    if not correct_answers:
        return "❌ Bunday test mavjud emas."

    correct = 0
    wrong = 0

    details = []

    for number, answer in pairs:
        number = int(number)

        if number not in correct_answers:
            continue

        if answer == correct_answers[number]:
            correct += 1
            details.append(f"✅ {number}-savol")
        else:
            wrong += 1
            details.append(
                f"❌ {number}-savol "
                f"(to'g'ri javob: {correct_answers[number].upper()})"
            )

    total = correct + wrong

    if total == 0:
        return "❌ Javoblar formatini tushunmadim."

    percent = round(correct / total * 100, 1)

    return (
        "📊 TEST NATIJASI\n\n"
        f"✅ To'g'ri: {correct}\n"
        f"❌ Noto'g'ri: {wrong}\n"
        f"📝 Jami: {total}\n"
        f"📈 Natija: {percent}%\n\n"
        + "\n".join(details)
    )


def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text == "/start":
        send_message(
            chat_id,
            "⚖️ HuquqchiUzBot'ga xush kelibsiz!\n\n"
            "📚 Huquq fanidan test ishlashingiz mumkin.\n\n"
            "Test javoblarini quyidagi formatda yuboring:\n\n"
            "1*1a2b3c4d5a\n\n"
            "Masalan, 1-testning 1-savoliga A, "
            "2-savoliga B javob."
        )
        return

    if text == "/test":
        send_message(
            chat_id,
            "📝 1-test\n\n"
            "1. O'zbekiston Respublikasining poytaxti qaysi?\n"
            "A) Samarqand\n"
            "B) Toshkent\n"
            "C) Buxoro\n"
            "D) Xiva\n\n"
            
            "2. Konstitutsiya kuni qachon?\n"
            "A) 8-dekabr\n"
            "B) 1-sentabr\n"
            "C) 14-yanvar\n"
            "D) 21-mart\n\n"

            "3. O'zbekiston Respublikasining davlat tili qaysi?\n"
            "A) Rus tili\n"
            "B) Ingliz tili\n"
            "C) O'zbek tili\n"
            "D) Qoraqalpoq tili\n\n"

            "4. Fuqarolarning asosiy huquqlari qayerda belgilanadi?\n"
            "A) Konstitutsiyada\n"
            "B) Darslikda\n"
            "C) Lug'atda\n"
            "D) Gazetada\n\n"

            "5. O'zbekiston Respublikasi Konstitutsiyasi nima?\n"
            "A) Oddiy kitob\n"
            "B) Asosiy qonun\n"
            "C) Farmon\n"
            "D) Qaror\n\n"

            "📌 Javoblarni bitta xabarda yuboring:\n"
            "1*1a2b3c4d5a"
        )
        return

    result = check_answers(text)

    if result:
        send_message(chat_id, result)
        return

    send_message(
        chat_id,
        "❓ Buyruq tushunilmadi.\n\n"
        "/start — botni boshlash\n"
        "/test — test ishlash"
    )


def bot_loop():
    offset = None

    while True:
        try:
            data = get_updates(offset)

            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    if "message" in update:
                        handle_message(update["message"])

        except Exception as error:
            print("Xatolik:", error)
            time.sleep(5)


@app.route("/")
def home():
    return "HuquqchiUzBot ishlayapti!"


if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()

    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
