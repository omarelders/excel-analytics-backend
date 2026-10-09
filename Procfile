web: uvicorn main:app --host=0.0.0.0 --port=${PORT:-5000} --proxy-headers --forwarded-allow-ips=127.0.0.1,::1
release: python run_migrations.py
