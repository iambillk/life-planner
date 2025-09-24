import sqlite3
import sys

# Path to your database
DB_PATH = 'instance/planner.db'  # Adjust if your DB is elsewhere

def add_contact_fields():
    """Add all new contact fields to the database"""
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # List of new fields to add (field_name, field_type)
    new_fields = [
        # Physical Address
        ('street_address', 'VARCHAR(255)'),
        ('address_line_2', 'VARCHAR(255)'),
        ('city', 'VARCHAR(100)'),
        ('state', 'VARCHAR(50)'),
        ('zip_code', 'VARCHAR(20)'),
        ('country', 'VARCHAR(100)'),
        
        # Additional Contact Methods
        ('mobile_phone', 'VARCHAR(64)'),
        ('work_phone', 'VARCHAR(64)'),
        ('home_phone', 'VARCHAR(64)'),
        ('personal_email', 'VARCHAR(255)'),
        ('website', 'VARCHAR(255)'),
        
        # Social/Digital
        ('linkedin_url', 'VARCHAR(255)'),
        ('twitter_url', 'VARCHAR(255)'),
        ('facebook_url', 'VARCHAR(255)'),
        ('instagram_url', 'VARCHAR(255)'),
        ('github_url', 'VARCHAR(255)'),
        
        # Important Dates
        ('birthday', 'DATE'),
        ('anniversary', 'DATE'),
        
        # Personal Details
        ('spouse_name', 'VARCHAR(120)'),
        ('children_names', 'TEXT'),  # TEXT for multiple names
        ('assistant_name', 'VARCHAR(120)'),
        ('business_card_photo', 'VARCHAR(255)'),  # Bonus: adding this too!
    ]
    
    # Add each field
    for field_name, field_type in new_fields:
        try:
            cursor.execute(f"ALTER TABLE contacts ADD COLUMN {field_name} {field_type}")
            print(f"✓ Added field: {field_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"⊘ Field already exists: {field_name}")
            else:
                print(f"✗ Error adding {field_name}: {e}")
    
    # Commit changes
    conn.commit()
    print("\n✅ Database update complete!")
    
    # Show the current structure
    cursor.execute("PRAGMA table_info(contacts)")
    columns = cursor.fetchall()
    print(f"\nContacts table now has {len(columns)} columns")
    
    conn.close()

if __name__ == "__main__":
    print("Adding new contact fields to database...")
    print("-" * 40)
    
    response = input("This will modify your database. Continue? (yes/no): ")
    if response.lower() == 'yes':
        add_contact_fields()
    else:
        print("Cancelled.")