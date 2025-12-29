# Backend API

This is the FastAPI backend for Gold Road.

## Setup

1.  **Create a virtual environment**:
    ```bash
    python -m venv venv
    ```

2.  **Activate the virtual environment**:
    - Windows:
      ```bash
      venv\Scripts\activate
      ```
    - macOS/Linux:
      ```bash
      source venv/bin/activate
      ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Server

Start the development server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
