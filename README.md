# Gold Road

This project consists of two separate components:

1.  **Frontend**: A React application located in the `frontend/` directory.
2.  **Backend**: A FastAPI application located in the `backend/` directory.

## Deployment & Repository Split

You can treat `frontend` and `backend` as separate repositories.

To separate them:
1.  Initialize a git repo in `frontend/`:
    ```bash
    cd frontend
    git init
    # Add remote and push
    ```
2.  Initialize a git repo in `backend/`:
    ```bash
    cd backend
    git init
    # Add remote and push
    ```

## Development

- **Frontend**: Run `npm run dev` inside `frontend/`.
- **Backend**: Run `uvicorn main:app --reload` inside `backend/`.
