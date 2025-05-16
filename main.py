import streamlit as st
st.set_page_config(page_title="AI Interview Assistant", layout="centered")

# THEN import or use other streamlit commands
import openai
import json
from fpdf import FPDF
import datetime
import os
import pathlib

# ------------------ LOGIN SYSTEM ------------------
#def check_login(username, password):
#    users = st.secrets["users"]
#    username = username.strip().lower()  # case-insensitive and trims spaces
#    return username in users and password == users[username]
#
#if "authenticated" not in st.session_state:
#    st.session_state.authenticated = False
#if "login_attempted" not in st.session_state:
#    st.session_state.login_attempted = False
#
#if not st.session_state.authenticated:
#    st.title("🔐 Login to Access Roy's AI Interview Coach")
#
#    with st.form("login_form"):
#        username = st.text_input("Username", value="", key="login_user")
#        password = st.text_input("Password", type="password", value="", key="login_pass")
#        submitted = st.form_submit_button("Login")
#
#    if submitted:
#        if check_login(username, password):
#            st.session_state.authenticated = True
#            st.success("✅ Login successful!")
#            st.rerun()
#       else:
#            st.session_state.login_attempted = True
#
#    if st.session_state.login_attempted:
#        st.error("❌ Invalid username or password.")
#    st.stop()
#
# ------------------ LOGOUT ------------------
if st.session_state.get("authenticated", False):
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.login_attempted = False
            st.experimental_rerun()
            
# ------------------ SETUP ------------------
openai.api_key = os.environ["OPENAI_API_KEY"]

def get_default_profile():
    return {
        "name": [],
        "title": [],
        "location": [],
        "experience": [],
        "skills": [],
        "softSkills": [],
        "learning": [],
        "certifications": [],
        "goals": ""
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
if "new_profile_name" not in st.session_state:
    st.session_state.new_profile_name = ""

def generate_interview_answer(question, profile_bundle):
    full_profile = profile_bundle["basic"].copy()
    full_profile["advancedQA"] = profile_bundle["advanced"]
    system_prompt = (
        "You are simulating interview responses for a candidate based on the following profile.\n"
        f"{json.dumps(full_profile)}\n\n"
        "Answer the following interview question clearly and confidently."
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
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interview_answer_{timestamp}.pdf"
    pdf.output(filename)
    return filename

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="AI Interview Assistant", layout="centered")
st.title("🧠 Roy's AI Interview Coach")

# ------------------ PROFILE MANAGER ------------------
st.sidebar.header("👤 Profile Manager")
profile_names = list(st.session_state.profiles.keys())
selected = st.sidebar.selectbox("Choose a profile", profile_names)
st.session_state.selected_profile = selected

st.sidebar.text_input("New profile name", key="new_profile_name")
if st.sidebar.button("💾 Save New Profile"):
    name = st.session_state.new_profile_name.strip()
    if name and name not in st.session_state.profiles:
        st.session_state.profiles[name] = {"basic": get_default_profile(), "advanced": []}
        st.session_state.selected_profile = name
        save_profiles(st.session_state.profiles)
        st.rerun()

current_profile = st.session_state.profiles[st.session_state.selected_profile]
profile = current_profile["basic"]
advanced_qna = current_profile["advanced"]

# ------------------ PROFILE EDIT ------------------
with st.expander("📝 Edit Basic Profile"):
    profile["name"] = st.text_input("Name", profile["name"])
    profile["title"] = st.text_input("Job Title", profile["title"])
    profile["location"] = st.text_input("Location", profile["location"])
    profile["experience"] = st.text_area("Experience (as bullet points)", "\n".join(profile["experience"])).split("\n")
    profile["skills"] = st.text_area("Technical Skills (comma-separated)", ", ".join(profile["skills"])).split(", ")
    profile["softSkills"] = st.text_area("Soft Skills (comma-separated)", ", ".join(profile["softSkills"])).split(", ")
    profile["learning"] = st.text_area("Currently Learning", ", ".join(profile["learning"])).split(", ")
    profile["certifications"] = st.text_area("Certifications", ", ".join(profile["certifications"])).split(", ")
    profile["goals"] = st.text_area("Career Goals", profile["goals"])
    save_profiles(st.session_state.profiles)

# ------------------ GET TO KNOW ME ------------------
if st.button("🧠 Get to Know Me Better"):
    st.session_state.gk_mode = True
    st.session_state.gk_index = 0
    st.session_state.gk_answers = []

    question_prompt = (
        "Generate 3 insightful and unique questions to learn about someone's "
        "professional background and personality to improve personalized advice. "
        "Return them as a JSON list of strings."
    )
    try:
        res = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question_prompt}]
        )
        st.session_state.gk_questions = json.loads(res.choices[0].message.content)
    except Exception as e:
        st.error("Failed to generate questions.")
        st.session_state.gk_mode = False
    st.rerun()

if st.session_state.gk_mode and st.session_state.gk_questions and st.session_state.gk_index < len(st.session_state.gk_questions):
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
        st.session_state.profiles[st.session_state.selected_profile]["advanced"].extend(st.session_state.gk_answers)
        save_profiles(st.session_state.profiles)
        st.rerun()

    st.stop()
elif st.session_state.gk_mode:
    st.session_state.profiles[st.session_state.selected_profile]["advanced"].extend(st.session_state.gk_answers)
    save_profiles(st.session_state.profiles)
    st.session_state.gk_mode = False
    st.success("🎉 All questions answered and saved.")

# ------------------ ADVANCED Q&A ------------------
with st.expander("🔍 View Advanced Q&A"):
    for i, item in enumerate(advanced_qna):
        edited_answer = st.text_area(f"Q{i+1}: {item['q']}", value=item["a"], key=f"edit_{i}")
        if st.button(f"💾 Save Edit Q{i+1}", key=f"save_edit_{i}"):
            advanced_qna[i]["a"] = edited_answer
            save_profiles(st.session_state.profiles)
            st.success(f"Answer to Q{i+1} updated.")
        if st.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
            del advanced_qna[i]
            save_profiles(st.session_state.profiles)
            st.rerun()

# ------------------ INTERVIEW SIM ------------------
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
