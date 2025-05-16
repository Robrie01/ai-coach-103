
# Full integrated version of AI Interview Coach
import streamlit as st
import openai
import json
import pathlib
import datetime
from fpdf import FPDF
from io import BytesIO
import docx2txt
import PyPDF2

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

# ------------------ SETUP ------------------
openai.api_key = os.environ["OPENAI_API_KEY"]

def get_default_profile():
    return {
        "name": "Roy O’Brien",
        "title": "IT Systems Technician",
        "location": "Derry, Northern Ireland",
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

# ------------------ UI SETUP ------------------
st.set_page_config(page_title="AI Interview Coach", layout="centered")
st.title("🧠 Roy's AI Interview Coach")

# Profile Manager
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

# CV Upload
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

# Edit Profile
with st.expander("📝 Edit Basic Profile"):
    profile["name"] = st.text_input("Name", profile["name"])
    profile["title"] = st.text_input("Job Title", profile["title"])
    profile["location"] = st.text_input("Location", profile["location"])
    profile["experience"] = st.text_area("Experience", "\n".join(profile["experience"])).split("\n")
    profile["skills"] = st.text_area("Technical Skills", ", ".join(profile["skills"])).split(", ")
    profile["softSkills"] = st.text_area("Soft Skills", ", ".join(profile["softSkills"])).split(", ")
    profile["learning"] = st.text_area("Currently Learning", ", ".join(profile["learning"])).split(", ")
    profile["certifications"] = st.text_area("Certifications", ", ".join(profile["certifications"])).split(", ")
    profile["goals"] = st.text_area("Career Goals", profile["goals"])
    save_profiles(st.session_state.profiles)

# Get to Know Me
if st.button("🧠 Get to Know Me Better"):
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
    st.subheader("🧠 Getting to Know You")
    st.write(current_q)
    user_input = st.text_area("Your answer", height=200, key=f"gk_input_{st.session_state.gk_index}")
    col1, col2 = st.columns(2)
    if col1.button("✅ Submit Answer", key="submit_answer"):
        st.session_state.gk_answers.append({"q": current_q, "a": user_input})
        st.session_state.gk_index += 1
        st.rerun()
    if col2.button("🚪 Exit", key="exit_gk"):
        st.session_state.gk_mode = False
        current_profile["advanced"].extend(st.session_state.gk_answers)
        save_profiles(st.session_state.profiles)
        st.rerun()
    st.stop()
elif st.session_state.gk_mode:
    current_profile["advanced"].extend(st.session_state.gk_answers)
    save_profiles(st.session_state.profiles)
    st.session_state.gk_mode = False
    st.success("🎉 All questions answered and saved.")

# Advanced Q&A Edit
with st.expander("🔍 View Advanced Q&A"):
    for i, item in enumerate(current_profile["advanced"]):
        edited = st.text_area(f"Q{i+1}: {item['q']}", value=item["a"], key=f"edit_{i}")
        if st.button(f"💾 Save Edit Q{i+1}", key=f"save_{i}"):
            current_profile["advanced"][i]["a"] = edited
            save_profiles(st.session_state.profiles)
            st.success(f"Q{i+1} updated.")
        if st.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
            del current_profile["advanced"][i]
            save_profiles(st.session_state.profiles)
            st.rerun()

# Interview
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
