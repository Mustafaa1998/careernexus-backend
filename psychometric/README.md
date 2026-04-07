# CareerNexus Skeleton Project

This repository provides a **skeleton implementation** of the CareerNexus project.  It contains a FastAPI backend with endpoints for resume analysis, simple tests and recommendations, and a minimal React frontend with pages for each major module.  The goal is to demonstrate the core architecture and give you a starting point for building the complete system described in the project plan.

> ⚠️  **Note:** This code is intentionally simplified.  You are expected to expand upon it by adding authentication, databases, gamification logic, video interviews, learning path flows, better UI design and error handling.

## Directory Structure

```
.
├── backend
│   ├── app.py              # FastAPI application with API endpoints
│   ├── resume_parser.py    # spaCy-based resume parsing utility
│   ├── recommendation.py   # Recommendation engine using TF‑IDF and cosine similarity
│   ├── data
│   │   ├── universities.json  # Sample university dataset
│   │   └── jobs.json          # Sample job dataset
│   ├── requirements.txt    # Python dependencies
│   └── __init__.py
└── frontend
    ├── package.json        # Node dependencies (React, Router, Axios)
    └── src
        ├── index.js
        ├── App.js
        ├── api.js         # Axios instance with API base URL
        └── components
            ├── Navbar.js
            ├── Dashboard.js
            ├── ResumeUpload.js
            ├── Tests.js
            ├── Recommendations.js
            ├── Interview.js
            ├── Gamification.js
            └── LearningPath.js
```

## Prerequisites

* **Python 3.8+** with **pip** installed.
* **Node.js** (v16 or later) and **npm** installed.
* spaCy English model: run `python -m spacy download en_core_web_sm` after installing dependencies.

## Backend Setup

1. Navigate to the `backend` directory:

   ```bash
   cd backend
   ```

2. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

4. Run the backend server using Uvicorn:

   ```bash
   uvicorn backend.app:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`.  You can visit `http://localhost:8000/docs` for interactive API documentation (thanks to FastAPI’s automatic Swagger docs).

## Frontend Setup

The front‑end code is provided as plain React components.  To run it you can create a new React app (e.g., using `create-react-app`) and copy the contents of the `frontend/src` folder into your project.  Here is a quick setup:

1. From the project root, create a new React app (if you don’t already have one):

   ```bash
   npx create-react-app careernexus-client
   cd careernexus-client
   ```

2. Install `axios` and `react-router-dom`:

   ```bash
   npm install axios react-router-dom
   ```

3. Copy the contents of `frontend/src` from this repository into the `src` folder of your new React app, replacing the existing files.  Also copy the `frontend/src/api.js` file.

4. Update `src/api.js` to set the correct base URL for your backend (e.g., `http://localhost:8000`).

5. Start the React development server:

   ```bash
   npm start
   ```

   The app will open at `http://localhost:3000` and you can navigate through the pages using the navbar.

## Extending the Project

This skeleton demonstrates how to:

* Upload and parse a resume with spaCy, returning structured data.
* Score simple aptitude and personality tests.
* Match user skills to sample universities and jobs using TF‑IDF and cosine similarity.

To build the full CareerNexus platform described in the FYP proposal, consider adding:

* **Authentication:** Secure routes with user sign‑up and login using Firebase Authentication or your own JWT solution.
* **Database:** Persist user profiles, test results and XP to Firestore/Supabase/PostgreSQL.
* **Gamification logic:** Implement XP, badges and leaderboards on the backend and surface in the frontend.
* **Interview module:** Integrate WebRTC for live interviews and speech‑to‑text for feedback.
* **Learning paths:** Use `react-flow` to build interactive flowcharts of recommended courses.
* **Admin portal:** Add routes and components for managing questions, programs, jobs and users.

Refer to the **complete_solution.md** document for a detailed project plan and design considerations.