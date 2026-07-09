import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import NEXT_QUESTION_PROMPT

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

description = input("Describe your project: ")   # تكتب الوصف
qa_history = []                                   # دفتر المحادثة (يبدأ فاضي)

while True:
    # نبني النص: الوصف + كل الأسئلة والأجوبة السابقة
    conversation = f"Description: {description}\n\nPrevious questions and answers:\n"
    for qa in qa_history:
        conversation += f"Q: {qa['q']}\nA: {qa['a']}\n"
    conversation += "\nNow ask the next question, or return done if you have enough."

    # نستدعي Gemini
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=conversation,
        config=types.GenerateContentConfig(
            system_instruction=NEXT_QUESTION_PROMPT,
            response_mime_type="application/json",
        ),
    )

    result = json.loads(response.text)   # نحوّل الرد لبيانات

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