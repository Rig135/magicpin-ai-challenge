import os
from dotenv import load_dotenv

load_dotenv()

TEAM_NAME = os.getenv("TEAM_NAME", "Team Alpha")
TEAM_MEMBERS = os.getenv("TEAM_MEMBERS", "Alice, Bob").split(",")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APPROACH = os.getenv("APPROACH", "Vera Engagement Engine")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "team@example.com")
VERSION = os.getenv("VERSION", "0.2.0")

