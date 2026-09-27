import os

TEAM_NAME = os.getenv("TEAM_NAME", "Team Alpha")
TEAM_MEMBERS = os.getenv("TEAM_MEMBERS", "Alice, Bob").split(",")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
APPROACH = os.getenv("APPROACH", "Phase 1 Skeleton")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "team@example.com")
VERSION = os.getenv("VERSION", "0.1.0")
