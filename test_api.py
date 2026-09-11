import os
import json
from dotenv import load_dotenv
from groq import Groq
from prompts import NEXT_QUESTION_PROMPT

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

description = input("Describe your project: ")   # تكتب الوصف
qa_history = []                                   # دفتر المحادثة (يبدأ فاضي)

while True:
    # نبني النص: الوصف + كل الأسئلة والأجوبة السابقة
    conversation = f"Description: {description}\n\nPrevious questions and answers:\n"
    for qa in qa_history:
        conversation += f"Q: {qa['q']}\nA: {qa['a']}\n"
    conversation += "\nNow ask the next question, or return done if you have enough."

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": NEXT_QUESTION_PROMPT},
            {"role": "user", "content": conversation},
        ],
    )

    result = json.loads(response.choices[0].message.content)   # نحوّل الرد لبيانات

    if result["done"]:                   # إذا قال done، نوقف
        print("\n✅ Enough information gathered!")
        break

    # نعرض السؤال، وننتظر ردّك
    print(f"\n❓ {result['question']}")
    answer = input("Your answer: ")

    # نضيف السؤال وإجابتك للدفتر
    qa_history.append({"q": result["question"], "a": answer})

# في النهاية، نطبع المحادثة كاملة
print("\n--- Conversation ---")
for qa in qa_history:
    print(f"Q: {qa['q']}\nA: {qa['a']}\n")
