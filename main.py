
import streamlit as st
import openai
import json
from fpdf import FPDF
import datetime
import os

# ------------------ LOGIN SYSTEM ------------------
#
#def check_login(username, password):
#    return (
#        username == st.secrets["credentials"]["username"]
#        and password == st.secrets["credentials"]["password"]
#    )
#
#if "authenticated" not in st.session_state:
#    st.session_state.authenticated = False
#
#if not st.session_state.authenticated:
#    st.title("🔐 Login to Access Roy's AI Interview Coach")
#    username = st.text_input("Username")
#    password = st.text_input("Password", type="password")
#    if st.button("Login"):
#        if check_login(username, password):
#            st.session_state.authenticated = True
#            st.experimental_rerun()
#        else:
#            st.error("Invalid credentials.")
#    st.stop()

# ------------------ SETUP ------------------
openai.api_key = os.environ["OPENAI_API_KEY"]

# ------------------ DEFAULT PROFILE ------------------
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
        "goals": ""
    }

# ------------------ FUNCTION ------------------
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

# ------------------ PDF EXPORT ------------------
def save_to_pdf(question, answer):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"Question: {question}\n\nAnswer: {answer}")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interview_answer_{timestamp}.pdf"
    pdf.output(filename)
    return filename

# ------------------ STATE INIT ------------------
if "profiles" not in st.session_state:
    st.session_state.profiles = {
        "Default": {"basic": get_default_profile(), "advanced": []}
    }
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

# ------------------ UI CONFIG ------------------
st.set_page_config(page_title="AI Interview Assistant", layout="centered")
st.title("🧠 Roy's AI Interview Coach")

# ------------------ PROFILE SELECTION ------------------
st.sidebar.header("👤 Profile Manager")
profile_names = list(st.session_state.profiles.keys())
selected = st.sidebar.selectbox("Choose a profile", profile_names)
st.session_state.selected_profile = selected

if st.sidebar.button("➕ Create New Profile"):
    new_name = st.sidebar.text_input("Enter new profile name", key="new_profile")
    if new_name and new_name not in st.session_state.profiles:
        st.session_state.profiles[new_name] = {"basic": get_default_profile(), "advanced": []}
        st.session_state.selected_profile = new_name
        st.experimental_rerun()

# Load current profile
current_profile = st.session_state.profiles[st.session_state.selected_profile]
profile = current_profile["basic"]
advanced_qna = current_profile["advanced"]

# ------------------ PROFILE EDITOR ------------------
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
    res = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": question_prompt}]
    )
    st.session_state.gk_questions = json.loads(res.choices[0].message.content)

if st.session_state.gk_mode and st.session_state.gk_index < len(st.session_state.gk_questions):
    current_q = st.session_state.gk_questions[st.session_state.gk_index]
    st.subheader("🧠 Getting to Know You")
    st.write(current_q)
    user_input = st.text_input("Your answer", key=f"gk_input_{st.session_state.gk_index}")

    col1, col2 = st.columns(2)
    if col1.button("✅ Submit Answer", key="submit_answer"):
        st.session_state.gk_answers.append({"q": current_q, "a": user_input})
        st.session_state.gk_index += 1
        st.experimental_rerun()

    if col2.button("🚪 Exit", key="exit_gk"):
        st.session_state.gk_mode = False
        st.session_state.profiles[st.session_state.selected_profile]["advanced"].extend(st.session_state.gk_answers)
        st.experimental_rerun()

    st.stop()
elif st.session_state.gk_mode:
    st.session_state.profiles[st.session_state.selected_profile]["advanced"].extend(st.session_state.gk_answers)
    st.session_state.gk_mode = False
    st.success("🎉 All questions answered and saved.")

# ------------------ ADVANCED VIEW & DELETE ------------------
with st.expander("🔍 View Advanced Q&A"):
    for i, item in enumerate(advanced_qna):
        st.markdown(f"**Q{i+1}:** {item['q']}  
**A:** {item['a']}")
        if st.button(f"🗑️ Delete Q{i+1}", key=f"delete_{i}"):
            del advanced_qna[i]
            st.experimental_rerun()

# ------------------ INTERVIEW SIMULATOR ------------------
st.markdown("---")
st.subheader("💬 Interview Simulator")
question_input = st.text_input("Enter your interview question")

if st.button("Generate Answer") and question_input:
    with st.spinner("Thinking..."):
        answer = generate_interview_answer(current_profile, current_profile)
        st.markdown("---")
        st.subheader("🗣️ Answer:")
        st.write(answer)

        if st.button("📄 Export as PDF"):
            filename = save_to_pdf(question_input, answer)
            st.success(f"Saved as {filename}")
