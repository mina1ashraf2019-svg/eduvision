import streamlit as st
import time
from app.core.security import get_supabase
from app.services.progress_service import ProgressService


def render_quiz(config: dict, student_id: str, lang: str, section_id: str):
    exam_id  = config.get("exam_id")
    duration = config.get("duration_minutes", 30)
    if not exam_id:
        st.info("لم يتم ربط امتحان بهذا القسم بعد.")
        return

    sb = get_supabase()

    # Check already submitted
    try:
        done = sb.table("results").select("id, score, total, submitted_at")\
                 .eq("student_id", student_id).eq("exam_id", exam_id).execute()
        if done.data:
            r   = done.data[0]
            pct = round(r["score"]/r["total"]*100) if r["total"] else 0
            col = "success" if pct >= 60 else "error"
            getattr(st, col)(f"{'درجتك' if lang=='ar' else 'Your score'}: {r['score']}/{r['total']} ({pct}%)")
            return
    except Exception:
        pass

    # Load exam
    try:
        exam = sb.table("exams").select("*").eq("id", exam_id).single().execute()
        if not exam.data:
            st.error("الامتحان غير موجود")
            return
        exam = exam.data
        qs   = sb.table("questions").select("*").eq("exam_id", exam_id)\
                 .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ في تحميل الامتحان: {e}")
        return

    st.markdown(f"**📝 {exam['title']}** — {duration} {'دقيقة' if lang=='ar' else 'min'}")

    if not qs:
        st.info("لا توجد أسئلة في هذا الامتحان.")
        return

    form_key = f"quiz_form_{exam_id}"
    answers  = {}

    with st.form(form_key):
        for i, q in enumerate(qs):
            st.markdown(f"**{i+1}. {q['question_text']}**")
            opts = {k: q[k] for k in ["option_a","option_b","option_c","option_d"] if q.get(k)}
            chosen = st.radio("", list(opts.values()),
                              key=f"q_{exam_id}_{q['id']}", index=None)
            answers[q["id"]] = {"chosen": chosen, "correct": q["correct_answer"],
                                 "opts": opts, "topic": q.get("topic",""),
                                 "points": q.get("points",1)}
            st.divider()

        submitted = st.form_submit_button(
            "✅ " + ("تسليم الامتحان" if lang=="ar" else "Submit Exam"),
            use_container_width=True, type="primary"
        )

    if submitted:
        score = 0; total = 0; weak = []
        opt_map = {"a":"option_a","b":"option_b","c":"option_c","d":"option_d"}
        for qid, ans in answers.items():
            total += ans["points"]
            correct_key = ans["correct"].lower()
            correct_val = ans["opts"].get(opt_map.get(correct_key, correct_key), ans["correct"])
            if ans["chosen"] == correct_val:
                score += ans["points"]
            elif ans["topic"]:
                weak.append(ans["topic"])

        try:
            sb.table("results").insert({
                "student_id": student_id,
                "exam_id":    exam_id,
                "score":      score,
                "total":      total,
                "weak_topics": list(set(weak)),
            }).execute()
            pct = round(score/total*100) if total else 0
            if pct >= 60:
                st.success(f"🎉 {score}/{total} ({pct}%)")
            else:
                st.error(f"❌ {score}/{total} ({pct}%) — تحتاج مراجعة")
            ProgressService().mark_section_complete(student_id, section_id)
            st.rerun()
        except Exception as e:
            st.error(f"خطأ في التسليم: {e}")
