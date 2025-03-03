# Knowledge Management tool for consultants

This project implements a Retrieval-Augmented Generation (RAG) system using Python and React. It processes documents, creates embeddings, and provides a Q&A interface powered by OpenAI and Supabase.

## Prerequisites

- Python 3.8+
- Node.js 16+
- OpenAI API account
- Supabase account

## Environment Setup

1. Create and activate a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables by creating a `.env` file in the project root:
```plaintext
LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_key
```

## Backend server

Open a new terminal where venv is activated and start the server
```bash
python3 -m main
```