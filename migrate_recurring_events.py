# Save this as migrate_recurring_events.py and run it once to update your database
# Run with: python migrate_recurring_events.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.base import db
from sqlalchemy import text

def migrate_recurring_events():
    """Add new columns to recurring_events table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add new columns if they don't exist
            migrations = [
                "ALTER TABLE recurring_events ADD COLUMN recurrence_type VARCHAR(20) DEFAULT 'weekly';",
                "ALTER TABLE recurring_events ADD COLUMN daily_interval INTEGER DEFAULT 1;",
                "ALTER TABLE recurring_events ADD COLUMN weekly_interval INTEGER DEFAULT 1;",
                "ALTER TABLE recurring_events ADD COLUMN monthly_date INTEGER;",
                "ALTER TABLE recurring_events ADD COLUMN monthly_interval INTEGER DEFAULT 1;",
                "ALTER TABLE recurring_events ADD COLUMN monthly_week INTEGER;",
                "ALTER TABLE recurring_events ADD COLUMN monthly_weekday INTEGER;",
                "ALTER TABLE recurring_events ADD COLUMN yearly_month INTEGER;",
                "ALTER TABLE recurring_events ADD COLUMN yearly_day INTEGER;",
                "ALTER TABLE recurring_events ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
            ]
            
            for migration in migrations:
                try:
                    db.session.execute(text(migration))
                    print(f"✓ Executed: {migration[:50]}...")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        print(f"✓ Column already exists: {migration[:50]}...")
                    else:
                        print(f"✗ Error: {migration[:50]}... - {str(e)}")
            
            # Update existing records to have recurrence_type = 'weekly'
            try:
                db.session.execute(text(
                    "UPDATE recurring_events SET recurrence_type = 'weekly' WHERE recurrence_type IS NULL;"
                ))
                print("✓ Updated existing records to have recurrence_type = 'weekly'")
            except Exception as e:
                print(f"✗ Could not update existing records: {str(e)}")
            
            db.session.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    migrate_recurring_events()