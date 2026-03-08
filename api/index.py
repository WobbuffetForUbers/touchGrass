import os
# Ensure we're using a writable temp directory for the database on Vercel
os.environ["DATABASE_URL"] = "sqlite:////tmp/touchgrass.db"

from main import app
