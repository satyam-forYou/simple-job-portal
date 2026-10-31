import os
import re
import uuid
import tempfile
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "college-project-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "job_portal.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads", "resumes")
app.config["APPLICATION_DETAILS_FOLDER"] = os.path.join(BASE_DIR, "uploads", "application_details")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["ALLOWED_EXTENSIONS"] = {"pdf", "docx"}

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["APPLICATION_DETAILS_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")
    phone = db.Column(db.String(20))
    location = db.Column(db.String(120))
    skills = db.Column(db.Text)
    education = db.Column(db.Text)
    experience = db.Column(db.Text)
    bio = db.Column(db.Text)
    resume_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    jobs_posted = db.relationship("Job", backref="poster", cascade="all, delete-orphan")
    applications = db.relationship("Application", backref="applicant", cascade="all, delete-orphan")

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(120))
    job_type = db.Column(db.String(50), default="Full-time")
    category = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text)
    min_experience = db.Column(db.Integer, default=0)
    salary_range = db.Column(db.String(100))
    posted_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    applications = db.relationship("Application", backref="job", cascade="all, delete-orphan")

    def skills(self):
        return [s.strip() for s in (self.required_skills or "").split(",") if s.strip()]

    def required_skills_list(self):
        return self.skills()

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resume_filename = db.Column(db.String(255))
    cover_note = db.Column(db.Text)
    status = db.Column(db.String(30), default="Applied")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("job_id", "user_id", name="one_application_per_student"),)

class ATSAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    score = db.Column(db.Integer, nullable=False)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="ats_analyses")
    job = db.relationship("Job")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def clean(value, limit=500):
    return (value or "").strip()[:limit]

def safe_filename(value, fallback="file"):
    """Make a readable and safe filename."""
    value = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
    return value[:80] or fallback


def save_resume(file, user_name, job_title="Profile"):
    """Save a resume using the applicant name and job title."""
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    name_part = safe_filename(user_name, "Applicant")
    job_part = safe_filename(job_title, "Resume")
    time_part = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{name_part}_{job_part}_Resume_{time_part}_{uuid.uuid4().hex[:6]}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename


def save_application_details(application, name, email, phone, location,
                              education, skills, experience, bio, cover_note):
    """Save a readable copy of application details as a text file."""
    os.makedirs(app.config["APPLICATION_DETAILS_FOLDER"], exist_ok=True)

    applicant_part = safe_filename(name, "Applicant")
    job_part = safe_filename(application.job.title, "Job")
    time_part = application.applied_at.strftime("%Y%m%d_%H%M%S")
    filename = f"{applicant_part}_{job_part}_Application_{time_part}_{application.id}.txt"

    details = f"""SMART JOB PORTAL - APPLICATION DETAILS

Application ID: {application.id}
Job Title: {application.job.title}
Company: {application.job.company}
Applied On: {application.applied_at.strftime("%d %B %Y, %I:%M %p")}
Status: {application.status}

APPLICANT DETAILS
Name: {name}
Email: {email}
Phone: {phone}
Location: {location}

EDUCATION
{education}

SKILLS
{skills}

EXPERIENCE
{experience or "Not provided"}

PROFESSIONAL PROFILE / BIO
{bio or "Not provided"}

COVER NOTE
{cover_note or "Not provided"}

RESUME FILE
{application.resume_filename}
"""

    path = os.path.join(app.config["APPLICATION_DETAILS_FOLDER"], filename)
    with open(path, "w", encoding="utf-8") as file:
        file.write(details)

    return filename

def valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value or ""))

def valid_name(value):
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,119}", value or ""))

def valid_phone(value):
    digits = re.sub(r"[\s+()-]", "", value or "")
    return digits.isdigit() and 10 <= len(digits) <= 15

def valid_years(value):
    try:
        return 0 <= int(value) <= 60
    except (TypeError, ValueError):
        return False

def admin_required(view):
    @wraps(view)
    def check_admin(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return check_admin

def job_form_data():
    mode = request.form.get("location_mode", "onsite")
    data = {
        "title": clean(request.form.get("title"), 200),
        "company": clean(request.form.get("company"), 150),
        "location": "Remote" if mode == "remote" else clean(request.form.get("location"), 120),
        "job_type": request.form.get("job_type", "Full-time"),
        "category": clean(request.form.get("category"), 100),
        "description": clean(request.form.get("description"), 3000),
        "required_skills": clean(request.form.get("required_skills"), 500),
        "min_experience": request.form.get("min_experience") or "0",
        "salary_range": clean(request.form.get("salary_range"), 100),
    }
    if not all([data["title"], data["company"], data["category"], data["description"], data["required_skills"]]):
        return None, "Please fill all required job details."
    if mode != "remote" and not data["location"]:
        return None, "Please enter a job location or select Remote."
    if data["job_type"] not in ["Full-time", "Part-time", "Internship", "Contract"]:
        return None, "Please select a valid job type."
    if not valid_years(data["min_experience"]):
        return None, "Minimum experience must be a number from 0 to 60."
    data["min_experience"] = int(data["min_experience"])
    return data, None

@app.route("/")
def index():
    jobs = Job.query.filter_by(is_active=True).order_by(Job.posted_at.desc()).all()
    return render_template("index.html", recent_jobs=jobs[:6], job_count=len(jobs))

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        role = request.form.get("role", "student")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        skills = request.form.get("skills", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        bio = request.form.get("bio", "").strip()

        if role not in ["student", "admin"]:
            role = "student"
        if not valid_name(name):
            flash("Please enter a valid full name.", "danger")
            return render_template("auth/register.html")
        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/register.html")
        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return render_template("auth/register.html")
        if password != confirm_password:
            flash("Password and confirm password do not match.", "danger")
            return render_template("auth/register.html")
        if not valid_phone(phone):
            flash("Please enter a valid 10-15 digit phone number.", "danger")
            return render_template("auth/register.html")
        if not location:
            flash("Please enter your location.", "danger")
            return render_template("auth/register.html")
        if not skills:
            flash("Please enter your skills.", "danger")
            return render_template("auth/register.html")
        if not education:
            flash("Please enter your education details.", "danger")
            return render_template("auth/register.html")
        if not experience:
            flash("Please enter your experience details.", "danger")
            return render_template("auth/register.html")
        if not bio:
            flash("Please enter your professional profile / bio.", "danger")
            return render_template("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("auth/register.html")

        user = User(name=name, email=email, role=role, phone=phone, location=location,
                    skills=skills, education=education, experience=experience, bio=bio)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        role_name = "Recruiter" if role == "admin" else "Student"
        flash(f"{role_name} account created. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("auth/register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if current_user.is_admin:
        return render_template("profile/view.html", user=current_user)

    if request.method == "POST":
        name = clean(request.form.get("name"), 120)
        phone = clean(request.form.get("phone"), 20)
        location = clean(request.form.get("location"), 120)
        skills = clean(request.form.get("skills"), 500)
        education = clean(request.form.get("education"), 500)
        experience = clean(request.form.get("experience"), 500)
        bio = clean(request.form.get("bio"), 1000)
        if not valid_name(name):
            flash("Please enter a valid full name.", "danger")
            return redirect(url_for("profile"))
        if phone and not valid_phone(phone):
            flash("Please enter a valid phone number.", "danger")
            return redirect(url_for("profile"))

        file = request.files.get("resume")
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Only PDF and DOCX files are allowed.", "danger")
                return redirect(url_for("profile"))
            current_user.resume_filename = save_resume(file, current_user.name, "Profile")

        current_user.name = name
        current_user.phone = phone
        current_user.location = location
        current_user.skills = skills
        current_user.education = education
        current_user.experience = experience
        current_user.bio = bio
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile/view.html", user=current_user)

@app.route("/resume/<filename>")
@login_required
def download_resume(filename):
    allowed = current_user.resume_filename == filename
    if current_user.is_admin:
        allowed = Application.query.filter_by(resume_filename=filename).join(Job).filter(
            Job.posted_by == current_user.id
        ).first() is not None
    if not allowed:
        abort(403)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/application/<int:app_id>/details")
@login_required
def download_application_details(app_id):
    application = db.get_or_404(Application, app_id)

    allowed = application.user_id == current_user.id
    if current_user.is_admin:
        allowed = application.job.posted_by == current_user.id

    if not allowed:
        abort(403)

    applicant_name = safe_filename(application.applicant.name, "Applicant")
    job_name = safe_filename(application.job.title, "Job")
    time_part = application.applied_at.strftime("%Y%m%d_%H%M%S")
    filename = f"{applicant_name}_{job_name}_Application_{time_part}_{application.id}.txt"
    path = os.path.join(app.config["APPLICATION_DETAILS_FOLDER"], filename)

    if not os.path.isfile(path):
        save_application_details(
            application,
            application.applicant.name,
            application.applicant.email,
            application.applicant.phone or "",
            application.applicant.location or "",
            application.applicant.education or "",
            application.applicant.skills or "",
            application.applicant.experience or "",
            application.applicant.bio or "",
            application.cover_note or ""
        )

    return send_from_directory(
        app.config["APPLICATION_DETAILS_FOLDER"],
        filename,
        as_attachment=True
    )


@app.route("/jobs")
def list_jobs():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    job_type = request.args.get("job_type", "").strip()
    query = Job.query.filter_by(is_active=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Job.title.ilike(like), Job.company.ilike(like),
                                    Job.required_skills.ilike(like)))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter_by(job_type=job_type)
    jobs = query.order_by(Job.posted_at.desc()).all()
    applied = set()
    if current_user.is_authenticated and not current_user.is_admin:
        applied = {a.job_id for a in Application.query.filter_by(user_id=current_user.id)}
    return render_template("jobs/list.html", jobs=jobs, query=q, location=location,
                           job_type=job_type, applied_job_ids=applied)

@app.route("/jobs/<int:job_id>")
def view_job(job_id):
    job = db.get_or_404(Job, job_id)
    already_applied = False
    if current_user.is_authenticated and not current_user.is_admin:
        already_applied = Application.query.filter_by(job_id=job.id, user_id=current_user.id).first() is not None
    return render_template("jobs/view.html", job=job, already_applied=already_applied)

@app.route("/jobs/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_job():
    if request.method == "POST":
        data, error = job_form_data()
        if error:
            flash(error, "danger")
            return render_template("jobs/form.html", job=None)
        db.session.add(Job(**data, posted_by=current_user.id))
        db.session.commit()
        flash("Job posted successfully.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("jobs/form.html", job=None)

@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_job(job_id):
    job = db.get_or_404(Job, job_id)
    if job.posted_by != current_user.id:
        abort(403)
    if request.method == "POST":
        data, error = job_form_data()
        if error:
            flash(error, "danger")
            return render_template("jobs/form.html", job=job)
        for key, value in data.items():
            setattr(job, key, value)
        job.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Job updated.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("jobs/form.html", job=job)

@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_job(job_id):
    job = db.get_or_404(Job, job_id)
    if job.posted_by != current_user.id:
        abort(403)
    db.session.delete(job)
    db.session.commit()
    flash("Job deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
@login_required
def apply_job(job_id):
    if current_user.is_admin:
        abort(403)

    job = db.get_or_404(Job, job_id)
    existing = Application.query.filter_by(job_id=job.id, user_id=current_user.id).first()
    if existing:
        flash("You already applied for this job.", "warning")
        return redirect(url_for("my_applications"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        education = request.form.get("education", "").strip()
        skills = request.form.get("skills", "").strip()
        cover_note = request.form.get("cover_note", "").strip()
        resume = request.files.get("resume")

        if not valid_name(name):
            flash("Please enter a valid full name.", "danger")
            return render_template("applications/apply.html", job=job)
        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("applications/apply.html", job=job)
        other_user = User.query.filter(User.email == email, User.id != current_user.id).first()
        if other_user:
            flash("This email is already used by another account.", "danger")
            return render_template("applications/apply.html", job=job)
        if not valid_phone(phone):
            flash("Please enter a valid phone number.", "danger")
            return render_template("applications/apply.html", job=job)
        if len(education) < 2 or len(education) > 500:
            flash("Please enter valid education details.", "danger")
            return render_template("applications/apply.html", job=job)
        if location and len(location) > 120:
            flash("Location is too long.", "danger")
            return render_template("applications/apply.html", job=job)
        if len(skills) > 500 or len(cover_note) > 1500:
            flash("Please keep skills and cover note within the allowed length.", "danger")
            return render_template("applications/apply.html", job=job)
        if not resume or not resume.filename:
            flash("Please upload your resume before submitting the application.", "danger")
            return render_template("applications/apply.html", job=job)
        if not allowed_file(resume.filename):
            flash("Only PDF and DOCX resume files are allowed.", "danger")
            return render_template("applications/apply.html", job=job)

        filename = save_resume(resume, name, job.title)

        current_user.name = name
        current_user.email = email
        current_user.phone = phone
        current_user.location = location
        current_user.education = education
        current_user.skills = skills
        current_user.resume_filename = filename

        application = Application(
            job_id=job.id,
            user_id=current_user.id,
            resume_filename=filename,
            cover_note=cover_note
        )
        db.session.add(application)
        db.session.commit()

        details_filename = save_application_details(
            application, name, email, phone, location,
            education, skills,
            current_user.experience or "",
            current_user.bio or "",
            cover_note
        )

        flash(
            f"Application submitted successfully. Resume saved as {filename}. "
            f"Application details saved as {details_filename}.",
            "success"
        )
        return redirect(url_for("my_applications"))

    return render_template("applications/apply.html", job=job)

@app.route("/my-applications")
@login_required
def my_applications():
    if current_user.is_admin:
        return redirect(url_for("admin_dashboard"))
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    return render_template("applications/mine.html", applications=applications)

@app.route("/jobs/<int:job_id>/applicants")
@login_required
@admin_required
def job_applicants(job_id):
    job = db.get_or_404(Job, job_id)
    if job.posted_by != current_user.id:
        abort(403)
    applications = Application.query.filter_by(job_id=job.id).order_by(Application.applied_at.desc()).all()
    return render_template("applications/job_applicants.html", job=job, applications=applications)

@app.route("/applications/<int:app_id>/status", methods=["POST"])
@login_required
@admin_required
def update_status(app_id):
    application = db.get_or_404(Application, app_id)
    if application.job.posted_by != current_user.id:
        abort(403)
    status = request.form.get("status")
    if status in ["Applied", "Under Review", "Shortlisted", "Rejected", "Hired"]:
        application.status = status
        db.session.commit()
    return redirect(url_for("job_applicants", job_id=application.job_id))

COMMON_SKILLS = [
    "python", "java", "javascript", "c++", "c#", "sql", "html", "css", "react",
    "flask", "django", "spring boot", "node.js", "bootstrap", "mongodb", "mysql",
    "git", "github", "docker", "aws", "linux", "machine learning", "data structures",
    "algorithms", "pandas", "numpy", "tensorflow", "excel", "power bi", "tableau",
    "communication", "leadership", "problem solving", "teamwork"
]

def extract_resume_text(path):
    try:
        if path.lower().endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        import docx
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    except Exception:
        return ""

def analyze_resume(text, job=None):
    text = text.lower()
    skills = job.skills() if job and job.skills() else COMMON_SKILLS
    matched = [s for s in skills if re.search(r"\b" + re.escape(s.lower()) + r"\b", text)]
    missing = [s for s in skills if s not in matched]
    score = int(len(matched) / max(len(skills), 1) * 100)
    suggestions = []
    if len(text.split()) < 150:
        suggestions.append("Add more details about projects, education and achievements.")
    if "project" not in text:
        suggestions.append("Add a Projects section with your practical work.")
    if missing:
        suggestions.append("Add relevant missing skills only if you actually have them.")
    if not suggestions:
        suggestions.append("Good coverage. Add measurable results to make achievements stronger.")
    return {"ats_score": max(5, min(score, 100)), "matched_skills": matched,
            "missing_skills": missing[:10], "suggestions": suggestions}

@app.route("/ats-score", methods=["GET", "POST"])
@login_required
def ats_score():
    if current_user.is_admin:
        abort(403)
    if request.method == "POST":
        file = request.files.get("resume")
        temp_path = None

        try:
            # A newly selected resume is processed in the system temporary folder.
            # It is NOT permanently copied into the project uploads folder.
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Only PDF and DOCX files are allowed.", "danger")
                    return redirect(url_for("ats_score"))

                ext = file.filename.rsplit(".", 1)[1].lower()
                temp_file = tempfile.NamedTemporaryFile(
                    prefix="jobportal_ats_", suffix=f".{ext}", delete=False
                )
                temp_path = temp_file.name
                temp_file.close()
                file.save(temp_path)
                path = temp_path

            elif current_user.resume_filename:
                path = os.path.join(app.config["UPLOAD_FOLDER"], current_user.resume_filename)
                if not os.path.isfile(path):
                    flash("Your saved resume is missing. Please upload it again.", "warning")
                    return redirect(url_for("ats_score"))
            else:
                flash("Please upload a resume first.", "warning")
                return redirect(url_for("ats_score"))

            job_id = request.form.get("job_id")
            job = db.session.get(Job, int(job_id)) if job_id and job_id.isdigit() else None
            result = analyze_resume(extract_resume_text(path), job)

            if not result["matched_skills"] and not result["missing_skills"]:
                flash("Could not read the resume. Use a text-based PDF or DOCX.", "danger")
                return redirect(url_for("ats_score"))

            analysis = ATSAnalysis(
                user_id=current_user.id,
                job_id=job.id if job else None,
                score=result["ats_score"]
            )
            db.session.add(analysis)
            db.session.commit()
            return render_template("resume_ai/result.html", result=result, job=job, analysis=analysis)

        except (OSError, ValueError) as error:
            db.session.rollback()
            app.logger.exception("ATS resume processing failed: %s", error)
            flash("Could not process the resume. Please try uploading it again.", "danger")
            return redirect(url_for("ats_score"))

        finally:
            # Newly uploaded ATS files are always temporary and are deleted after analysis.
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    app.logger.warning("Could not delete temporary ATS file: %s", temp_path)

    jobs = Job.query.filter_by(is_active=True).order_by(Job.posted_at.desc()).all()
    return render_template("resume_ai/ats_score.html", jobs=jobs)

@app.route("/dashboard")
@login_required
def dashboard():
    return admin_dashboard() if current_user.is_admin else student_dashboard()

def student_dashboard():
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    jobs = Job.query.filter_by(is_active=True).order_by(Job.posted_at.desc()).all()
    counts = {}
    for app_item in applications:
        counts[app_item.status] = counts.get(app_item.status, 0) + 1
    latest_analysis = ATSAnalysis.query.filter_by(user_id=current_user.id).order_by(ATSAnalysis.analyzed_at.desc()).first()
    profile_fields = [current_user.name, current_user.email, current_user.phone, current_user.location,
                      current_user.skills, current_user.education, current_user.resume_filename]
    profile_complete = round(sum(bool(value) for value in profile_fields) / len(profile_fields) * 100)
    return render_template("dashboard/student.html", applications=applications,
                           recent_jobs=jobs[:5], status_counts=counts, latest_analysis=latest_analysis,
                           available_jobs=len(jobs), profile_complete=profile_complete)

@app.route("/dashboard/admin")
@login_required
@admin_required
def admin_dashboard():
    jobs = Job.query.filter_by(posted_by=current_user.id).order_by(Job.posted_at.desc()).all()
    job_ids = [job.id for job in jobs]
    applications = Application.query.filter(Application.job_id.in_(job_ids)).order_by(
        Application.applied_at.desc()).all() if job_ids else []
    status_counts = {}
    for item in applications:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
    jobs_with_applicants = sum(1 for job in jobs if job.applications)
    return render_template("dashboard/admin.html", jobs=jobs, applications=applications,
                           total_jobs=len(jobs), active_jobs=sum(j.is_active for j in jobs),
                           total_applications=len(applications),
                           jobs_with_applicants=jobs_with_applicants,
                           status_counts=status_counts)

@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404

with app.app_context():
    db.create_all()
    if not ATSAnalysis.query.first():
        demo_student = User.query.filter_by(role="student").order_by(User.id).first()
        demo_job = Job.query.filter_by(is_active=True).order_by(Job.id).first()
        if demo_student:
            db.session.add(ATSAnalysis(user_id=demo_student.id,
                                       job_id=demo_job.id if demo_job else None,
                                       score=78))
            db.session.commit()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
