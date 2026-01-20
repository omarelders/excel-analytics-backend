from dotenv import load_dotenv
import os

print(f"Current Working Directory: {os.getcwd()}")
print("Files in current directory:")
for f in os.listdir():
    if f.startswith(".env"):
        print(f" - {f}")

print("\nAttempting to load .env...")
loaded = load_dotenv(verbose=True)
print(f"load_dotenv returned: {loaded}")

db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL value: '{db_url}'")

if db_url is None:
    print("❌ DATABASE_URL is None")
else:
    print("✅ DATABASE_URL found")
