import streamlit as st

TRANSLATIONS = {
    "ar": {
        "app_name": "EduVision", "app_subtitle": "منصة التعليم الذكي",
        "login": "تسجيل الدخول", "register": "حساب جديد",
        "logout": "🚪 خروج", "email": "البريد الإلكتروني",
        "password": "كلمة المرور", "confirm_password": "تأكيد كلمة المرور",
        "full_name": "الاسم الكامل", "first_name": "الاسم الأول",
        "last_name": "الاسم الأخير", "login_btn": "تسجيل الدخول",
        "register_btn": "إنشاء الحساب", "loading": "جاري التحميل...",
        "success": "تم بنجاح!", "error": "حدث خطأ!",
        "fill_all_fields": "يرجى إدخال جميع البيانات",
        "passwords_not_match": "كلمتا المرور غير متطابقتين",
        "password_too_short": "كلمة المرور أقل من 8 أحرف",
        "invalid_email": "البريد الإلكتروني غير صحيح",
        "students_only": "تسجيل الطلاب فقط",
        "teachers_added_by_admin": "المعلمون يُضافون من لوحة تحكم المشرف",
        "my_subjects": "موادي", "locked_subjects": "مواد مقفلة",
        "welcome": "أهلاً",
    },
    "en": {
        "app_name": "EduVision", "app_subtitle": "Smart Learning Platform",
        "login": "Sign In", "register": "Register",
        "logout": "🚪 Logout", "email": "Email",
        "password": "Password", "confirm_password": "Confirm Password",
        "full_name": "Full Name", "first_name": "First Name",
        "last_name": "Last Name", "login_btn": "Sign In",
        "register_btn": "Create Account", "loading": "Loading...",
        "success": "Done!", "error": "An error occurred!",
        "fill_all_fields": "Please fill in all fields",
        "passwords_not_match": "Passwords do not match",
        "password_too_short": "Password must be at least 8 characters",
        "invalid_email": "Invalid email address",
        "students_only": "Student Registration Only",
        "teachers_added_by_admin": "Teachers are added by admin",
        "my_subjects": "My Subjects", "locked_subjects": "Locked Subjects",
        "welcome": "Welcome",
    }
}

def t(key: str, lang: str = "ar") -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["ar"]).get(key, key)

def get_lang() -> str:
    if "user" in st.session_state and st.session_state.user:
        return st.session_state.user.get("language", "ar")
    return st.session_state.get("lang", "ar")
