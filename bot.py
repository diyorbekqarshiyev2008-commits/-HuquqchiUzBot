import os
import re
import sqlite3
import threading
import requests
from flask import Flask

# =========================
# SOZLAMALAR
# =========================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID topilmadi")

ADMIN_ID = int(ADMIN_ID)

API = f"https://api.telegram.org/bot{TOKEN}"
DB_NAME = "tests.db"

app = Flask(__name__)


# =========================
# DATABASE
# =========================

def init_db():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            test_id INTEGER PRIMARY KEY,
            answers TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_test(test_id, answers):
    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        "INSERT OR REPLACE INTO tests (test_id, answers) VALUES (?, ?)",
        (test_id, answers)
    )

    conn.commit()
    conn.close()


def get_test(test_id):
    conn = sqlite3.connect(DB_NAME)

    row = conn.execute(
        "SELECT answers FROM tests WHERE test_id = ?",
        (test_id,)
    ).fetchone()

    conn.close()

    if row:
        return row[0]

    return None


# =========================
# TELEGRAM
# =========================

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

    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{API}/getUpdates",
        params=params,
        timeout=35
    )

    return response.json()


# =========================
# JAVOBLARNI PARSE QILISH
# =========================

def parse_answers(text):
    """
    Misol:

    1*1a2b3c4d5a

    yoki:

    15*1a2b3c4d5a6b

    Natija:
    test_id = 15
    answers = {
        1: "a",
        2: "b",
        3: "c",
        ...
    }
    """

    text = text.strip().lower()

    match = re.fullmatch(r"(\d+)\*(.+)", text)

    if not match:
        return None, None

    test_id = int(match.group(1))
    answer_text = match.group(2)

    pairs = re.findall(r"(\d+)([abcd])", answer_text)

    if not pairs:
        return None, None

    answers = {}

    for number, letter in pairs:
        answers[int(number)] = letter

    return test_id, answers


# =========================
# KALITNI PARSE QILISH
# =========================

def parse_key(text):
    """
    Admin kalit kiritadi:

    /set 1 1a2b3c4d5a

    yoki:

    /set 15 1a2b3c4d5a6b
    """

    match = re.fullmatch(
        r"/set\s+(\d+)\s+(.+)",
        text.strip().lower()
    )

    if not match:
        return None, None

    test_id = int(match.group(1))
    answer_text = match.group(2)

    pairs = re.findall(r"(\d+)([abcd])", answer_text)

    if not pairs:
        return None, None

    answers = {}

    for number, letter in pairs:
        answers[int(number)] = letter

    return test_id, answers


# =========================
# TESTNI TEKSHIRISH
# =========================

def check_test(test_id, student_answers):
    key_text = get_test(test_id)

    if not key_text:
        return None

    correct_answers = {}

    pairs = re.findall(r"(\d+)([abcd])", key_text)

    for number, letter in pairs:
        correct_answers[int(number)] = letter

    total = len(correct_answers)
    correct = 0
    wrong = 0
    unanswered = 0

    wrong_questions = []
    unanswered_questions = []

    for question_number, correct_answer in correct_answers.items():

        student_answer = student_answers.get(question_number)

        if student_answer is None:
            unanswered += 1
            unanswered_questions.append(question_number)

        elif student_answer == correct_answer:
            correct += 1

        else:
            wrong += 1
            wrong_questions.append(
                f"{question_number}({correct_answer.upper()})"
            )

    if total > 0:
        percent = round(correct / total * 100, 1)
    else:
        percent = 0

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "percent": percent,
        "wrong_questions": wrong_questions,
        "unanswered_questions": unanswered_questions
    }


# =========================
# ADMIN KOMANDALARI
# =========================

def admin_command(chat_id, text):

    # /set
    if text.lower().startswith("/set "):

        if chat_id != ADMIN_ID:
            send_message(
                chat_id,
                "⛔ Bu buyruq faqat administrator uchun."
            )
            return

        test_id, answers = parse_key(text)

        if test_id is None:
            send_message(
                chat_id,
                "❌ Format noto‘g‘ri.\n\n"
                "To‘g‘ri format:\n"
                "/set 1 1a2b3c4d5a\n\n"
                "Masalan:\n"
                "/set 15 1a2b3c4d5a6b7c"
            )
            return

        answer_string = "".join(
            f"{number}{answers[number]}"
            for number in sorted(answers)
        )

        save_test(test_id, answer_string)

        send_message(
            chat_id,
            f"✅ Test #{test_id} kaliti saqlandi!\n\n"
            f"📝 Savollar soni: {len(answers)}\n"
            f"🔑 Kalit: {answer_string}"
        )

        return

    # /delete
    if text.lower().startswith("/delete "):

        if chat_id != ADMIN_ID:
            send_message(
                chat_id,
                "⛔ Bu buyruq faqat administrator uchun."
            )
            return

        match = re.fullmatch(
            r"/delete\s+(\d+)",
            text.strip().lower()
        )

        if not match:
            send_message(
                chat_id,
                "❌ Masalan:\n/delete 15"
            )
            return

        test_id = int(match.group(1))

        conn = sqlite3.connect(DB_NAME)

        conn.execute(
            "DELETE FROM tests WHERE test_id = ?",
            (test_id,)
        )

        conn.commit()
        conn.close()

        send_message(
            chat_id,
            f"🗑 Test #{test_id} o‘chirildi."
        )

        return

    # /check
    if text.lower().startswith("/check "):

        if chat_id != ADMIN_ID:
            send_message(
                chat_id,
                "⛔ Bu buyruq faqat administrator uchun."
            )
            return

        match = re.fullmatch(
            r"/check\s+(\d+)",
            text.strip().lower()
        )

        if not match:
            send_message(
                chat_id,
                "❌ Masalan:\n/check 15"
            )
            return

        test_id = int(match.group(1))

        key = get_test(test_id)

        if key:
            questions = len(
                re.findall(r"\d+[abcd]", key)
            )

            send_message(
                chat_id,
                f"📚 Test #{test_id}\n"
                f"📝 Savollar: {questions}\n"
                f"🔑 Kalit: {key}"
            )
        else:
            send_message(
                chat_id,
                "❌ Bunday test topilmadi."
            )

        return

    # /admin
    if text == "/admin":

        if chat_id != ADMIN_ID:
            send_message(
                chat_id,
                "⛔ Siz administrator emassiz."
            )
            return

        send_message(
            chat_id,
            "👨‍🏫 ADMIN PANEL\n\n"

            "🔑 Kalit kiritish:\n"
            "/set 1 1a2b3c4d5a\n\n"

            "🔎 Test kalitini ko‘rish:\n"
            "/check 1\n\n"

            "🗑 Testni o‘chirish:\n"
            "/delete 1"
        )

        return

    return False


# =========================
# ODDIY FOYDALANUVCHI
# =========================

def handle_message(message):

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # /start
    if text == "/start":

        send_message(
            chat_id,

            "⚖️ HuquqchiUzBot\n\n"

            "📚 Sizga berilgan PDF testni ishlab chiqing.\n\n"

            "Javoblaringizni quyidagi formatda yuboring:\n\n"

            "1*1a2b3c4d5a\n\n"

            "Bu yerda:\n"
            "1* — test raqami\n"
            "1a — 1-savol A\n"
            "2b — 2-savol B\n"
            "3c — 3-savol C\n\n"

            "🤖 Bot javoblaringizni avtomatik tekshiradi."
        )

        return

    # Admin buyruqlari
    if text.startswith("/"):
        result = admin_command(chat_id, text)

        if result is not False:
            return

    # O'quvchi javoblari
    test_id, student_answers = parse_answers(text)

    if test_id is not None:

        result = check_test(
            test_id,
            student_answers
        )

        if result is None:

            send_message(
                chat_id,
                f"❌ Test #{test_id} topilmadi.\n\n"
                "Test raqamini tekshirib qayta yuboring."
            )

            return

        wrong_text = ""

        if result["wrong_questions"]:
            wrong_text = (
                "\n\n❌ Xato savollar:\n"
                + ", ".join(result["wrong_questions"])
            )

        unanswered_text = ""

        if result["unanswered_questions"]:
            unanswered_text = (
                "\n\n⚠️ Javobsiz savollar:\n"
                + ", ".join(
                    map(
                        str,
                        result["unanswered_questions"]
                    )
                )
            )

        send_message(
            chat_id,

            "📊 NATIJA\n\n"

            f"📝 Test: #{test_id}\n"
            f"📚 Jami: {result['total']}\n\n"

            f"✅ To‘g‘ri: {result['correct']}\n"
            f"❌ Noto‘g‘ri: {result['wrong']}\n"
            f"⚪ Javobsiz: {result['unanswered']}\n\n"

            f"📈 Natija: {result['percent']}%"

            f"{wrong_text}"
            f"{unanswered_text}"
        )

        return

    # Noto'g'ri format
    send_message(
        chat_id,

        "❓ Javob formatini tushunmadim.\n\n"

        "Masalan:\n"
        "1*1a2b3c4d5a\n\n"

        "📌 Avval PDF testni ishlab chiqing, "
        "keyin javoblaringizni shu ko‘rinishda yuboring."
    )


# =========================
# BOT LOOP
# =========================

def bot_loop():

    offset = None

    while True:

        try:

            data = get_updates(offset)

            if data.get("ok"):

                for update in data.get("result", []):

                    offset = update["update_id"] + 1

                    if "message" in update:
                        handle_message(
                            update["message"]
                        )

        except Exception as error:

            print("Xatolik:", error)

            import time
            time.sleep(5)


# =========================
# RENDER SERVER
# =========================

@app.route("/")
def home():

    return "HuquqchiUzBot ishlayapti! ⚖️"


# =========================
# START
# =========================

if __name__ == "__main__":

    init_db()

    threading.Thread(
        target=bot_loop,
        daemon=True
    ).start()

    port = int(
        os.getenv("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )        
