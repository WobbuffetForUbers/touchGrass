import os
# Ensure we're using a writable temp directory for the database on Vercel
os.environ["DATABASE_URL"] = "sqlite:////tmp/touchgrass.db"

# Now that main.py is in the same folder, this import is more reliable
from .main import app
