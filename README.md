# Smart Job Portal - Mini Project

A simple Flask project for students and recruiters. It uses SQLite and is designed to be easy to understand and explain in a viva.

## Main Modules
1. Student registration and login
2. Recruiter registration and read-only recruiter profile
3. Student profile and resume upload
4. Job search and job posting
5. Job application with details + resume upload
6. Recruiter dashboard and applicant management
7. One simple ATS Resume Analyzer

## Technology
- Python + Flask
- HTML, CSS, Bootstrap and JavaScript
- SQLite
- pypdf for PDF text
- python-docx for DOCX text

## Database
The SQLite database is already included here:

`instance/job_portal.db`

It contains 3 recruiters, 8 demo students, 20 jobs and 24 applications.
The application only runs `db.create_all()` at startup; demo-data creation code is not kept in `app.py` to make the project shorter and easier to explain.

## Demo Recruiter Accounts
All three use password `admin123`.

| Recruiter | Email | Password |
|---|---|---|
| Neha Kulkarni | admin@jobportal.com | admin123 |
| Rohit Singh | admin2@jobportal.com | admin123 |
| Pooja Nair | admin3@jobportal.com | admin123 |

Recruiters can also sign up from the Sign Up page. Recruiter profiles are read-only after creation.

## Demo Student Accounts
Password for all demo students: `demo1234`.

- rahul@example.com
- priya@example.com
- amit@example.com
- sneha@example.com
- karan@example.com
- ananya@example.com
- vikram@example.com
- meera@example.com

## Important Features
- Multiple students can apply to the same job.
- A student cannot apply twice to the same job.
- Apply flow: **Apply Now -> Fill Details -> Upload Resume -> Submit**.
- Recruiters see only their own jobs and applicants.
- Job location supports **Remote** or a normal location.
- Server-side validation checks submitted data.
- ATS analysis uses a temporary upload and removes it after analysis, so it does not create an extra permanent resume.

## Run
On Windows, if `python` is not recognized, use the Python Launcher (`py`) or install Python and add it to PATH.

```powershell
py -m venv venv
venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

Open `http://127.0.0.1:5000`.

## Project Structure

```text
simple_job_portal/
├── app.py
├── requirements.txt
├── README.md
├── instance/
│   └── job_portal.db
├── static/
│   ├── css/
│   └── js/
├── templates/
└── uploads/
    └── resumes/
```

## Code Size
The main Python file is about **600 lines**. The project deliberately avoids unnecessary APIs and complex frameworks so the code is easier to read and explain.


## Changes made
1. Sign Up now requires all profile details for both Student and Recruiter accounts.
2. Added Confirm Password validation.
3. Resume filenames are saved using applicant name, job title and application time.
4. Application details are saved as a readable TXT file with a proper applicant/job name.
5. Recruiters and applicants can download the application details file.
6. Resumes and application-details files are kept in separate folders under `uploads/`.
