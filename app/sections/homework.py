import streamlit as st
from app.core.security import get_supabase
from app.services.progress_service import ProgressService


def render_homework(config: dict, student_id: str, lang: str, section_id: str):
    hw_id = config.get("hw_id")
    if not hw_id:
        st.info("لم يتم ربط واجب بهذا القسم.")
        return

    sb = get_supabase()

    try:
        done = sb.table("results").select("id, score, total")\
                 .eq("student_id", student_id).eq("hw_id", hw_id).execute()
        if done.data:
            r   = done.data[0]
            pct = round(r["score"]/r["total"]*100) if r["total"] else 0
            st.success(f"✅ {'سلّمت الواجب' if lang=='ar' else 'Submitted'} — {r['score']}/{r['total']} ({pct}%)")
            return
    except Exception:
        pass

    try:
        hw = sb.table("homework").select("*").eq("id", hw_id).single().execute()
        if not hw.data:
            st.error("الواجب غير موجود")
            return
        qs = sb.table("questions").select("*").eq("hw_id", hw_id)\
               .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    st.markdown(f"**📚 {hw.data['title']}**")
    if hw.data.get("deadline"):
        st.caption(f"⏰ {'الموعد النهائي' if lang=='ar' else 'Deadline'}: {str(hw.data['deadline'])[:10]}")

    if not qs:
        st.info("لا توجد أسئلة.")
        return

    answers = {}
    with st.form(f"hw_form_{hw_id}"):
        for i, q in enumerate(qs):
            st.markdown(f"**{i+1}. {q['question_text']}**")
            opts = {k: q[k] for k in ["option_a","option_b","option_c","option_d"] if q.get(k)}
            chosen = st.radio("", list(opts.values()),
                              key=f"hwq_{hw_id}_{q['id']}", index=None)
            answers[q["id"]] = {"chosen": chosen, "correct": q["correct_answer"],
                                 "opts": opts, "topic": q.get("topic",""),
                                 "points": q.get("points",1)}
            st.divider()
        if st.form_submit_button("✅ " + ("تسليم الواجب" if lang=="ar" else "Submit"),
                                 use_container_width=True, type="primary"):
            score = 0; total = 0; weak = []
            opt_map = {"a":"option_a","b":"option_b","c":"option_c","d":"option_d"}
            for qid, ans in answers.items():
                total += ans["points"]
                ck = ans["correct"].lower()
                cv = ans["opts"].get(opt_map.get(ck,ck), ans["correct"])
                if ans["chosen"] == cv:
                    score += ans["points"]
                elif ans["topic"]:
                    weak.append(ans["topic"])
            try:
                sb.table("results").insert({
                    "student_id": student_id,
                    "hw_id": hw_id,
                    "score": score, "total": total,
                    "weak_topics": list(set(weak)),
                }).execute()
                ProgressService().mark_section_complete(student_id, section_id)
                st.success(f"✅ {score}/{total}")
                st.rerun()
            except Exception as e:
                st.error(f"خطأ: {e}")
