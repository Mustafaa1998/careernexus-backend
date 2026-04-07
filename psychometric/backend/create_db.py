from .db import engine, Base
from . import models  # registers models

def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created.")

if __name__ == "__main__":
    main()
