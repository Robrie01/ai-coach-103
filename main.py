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
if "username" not in st.session_state:
    st.session_state.username = ""
if "login_attempted" not in st.session_state:
    st.session_state.login_attempted = False

if not st.session_state.authenticated:
    st.title("🔐 Login to Access AI Interview Coach")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        if check_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username.strip().lower()
            st.rerun()
        else:
            st.session_state.login_attempted = True
    if st.session_state.login_attempted:
        st.error("❌ Invalid username or password.")
    st.stop()

# ------------------ LOGOUT ------------------
with st.sidebar:
    if st.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ------------------ OPENAI API ------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ------------------ PROFILE MANAGEMENT ------------------
PROFILE_STORE = "profiles.json"

def load_profiles():
    if pathlib.Path(PROFILE_STORE).exists():
        with open(PROFILE_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

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
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"OpenAI CV analysis error: {e}")
        return {}
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

def generate_interview_answer(question, profile_bundle):
    full_profile = profile_bundle["profile"]
    full_profile["advancedQA"] = profile_bundle.get("advanced", [])
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

username = st.session_state.username
all_profiles = st.session_state.profiles

if username not in all_profiles:
    st.subheader("👤 Set Up Your Profile")
    name = st.text_input("Full Name *", "")
    uploaded_file = st.file_uploader("Optional: Upload your CV (PDF or DOCX)", type=["pdf", "docx"])
    if st.button("Create Profile") and name.strip():
        profile_data = {
            "name": name.strip(),
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
        if uploaded_file:
            cv_text = extract_cv_text(uploaded_file)
            if cv_text:
                profile_data["cvText"] = cv_text
                filled = autofill_profile_from_cv(cv_text)
                for key in ["name", "title", "location", "goals"]:
                    profile_data[key] = filled.get(key, profile_data.get(key, ""))
                for key in ["skills", "softSkills", "learning", "certifications"]:
                    value = filled.get(key, "")
                    if isinstance(value, list):
                        profile_data[key] = [s.strip() for s in value]
                    elif isinstance(value, str):
                        profile_data[key] = [s.strip() for s in value.split(",")]
                    else:
                        profile_data[key] = []
                profile_data["experience"] = filled.get("experience", [])
        all_profiles[username] = {"profile": profile_data, "advanced": []}
        save_profiles(all_profiles)
        st.rerun()
    st.stop()

user_profile = all_profiles[username]
profile = user_profile["profile"]
advanced_qna = user_profile["advanced"]

# ------------------ PROFILE EDIT ------------------
with st.expander("📝 Edit Profile"):
    profile["name"] = st.text_input("Name", profile["name"])
    profile["title"] = st.text_input("Job Title", profile["title"])
    profile["location"] = st.text_input("Location", profile["location"])
    profile["experience"] = st.text_area(
        "Experience",
        "\n".join(str(item) if not isinstance(item, str) else item for item in profile["experience"])
    ).split("\n")
    profile["skills"] = st.text_area("Technical Skills", ", ".join(str(item).strip() for item in profile["skills"] if str(item).strip())).split(", ")
    profile["softSkills"] = st.text_area("Soft Skills", ", ".join(str(item).strip() for item in profile["softSkills"] if str(item).strip())).split(", ")
    profile["learning"] = st.text_area("Currently Learning", ", ".join(str(item).strip() for item in profile["learning"] if str(item).strip())).split(", ")
    profile["certifications"] = st.text_area("Certifications", ", ".join(str(item).strip() for item in profile["certifications"] if str(item).strip())).split(", ")
    profile["goals"] = st.text_area("Career Goals", profile["goals"])
    if st.button("💾 Save Profile"):
        save_profiles(all_profiles)
        st.success("Profile saved.")

# ------------------ CV REUPLOAD ------------------
with st.expander("📄 Upload or Replace CV"):
    if profile.get("cvText"):
        st.markdown("✅ A CV is already uploaded and stored for this profile.")
    uploaded_file = st.file_uploader("Upload your CV (PDF or DOCX)", type=["pdf", "docx"])
    if uploaded_file:
        cv_text = extract_cv_text(uploaded_file)
        if cv_text:
            profile["cvText"] = cv_text
            filled = autofill_profile_from_cv(cv_text)
            for key in ["name", "title", "location", "goals"]:
                profile[key] = filled.get(key, profile.get(key, ""))
            for key in ["skills", "softSkills", "learning", "certifications"]:
                value = filled.get(key, "")
                if isinstance(value, list):
                    profile[key] = [s.strip() for s in value]
                elif isinstance(value, str):
                    profile[key] = [s.strip() for s in value.split(",")]
                else:
                    profile[key] = []
            profile["experience"] = filled.get("experience", [])
            save_profiles(all_profiles)
            st.success("CV uploaded and profile updated.")
        else:
            st.error("Could not extract text from this file.")

          # ------------------ ADVANCED Q&A ------------------
st.markdown("---")
st.subheader("🧠 Get to Know Me")

if len(advanced_qna) >= 50:
    st.warning("You’ve reached the 50-question limit. Please delete some before continuing.")
else:
    if st.button("Start Advanced Q&A"):
        st.session_state.gk_mode = True
        st.session_state.gk_index = 0
        st.session_state.gk_answers = []
        question_prompt = (
            "Ask me one highly personal, unique question that helps you deeply understand my character, motivations, challenges, values, or ambitions."
            " Return only a JSON list with one question, like this: [\"Your question here\"]."
            " Avoid repeating previous questions or rephrasing the same idea."
        )
        try:
            res = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": question_prompt}]
            )
            question_list = json.loads(res.choices[0].message.content)
            st.session_state.gk_questions = [question_list[0]]
            st.session_state.gk_index = 0
        except Exception as e:
            st.error(f"OpenAI error: {e}")
            st.stop()

if st.session_state.get("gk_mode", False):
    if len(st.session_state.gk_questions) > 0:
        current_q = st.session_state.gk_questions[st.session_state.gk_index]
        st.write(current_q)
        user_input = st.text_area("Your answer", value="", height=150, key=f"gk_input_{current_q}")
        col1, col2 = st.columns(2)
        if col1.button("✅ Submit Answer", key="submit_answer"):
            st.session_state.gk_answers.append({"q": current_q, "a": user_input})
            question_prompt = (
                "Ask me one insightful, unique question about my professional background that hasn't been asked yet. "
                "Avoid rephrasing or repeating any of the following questions I've already answered: "
                f"{[q['q'] for q in st.session_state.gk_answers]}. "
                "Return only a JSON list with one question, like this: [\"Your question here\"]"
            )
            try:
                res = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": question_prompt}]
                )
                content = res.choices[0].message.content.strip()
                try:
                    question_list = json.loads(content)
                    if isinstance(question_list, list) and question_list:
                        st.session_state.gk_questions = [question_list[0]]
                        st.rerun()
                    else:
                        st.error("Unexpected format from OpenAI. No question returned.")
                        st.stop()
                except Exception as e:
                    st.error(f"OpenAI returned invalid JSON: {e}")
                    st.stop()
                
            except Exception as e:
                st.error(f"OpenAI error: {e}")
                st.stop()
        if col2.button("🚪 Exit", key="exit_gk"):
            st.session_state.gk_mode = False
            advanced_qna.extend(st.session_state.gk_answers)
            save_profiles(all_profiles)
            st.rerun()
        st.stop()
    else:
        advanced_qna.extend(st.session_state.gk_answers)
        save_profiles(all_profiles)
        st.session_state.gk_mode = False
        st.success("🎉 All questions saved.")

with st.expander("🔍 View & Manage Advanced Q&A"):
    for i, item in enumerate(advanced_qna):
        st.markdown(f"**Q{i+1}:** {item['q']}")
        answer = st.text_area("Answer", item["a"], key=f"edit_a_{i}")
        col1, col2 = st.columns(2)
        if col1.button(f"💾 Save Q{i+1}", key=f"save_{i}"):
            advanced_qna[i]["a"] = answer
            save_profiles(all_profiles)
            st.success(f"Saved Q{i+1}")
        if col2.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
            del advanced_qna[i]
            save_profiles(all_profiles)
            st.rerun()

# ------------------ INTERVIEW SIMULATION ------------------
st.markdown("---")
st.subheader("💬 Interview Simulator")
question_input = st.text_input("Enter your interview question")
if st.button("Generate Answer") and question_input:
    with st.spinner("Thinking..."):
        answer = generate_interview_answer(question_input, user_profile)
        st.markdown("---")
        st.subheader("🗣️ Answer:")
        st.write(answer)
        if st.button("📄 Export as PDF"):
            filename = save_to_pdf(question_input, answer)
            st.success(f"Saved as {filename}")
