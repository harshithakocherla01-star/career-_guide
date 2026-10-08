# TechTide AI Skill Gap & Career Roadmap Platform

A full-stack, production-grade web application built according to the **TechTide Hackday 1.0 System Architecture Document** (Domain: EdTech / Career Development).

---

## 🚀 Key Architectural Highlights

1. **Explainable & Interpretable**:
   - Every Career Readiness Score is calculated with the exact formula:
     $$\text{score} = 100 \times \frac{\sum (\text{weight}_i \times \min(\text{user\_level}_i / \text{required\_level}_i, 1))}{\sum \text{weight}_i}$$
   - Point losses explain exact deficiencies (e.g. *"Missing Docker (weight 0.8) costs 9.2 pts"*).

2. **Missing-Skill Prioritization (DAG Topological Sort)**:
   - Priority metric:
     $$\text{priority} = \text{weight} \times \frac{\text{required\_level} - \text{user\_level}}{\text{effort\_weeks}}$$
   - Prerequisite dependency graph ensures foundational skills come first (e.g. Python $\rightarrow$ Pandas $\rightarrow$ Machine Learning; Linux $\rightarrow$ Docker $\rightarrow$ Kubernetes).

3. **Grounded & Verifiable Roadmaps (Agentic Loop)**:
   - Roadmaps are built only from a curated resource and practical project database (no hallucinated links).
   - Pacemaker validates against the user's weekly available hours budget.

4. **100% Resilient Hybrid AI**:
   - Supports Claude / Gemini API keys when available.
   - Includes a deterministic rule-based NLP extractor and template planner that works offline out of the box with zero external API dependencies.

5. **Role & Career Path Recommendation**:
   - NumPy cosine similarity on skill vectors ranks alternate career paths and suggests the top 2–3 unlocking skills.

6. **Interactive Features**:
   - Resume drag-and-drop parser with ATS compliance score and feedback.
   - Chart.js Radar, Line, Bar, and SVG circular progress rings.
   - Milestone checkbox completion that levels up candidate skills and updates readiness live.
   - Role- & gap-specific Technical Mock Interview simulator with 1–5 rubric evaluation.
   - Downloadable multi-page career readiness & roadmap PDF generated via ReportLab.
   - Extensible Admin Panel with cohort analytics on macro skill gaps.

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JS, Chart.js, FontAwesome | Responsive UI, Radar, Bar, Line charts, Progress rings |
| **Backend** | Python 3.12, Flask (App Factory & Blueprints) | REST API, Business logic, Auth |
| **AI / NLP** | Anthropic Claude / Gemini API + Resilient Rule Engine | Skill extraction, Roadmap loop, Mock interview grading |
| **Parsing** | `pypdf`, `python-docx` | Clean text extraction from PDF and Word documents |
| **Recommendation**| NumPy Cosine Similarity | Skill vector matching across roles |
| **Database** | SQLite / SQLAlchemy ORM | Relational models for users, skills, roles, roadmaps |
| **Reporting** | ReportLab | Downloadable multi-page career roadmap PDF |
| **Security** | PyJWT, Werkzeug password hashing | Role-based access control (`user` vs `admin`) |

---

## 🏁 Quick Start & Running the Platform

1. Navigate to the project directory:
   ```powershell
   cd d:\24BQ1A05L3\career-platform
   ```

2. Start the application:
   ```powershell
   python run.py
   ```

3. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

## 👥 Demo Accounts

The database comes pre-seeded with rich roles, canonical skills, resources, projects, and test accounts:

| Role | Email | Password | Details |
|---|---|---|---|
| **Candidate** | `alex@techtide.io` | `alex123` | Preloaded with skills (JS, HTML/CSS, Git, SQL, Python), target role: Full Stack Web Developer |
| **Admin** | `admin@techtide.io` | `admin123` | Access to Admin console, cohort analytics, taxonomy CRUD |

*You can also register a brand new account or click the 1-click test buttons on the login page.*

---

## 🧪 Running Automated Tests

Run the unit and end-to-end integration test suites:
```powershell
python -m unittest tests/test_engines.py
python -m unittest tests/test_api.py
```
*(All 12 tests execute in under 7 seconds with 100% pass rate).*
