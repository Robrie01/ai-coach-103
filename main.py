import streamlit as st
st.set_page_config(page_title="AI Interview Assistant", layout="centered")

import openai
import json
import datetime
import os
import pathlib
import requests
import base64
from fpdf import FPDF

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
        username = st.text_input("Username", value="", key="login_user")
        password = st.text_input("Password", type="password", value="", key="login_pass")
        submitted = st.form_submit_button("Login")
    if submitted:
        if check_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username.strip().lower()
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.session_state.login_attempted = True
    if st.session_state.login_attempted:
        st.error("❌ Invalid username or password.")
    st.stop()

if st.session_state.get("authenticated", False):
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.login_attempted = False
            st.experimental_rerun()

openai.api_key = os.environ.get("OPENAI_API_KEY")

BACKUP_FILE = "profiles_backup.json"

for key, default in {
    "gk_mode": False,
    "gk_questions": [],
    "gk_answers": [],
    "gk_index": 0,
    "new_profile_name": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

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
        "goals": ""
    }

def github_api_headers():
    return {"Authorization": f"token {st.secrets.github.token}"}

def get_github_url():
    return f"https://api.github.com/repos/{st.secrets.github.username}/{st.secrets.github.repo}/contents/{st.secrets.github.filepath}"

def load_profiles():
    try:
        url = get_github_url()
        res = requests.get(url, headers=github_api_headers())
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"])
            st.session_state.profile_sha = res.json()["sha"]
            return json.loads(content)
    except Exception:
        pass
    if pathlib.Path(BACKUP_FILE).exists():
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_profiles(profiles):
    try:
        url = get_github_url()
        encoded_content = base64.b64encode(json.dumps(profiles, indent=2).encode()).decode()
        data = {
            "message": f"Update by {st.session_state.username} at {datetime.datetime.now()}",
            "content": encoded_content,
            "sha": st.session_state.get("profile_sha"),
            "branch": "main"
        }
        res = requests.put(url, headers=github_api_headers(), json=data)
        if res.status_code == 200:
            st.success("Profiles saved to GitHub.")
            st.session_state.profile_sha = res.json()["content"]["sha"]
        else:
            st.error("Failed to save profiles to GitHub.")
    except Exception:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2)
        st.warning("GitHub unavailable, saved to local backup.")

username_key = st.session_state.username
if "profiles" not in st.session_state:
    all_profiles = load_profiles()
    st.session_state.profiles = all_profiles.get(username_key, {"Default": {"basic": get_default_profile(), "advanced": []}})
if "selected_profile" not in st.session_state:
    st.session_state.selected_profile = "Default"

def generate_interview_answer(question, profile_bundle):
    full_profile = profile_bundle["basic"].copy()
    full_profile["advancedQA"] = profile_bundle["advanced"]
    profile_data = json.dumps(full_profile)
    system_prompt = f"""
You are simulating interview responses for a candidate based on the following profile.
{profile_data}

Answer the following interview question clearly and confidently.
"""
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
    except Exception:
        st.error("Failed to generate questions.")
        st.session_state.gk_mode = False
    st.rerun()

current_profile = st.session_state.profiles[st.session_state.selected_profile]
profile = current_profile["basic"]
advanced_qna = current_profile["advanced"]

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
        current_profile["advanced"].extend(st.session_state.gk_answers)
        save_profiles({st.session_state.username: st.session_state.profiles})
        st.session_state.gk_mode = False
        st.rerun()
    st.stop()
elif st.session_state.gk_mode:
    current_profile["advanced"].extend(st.session_state.gk_answers)
    save_profiles({st.session_state.username: st.session_state.profiles})
    st.session_state.gk_mode = False
    st.success("🎉 All questions answered and saved.")

st.title("🧠 Roy's AI Interview Coach")

with st.expander("📘 View Saved 'Get to Know Me' Answers"):
    if advanced_qna:
        for i, item in enumerate(advanced_qna):
            st.markdown(f"**Q{i+1}:** {item['q']}")
            edited_answer = st.text_area(f"Edit A{i+1}:", item['a'], key=f"edit_answer_{i}")
            col1, col2 = st.columns([1, 1])
            if col1.button(f"💾 Save A{i+1}", key=f"save_edit_{i}"):
                advanced_qna[i]['a'] = edited_answer
                save_profiles({st.session_state.username: st.session_state.profiles})
                st.success(f"Answer {i+1} updated.")
            if col2.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
                del advanced_qna[i]
                save_profiles({st.session_state.username: st.session_state.profiles})
                st.experimental_rerun()
            st.markdown("---")
    else:
        st.info("No saved Q&A yet. Try 'Get to Know Me' to get started.")

st.sidebar.header("👤 Profile Manager")
profile_names = list(st.session_state.profiles.keys())
st.session_state.selected_profile = st.sidebar.selectbox("Choose a profile", profile_names)

st.sidebar.text_input("New profile name", key="new_profile_name")
if st.sidebar.button("💾 Save New Profile"):
    name = st.session_state.new_profile_name.strip()
    if name and name not in st.session_state.profiles:
        st.session_state.profiles[name] = {"basic": get_default_profile(), "advanced": []}
        st.session_state.selected_profile = name
        save_profiles({st.session_state.username: st.session_state.profiles})
        st.rerun()

current_profile = st.session_state.profiles[st.session_state.selected_profile]
profile = current_profile["basic"]
advanced_qna = current_profile["advanced"]

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
    save_profiles({st.session_state.username: st.session_state.profiles})
