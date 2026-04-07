# CareerNexus Backend

Backend repository for the CareerNexus platform. This project integrates multiple intelligent modules designed to assist users in career guidance, skill analysis, and decision-making.

---

## Overview

CareerNexus is an AI-powered platform that combines various modules such as chatbot assistance, career recommendations, psychometric analysis, and resume parsing to provide personalised career insights.

---

## Modules

- **Chatbot Module**  
  Provides AI-based career guidance and answers user queries.

- **Recommendation System**  
  Suggests suitable careers, jobs, and universities based on user skills.

- **Psychometric Analysis**  
  Evaluates personality traits and aptitude through structured tests.

- **Resume Parser**  
  Extracts and analyses information from user resumes using NLP techniques.

---

## Tech Stack

- Python
- FastAPI
- Natural Language Processing (NLP)
- Machine Learning
- REST APIs

---

## Project Structure

```text
CareerNexus_Chatbot/
CareerNexus_Recommendation/
ResumeParser/
psychometric/
```

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/Mustafaa1998/careernexus-backend.git
```

### 2. Navigate to the project folder
```bash
cd careernexus-backend
```

### 3. Create a virtual environment (recommended)
```bash
python -m venv venv
```

### 4. Activate the virtual environment
- Windows:
  ```bash
  venv\Scripts\activate
  ```
  
- Mac/Linux:
  ```bash
  source venv/bin/activate
  ```
  
### 5. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Backend
```bash
uvicorn app:app --reload
```

Then open:
```md
🔗 http://localhost:8000/docs
```

---

## Future Improvements
- Authentication system (JWT / Firebase)
- Database integration (PostgreSQL / MongoDB)
- Gamification (XP, badges, leaderboards)
- Interview module (WebRTC + speech analysis)
- Admin dashboard
- Full frontend integration

---

## Author
**Muhammad Mustafa**  
📧 mustafasaleem1998@gmail.com  
🔗 https://www.linkedin.com/in/muhammad-mustafa-169282188/

