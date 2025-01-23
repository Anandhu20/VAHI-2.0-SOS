from app import app, db

# Create tables for the database
with app.app_context():
    db.create_all()
    print("Database and tables created successfully!")
