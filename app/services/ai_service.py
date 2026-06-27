"""
AI Feedback Service using Groq (llama-3.3-70b-versatile).
Ported and enhanced from v1 ai_feedback.py.
"""
from __future__ import annotations
import streamlit as st


def _get_groq_client():
    try:
        from groq import Groq
        api_key = st.secrets.get("GROQ_API_KEY") or st.secrets.get("groq", {}).get("api_key")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in secrets")
        return Groq(api_key=api_key)
    except Exception as e:
        raise RuntimeError(f"Groq init failed: {e}")


def generate_exam_feedback(
    student_name: str,
    exam_title: str,
    score: int,
    total: int,
    weak_topics: list[str] | None = None,
    lang: str = "ar",
) -> str:
    """
    Generate AI feedback after an exam submission.
    Returns Arabic or English feedback string.
    """
    pct = round(score / total * 100) if total else 0
    weak_str = "، ".join(weak_topics) if weak_topics else "لا توجد"

    if lang == "ar":
        prompt = f"""أنت مساعد تعليمي ذكي لمنصة EduVision LMS.

الطالب: {student_name}
الامتحان: {exam_title}
الدرجة: {score} من {total} ({pct}%)
المواضيع الضعيفة: {weak_str}

اكتب تغذية راجعة باللغة العربية بأسلوب تشجيعي وبناء:
1. ابدأ بتهنئة أو تشجيع حسب الدرجة
2. وضّح نقاط القوة
3. وضّح المواضيع التي تحتاج مراجعة (إن وجدت)
4. قدّم نصيحة عملية للتحسين
5. اختم برسالة تحفيزية

اكتب بأسلوب ودود ومحفّز، 3-5 جمل كحد أقصى."""
    else:
        prompt = f"""You are an AI educational assistant for EduVision LMS.

Student: {student_name}
Exam: {exam_title}
Score: {score}/{total} ({pct}%)
Weak topics: {weak_str or 'None'}

Write encouraging and constructive feedback:
1. Start with congratulation or encouragement based on score
2. Highlight strengths
3. Point out topics needing review (if any)
4. Give practical improvement advice
5. End with motivational message

Keep it friendly, 3-5 sentences max."""

    try:
        client   = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful educational AI assistant."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=400,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ تعذّر توليد التغذية الراجعة: {e}"


def generate_weak_topic_analysis(
    student_name: str,
    subject_name: str,
    wrong_answers: list[dict],
    lang: str = "ar",
) -> str:
    """
    Analyze wrong answers and identify weak topics.
    wrong_answers: [{"question": str, "topic": str, "correct": str, "student_answer": str}]
    """
    if not wrong_answers:
        return "أداء ممتاز! لا توجد أخطاء تحتاج تحليل." if lang=="ar" else "Excellent! No errors to analyze."

    wrong_summary = "\n".join([
        f"- السؤال: {w['question'][:60]} | الموضوع: {w.get('topic','—')} | الصواب: {w.get('correct','—')}"
        for w in wrong_answers[:10]
    ])

    prompt = f"""أنت مدرس خبير في تحليل أداء الطلاب.

الطالب: {student_name}
المادة: {subject_name}
الأخطاء:
{wrong_summary}

حلّل هذه الأخطاء وقدّم:
1. المواضيع الأكثر ضعفاً (مرتبة حسب الأهمية)
2. سبب محتمل لكل خطأ
3. خطوات عملية للمراجعة

اكتب بإيجاز وبأسلوب تعليمي مفيد، 4-6 جمل."""

    try:
        client   = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert educational analyst."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=500,
            temperature=0.6,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ تعذّر التحليل: {e}"


def generate_hw_feedback(
    student_name: str,
    hw_title: str,
    grade: int,
    teacher_notes: str = "",
    lang: str = "ar",
) -> str:
    """
    Generate AI-enhanced feedback for a homework submission.
    """
    prompt = f"""أنت مساعد تعليمي ذكي.

الطالب: {student_name}
الواجب: {hw_title}
الدرجة: {grade}/100
ملاحظات المعلم: {teacher_notes or 'لا توجد'}

اكتب تغذية راجعة مكملة لملاحظات المعلم، بأسلوب تشجيعي وبناء.
3-4 جمل فقط."""

    try:
        client   = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful educational AI assistant."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ تعذّر توليد التغذية الراجعة: {e}"
