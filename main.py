import streamlit as st
import openai
import json
import os
import pathlib
import datetime
from fpdf import FPDF
import docx2txt
import PyPDF2

st.set_page_config(page_title="AI Interview Coach", layout="centered", initial_sidebar_state="expanded")

# ------------------ PROFILE LOADING ------------------
import requests

def load_profiles():
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"}
    gist_url = f"https://api.github.com/gists/{st.secrets['GIST_ID']}"
    try:
        res = requests.get(gist_url, headers=headers)
        res.raise_for_status()
        gist_data = res.json()
        content = gist_data["files"]["profiles.json"]["content"]
        return json.loads(content)
    except Exception as e:
        st.warning(f"Could not load profiles from Gist: {e}")
        return {}

def save_profiles(profiles):
    headers = {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{st.secrets['GIST_ID']}"
    updated_data = {
        "files": {
            "profiles.json": {
                "content": json.dumps(profiles, indent=2)
            }
        }
    }
    try:
        res = requests.patch(gist_url, headers=headers, data=json.dumps(updated_data))
        res.raise_for_status()
    except Exception as e:
        st.error(f"Failed to save profiles to Gist: {e}")

# ------------------ LOGIN SYSTEM ------------------
def check_login(username, password):
    username = username.strip().lower()
    # Check Gist profiles first
    all_profiles = st.session_state.get("profiles", {})
    if username in all_profiles and all_profiles[username].get("settings", {}).get("password") == password:
        return True
    # Fallback to secrets
    users = st.secrets.get("users", {})
    return username in users and password == users[username]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "login_attempted" not in st.session_state:
    st.session_state.login_attempted = False

if "profiles" not in st.session_state:
    st.session_state.profiles = load_profiles()

if not st.session_state.authenticated:
    st.title("🔐 Login to Access AI Interview Coach")
    form_tabs = st.tabs(["Login", "Sign Up"])

    with form_tabs[0]:
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

    with form_tabs[1]:
        with st.form("signup_form"):
            new_email = st.text_input("Email")
            new_username = st.text_input("Create Username")
            new_password = st.text_input("Create Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted_signup = st.form_submit_button("Sign Up")
        if submitted_signup:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            elif new_username.strip().lower() in st.session_state.profiles:
                st.error("Username already exists.")
            else:
                all_profiles = st.session_state.profiles
                if "pending_signups" not in all_profiles:
                    all_profiles["pending_signups"] = []
                all_profiles["pending_signups"].append({
                    "email": new_email,
                    "username": new_username.strip().lower(),
                    "password": new_password
                })
                save_profiles(all_profiles)
                st.session_state.profiles = all_profiles
                st.success("Signup request sent for approval.")

    st.stop()

# ------------------ DELETE CONFIRMATION POPUP ------------------
all_profiles = st.session_state.profiles
if st.session_state.get("confirm_delete_user"):
    user_to_delete = st.session_state["confirm_delete_user"]
    st.warning(f"Are you sure you want to delete user: {user_to_delete}?")
    col1, col2 = st.columns([1, 1])
    if col1.button("✅ Yes, delete user"):
        if all_profiles.get(user_to_delete, {}).get("super_admin"):
            st.error("❌ This user is a super admin and cannot be deleted.")
        else:
            del all_profiles[user_to_delete]
            save_profiles(all_profiles)
            st.success(f"User {user_to_delete} deleted.")
        del st.session_state["confirm_delete_user"]
        st.rerun()
    if col2.button("❌ Cancel"):
        del st.session_state["confirm_delete_user"]
        st.rerun()

# ------------------ DARK MODE TOGGLE ------------------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

with st.sidebar:
    dark_mode_toggle = st.checkbox("🌙 Enable Dark Mode", value=st.session_state.dark_mode)
    st.session_state.dark_mode = dark_mode_toggle

if st.session_state.dark_mode:
    st.markdown("""
        <style>
        html, body, .stApp {
            background-color: #0e1117;
            color: #f0f0f0;
        }
        .stTextInput input, .stTextArea textarea {
            background-color: #262730;
            color: #f0f0f0;
        }
        .stButton>button {
            background-color: #202231;
            color: #ffffff;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #1e1e2f;
            color: #f0f0f0;
        }
        .stSidebar {
            background-color: #111827;
        }
        .stFileUploader, .stFileUploader label {
            background-color: #262730;
            color: #f0f0f0;
        }
        .streamlit-expanderHeader {
            background-color: #1e1e2f;
            color: #f0f0f0;
        }
        .streamlit-expanderContent {
            background-color: #0e1117;
        }
        a {
            color: #58a6ff;
        }
        </style>
    """, unsafe_allow_html=True)

# ------------------ LOGOUT ------------------
username = st.session_state.username
all_profiles = st.session_state.profiles

with st.sidebar:
    if all_profiles.get(username, {}).get("is_admin") or all_profiles.get(username, {}).get("super_admin"):
        if all_profiles.get(username, {}).get("super_admin"):
          st.markdown("🛡️ **Super Admin Account**")
        else:
          st.markdown("🛡️ **Admin Account**")

    if st.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if all_profiles.get(username, {}).get("is_admin") or all_profiles.get(username, {}).get("super_admin"):
        with st.expander("🧾 Approve Sign Ups"):
            pending = all_profiles.get("pending_signups", [])
            if pending:
                for i, req in enumerate(pending):
                    st.write(f"**{req['username']}** ({req['email']})")
                    col1, col2 = st.columns([1, 1])
                    if col1.button(f"✅ Approve {i}"):
                        all_profiles[req["username"]] = {
                            "settings": {
                                "username": req["username"],
                                "password": req["password"]
                            },
                            "is_admin": False,
                            "profile": {
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
                            },
                            "advanced": []
                        }
                        save_profiles(all_profiles)
                        del all_profiles["pending_signups"][i]
                        st.rerun()
                    if col2.button(f"❌ Deny {i}"):
                        del all_profiles["pending_signups"][i]
                        save_profiles(all_profiles)
                        st.rerun()
            else:
                st.info("No pending signups.")

        with st.expander("🧑‍💼 Manage Users"):
            for user, data in all_profiles.items():
                if user not in ["pending_signups"] and user != username:
                    user_settings = data.get("settings", {})
                    is_super_admin = data.get("super_admin", False)
                    col1, col2, col3 = st.columns([2, 1, 1], gap="small")
                    col1.write(f"👤 {user_settings.get('username', user)}")
                    is_admin = data.get("is_admin", False)
                    if not is_super_admin and col2.checkbox("Admin", value=is_admin, key=f"admin_toggle_{user}") != is_admin:
                        all_profiles[user]["is_admin"] = not is_admin
                        save_profiles(all_profiles)
                        st.rerun()
                    if not is_super_admin and col3.button(f"❌ Delete {user}", key=f"delete_user_btn_{user}"):
                        st.session_state["confirm_delete_user"] = user
                        st.rerun()
                    

# ------------------ OPENAI API ------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ------------------ PROFILE MANAGEMENT ------------------
PROFILE_STORE = "profiles.json"

import requests

def load_profiles():
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"}
    gist_url = f"https://api.github.com/gists/{st.secrets['GIST_ID']}"
    try:
        res = requests.get(gist_url, headers=headers)
        res.raise_for_status()
        gist_data = res.json()
        content = gist_data["files"]["profiles.json"]["content"]
        return json.loads(content)
    except Exception as e:
        st.warning(f"Could not load profiles from Gist: {e}")
        return {}

def save_profiles(profiles):
    headers = {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{st.secrets['GIST_ID']}"
    updated_data = {
        "files": {
            "profiles.json": {
                "content": json.dumps(profiles, indent=2)
            }
        }
    }
    try:
        res = requests.patch(gist_url, headers=headers, data=json.dumps(updated_data))
        res.raise_for_status()
    except Exception as e:
        st.error(f"Failed to save profiles to Gist: {e}")

def extract_cv_text(uploaded_file):
    if uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif uploaded_file.name.endswith(".docx"):
        return docx2txt.process(uploaded_file)
    return ""

def autofill_profile_from_cv(cv_text):
    import re
    # Pre-cleaning: remove excess whitespace, tabs, and bullet characters
    cleaned_cv = re.sub(r'[•●▪︎◦\-\u2022\u25AA]+', '', cv_text)
    cleaned_cv = re.sub(r'\n+', '\n', cleaned_cv)
    trimmed_cv = cleaned_cv[:3000]  # Optional: limit CV text for token safety

    prompt = (
        "You are an expert CV parser. Extract the following structured profile information as a JSON object:\n\n"
        "{\n"
        "  \"name\": string,\n"
        "  \"title\": string,\n"
        "  \"location\": string,\n"
        "  \"skills\": [string],\n"
        "  \"softSkills\": [string],\n"
        "  \"experience\": [string],\n"
        "  \"certifications\": [string],\n"
        "  \"learning\": [string],\n"
        "  \"goals\": string\n"
        "}\n\n"
        "Only return valid JSON. Use bullet points from experience and training sections. Parse the CV text below:\n\n"
        f"{trimmed_cv}"
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

def generate_interview_answer(question, profile_bundle):
    full_profile = profile_bundle["profile"]
    full_profile["advancedQA"] = profile_bundle.get("advanced", [])
    system_prompt = (
        "You are simulating interview responses based on this structured profile and CV content:\n"
        f"{json.dumps(full_profile)}\n\n"
        "Answer the following interview question in a clear, friendly, and concise way. Keep the tone approachable and avoid overly formal or robotic phrasing."
    )
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

def generate_role_question(title, description, responsibilities):
    prompt = (
        "You are an experienced interviewer preparing questions for a job candidate. "
        f"Role: {title}. Description: {description} "
        f"Responsibilities: {responsibilities}. "
        "Generate one concise interview question relevant to this position. "
        "Return only the question text."
    )
    try:
        res = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"OpenAI error: {e}")
        return ""

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
        st.session_state.profiles = all_profiles
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
        col1, col2, col3 = st.columns([1, 1, 1], gap="small")
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
        if col2.button("⏭️ Skip", key="skip_gk_btn"):
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

        if col3.button("🚪 Exit", key="exit_gk"):
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

with st.expander("Job Role"):
    job_title_input = st.text_input("Job Title for this interview", key="job_title_input")
    job_desc_input = st.text_area("Job Description", key="job_desc_input")
    job_resp_input = st.text_area("Key Responsibilities", key="job_resp_input")

col_q, col_btn = st.columns([3, 1])
if col_btn.button("Generate Question"):
    generated_q = generate_role_question(job_title_input, job_desc_input, job_resp_input)
    if generated_q:
        st.session_state.question_input = generated_q
        st.rerun()
question_input = col_q.text_input("Enter your interview question", key="question_input")

if st.button("Generate Answer") and question_input:
    with st.spinner("Thinking..."):
        answer = generate_interview_answer(question_input, user_profile)
        st.markdown("---")
        st.subheader("🗣️ Answer:")
        st.write(answer)
        if st.button("📄 Export as PDF"):
            filename = save_to_pdf(question_input, answer)
            st.success(f"Saved as {filename}")
