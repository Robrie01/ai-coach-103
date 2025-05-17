
import streamlit as st
import openai
import json
import os
import pathlib
import datetime
from fpdf import FPDF
import docx2txt
import PyPDF2

st.set_page_config(page_title="AI Interview Coach", layout="centered")

# ------------------ LOGIN SYSTEM ------------------
def check_login(username, password):
    users = st.secrets["users"]
    username = username.strip().lower()
    return username in users and password == users[username]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_attempted" not in st.session_state:
    st.session_state.login_attempted = False

if not st.session_state.authenticated:
    st.title("🔐 Login to Access Roy's AI Interview Coach")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        if check_login(username, password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.session_state.login_attempted = True
    if st.session_state.login_attempted:
        st.error("❌ Invalid username or password.")
    st.stop()

# ------------------ LOGOUT BUTTON ------------------
with st.sidebar:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.login_attempted = False
        st.rerun()

# ------------------ OPENAI SETUP ------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

def get_default_profile():
    return {
        "name": "",
        "title": "",
        "location": "",
        "experience": [],
        "skills": [],
        "softSkills": [],
        "learning": [],
        "certifications": [],
        "goals": "",
        "cvText": ""
    }

PROFILE_STORE = "profiles.json"

def load_profiles():
    if pathlib.Path(PROFILE_STORE).exists():
        with open(PROFILE_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"Default": {"basic": get_default_profile(), "advanced": []}}

def save_profiles(profiles):
    with open(PROFILE_STORE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)

def extract_cv_text(uploaded_file):
    if uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif uploaded_file.name.endswith(".docx"):
        return docx2txt.process(uploaded_file)
    return ""

def autofill_profile_from_cv(cv_text):
    prompt = (
        "Extract the following as JSON from this CV text: name, job title, location, skills (comma separated), "
        "soft skills (comma separated), experience (bullet points), certifications, learning focus, and career goals.\n"
        "CV TEXT:\n" + cv_text
    )
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

def generate_interview_answer(question, profile_bundle):
    full_profile = profile_bundle["basic"].copy()
    full_profile["advancedQA"] = profile_bundle["advanced"]
    system_prompt = (
        "You are simulating interview responses based on this structured profile and CV content:\n"
        f"{json.dumps(full_profile)}\n\n"
        "Answer the following interview question in a clear, confident, and tailored way."
    )
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

def save_to_pdf(question, answer):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"Question: {question}\n\nAnswer: {answer}")
    filename = f"interview_answer_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    return filename

# ------------------ STATE INIT ------------------
if "profiles" not in st.session_state:
    st.session_state.profiles = load_profiles()
if "selected_profile" not in st.session_state:
    st.session_state.selected_profile = "Default"
if "gk_mode" not in st.session_state:
    st.session_state.gk_mode = False
if "gk_questions" not in st.session_state:
    st.session_state.gk_questions = []
if "gk_answers" not in st.session_state:
    st.session_state.gk_answers = []
if "gk_index" not in st.session_state:
    st.session_state.gk_index = 0

# ------------------ PROFILE MANAGER ------------------
st.sidebar.header("👤 Profile Manager")
profile_names = list(st.session_state.profiles.keys())
selected = st.sidebar.selectbox("Choose a profile", profile_names)
st.session_state.selected_profile = selected

new_profile_name = st.sidebar.text_input("New profile name")
if st.sidebar.button("➕ Save New Profile") and new_profile_name:
    st.session_state.profiles[new_profile_name] = {"basic": get_default_profile(), "advanced": []}
    st.session_state.selected_profile = new_profile_name
    save_profiles(st.session_state.profiles)
    st.rerun()

current_profile = st.session_state.profiles[st.session_state.selected_profile]
profile = current_profile["basic"]
advanced_qna = current_profile["advanced"]

# ------------------ CV UPLOAD ------------------
with st.expander("📄 Upload or Replace CV"):
    uploaded_file = st.file_uploader("Upload your CV (PDF or DOCX)", type=["pdf", "docx"])
    if uploaded_file:
        cv_text = extract_cv_text(uploaded_file)
        if cv_text:
            profile["cvText"] = cv_text
            filled = autofill_profile_from_cv(cv_text)
            for key in ["name", "title", "location", "goals"]:
                profile[key] = filled.get(key, profile.get(key, ""))
            for key in ["skills", "softSkills", "learning", "certifications"]:
                profile[key] = [s.strip() for s in filled.get(key, "").split(",")]
            profile["experience"] = filled.get("experience", [])
            save_profiles(st.session_state.profiles)
            st.success("CV uploaded and profile updated.")
        else:
            st.error("Could not extract text from this file.")

# ------------------ GET TO KNOW ME ------------------
st.markdown("---")
st.subheader("🧠 Get to Know Me Better")

if len(advanced_qna) >= 50:
    st.warning("You’ve reached the 50-question limit. Please delete previous Q&A before continuing.")
else:
    if st.button("Start Advanced Q&A"):
        st.session_state.gk_mode = True
        st.session_state.gk_index = 0
        st.session_state.gk_answers = []
        question_prompt = (
            "Generate 3 insightful and unique questions to learn about someone's "
            "professional background and personality to improve personalized advice. "
            "Return them as a JSON list of strings."
        )
        res = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question_prompt}]
        )
        st.session_state.gk_questions = json.loads(res.choices[0].message.content)
        st.rerun()

if st.session_state.gk_mode and st.session_state.gk_index < len(st.session_state.gk_questions):
    current_q = st.session_state.gk_questions[st.session_state.gk_index]
    st.write(f"**Q{st.session_state.gk_index + 1}:** {current_q}")
    user_input = st.text_area("Your answer", height=150, key=f"gk_input_{st.session_state.gk_index}")
    col1, col2 = st.columns(2)
    if col1.button("✅ Submit Answer", key="submit_answer"):
        st.session_state.gk_answers.append({"q": current_q, "a": user_input})
        st.session_state.gk_index += 1
        st.rerun()
    if col2.button("🚪 Exit", key="exit_gk"):
        st.session_state.gk_mode = False
        advanced_qna.extend(st.session_state.gk_answers)
        save_profiles(st.session_state.profiles)
        st.rerun()
    st.stop()
elif st.session_state.gk_mode:
    advanced_qna.extend(st.session_state.gk_answers)
    save_profiles(st.session_state.profiles)
    st.session_state.gk_mode = False
    st.success("🎉 All questions answered and saved.")

# ------------------ ADVANCED Q&A VIEW ------------------
with st.expander("🔍 View & Manage Advanced Q&A"):
    for i, item in enumerate(advanced_qna):
        st.markdown(f"**Q{i+1}:** {item['q']}")
        answer = st.text_area("Answer", item["a"], key=f"edit_a_{i}")
        col1, col2 = st.columns(2)
        if col1.button(f"💾 Save Q{i+1}", key=f"save_{i}"):
            advanced_qna[i]["a"] = answer
            save_profiles(st.session_state.profiles)
            st.success(f"Saved Q{i+1}")
        if col2.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
            del advanced_qna[i]
            save_profiles(st.session_state.profiles)
            st.rerun()

# ------------------ INTERVIEW SIMULATOR ------------------
st.markdown("---")
st.subheader("💬 Interview Simulator")
question_input = st.text_input("Enter your interview question")
if st.button("Generate Answer") and question_input:
    with st.spinner("Thinking..."):
        answer = generate_interview_answer(question_input, current_profile)
        st.markdown("---")
        st.subheader("🗣️ Answer:")
        st.write(answer)
        if st.button("📄 Export as PDF"):
            filename = save_to_pdf(question_input, answer)
            st.success(f"Saved as {filename}")
