import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.seed import seed

if __name__ == "__main__":
    seed()
    print("Seed complete")
