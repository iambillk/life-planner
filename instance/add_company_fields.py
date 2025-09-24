#!/usr/bin/env python3
"""
Script to add new fields to the companies table in planner.db
Run this once to update your database schema.
"""

import sqlite3
import os
import sys

# Database path - adjust if your planner.db is in a different location
DB_PATH = 'planner.db'

def add_company_fields():
    """Add new fields to the companies table"""
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"Error: Database '{DB_PATH}' not found!")
        print("Make sure you're running this script from the correct directory.")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if companies table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
        if not cursor.fetchone():
            print("Error: companies table doesn't exist!")
            return False
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(companies)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Define new columns to add
        new_columns = [
            ('logo', 'VARCHAR(255)'),
            ('industry', 'VARCHAR(100)'),
            ('size', 'VARCHAR(50)'),
            ('address', 'VARCHAR(255)'),
            ('linkedin', 'VARCHAR(255)'),
            ('twitter', 'VARCHAR(255)')
        ]
        
        # Add each column if it doesn't exist
        columns_added = []
        columns_skipped = []
        
        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                try:
                    alter_query = f"ALTER TABLE companies ADD COLUMN {column_name} {column_type}"
                    cursor.execute(alter_query)
                    columns_added.append(column_name)
                    print(f"✓ Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"✗ Error adding column {column_name}: {e}")
            else:
                columns_skipped.append(column_name)
                print(f"→ Column already exists: {column_name}")
        
        # Commit changes
        conn.commit()
        
        # Print summary
        print("\n" + "="*50)
        print("MIGRATION SUMMARY")
        print("="*50)
        if columns_added:
            print(f"✓ Successfully added {len(columns_added)} columns: {', '.join(columns_added)}")
        if columns_skipped:
            print(f"→ Skipped {len(columns_skipped)} existing columns: {', '.join(columns_skipped)}")
        
        # Show current table structure
        print("\n" + "="*50)
        print("CURRENT COMPANIES TABLE STRUCTURE")
        print("="*50)
        cursor.execute("PRAGMA table_info(companies)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"{col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else 'NULL':8} {f'DEFAULT {col[4]}' if col[4] else ''}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def create_logo_directory():
    """Create the company_logos directory if it doesn't exist"""
    logo_dir = os.path.join('static', 'company_logos')
    if not os.path.exists(logo_dir):
        os.makedirs(logo_dir)
        print(f"\n✓ Created directory: {logo_dir}")
    else:
        print(f"\n→ Directory already exists: {logo_dir}")

def backup_database():
    """Create a backup of the database before migration"""
    import shutil
    from datetime import datetime
    
    if os.path.exists(DB_PATH):
        backup_name = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(DB_PATH, backup_name)
        print(f"✓ Created backup: {backup_name}")
        return backup_name
    return None

def main():
    print("="*50)
    print("COMPANIES TABLE MIGRATION SCRIPT")
    print("="*50)
    print(f"Database: {DB_PATH}\n")
    
    # Create backup
    print("Creating backup...")
    backup_file = backup_database()
    
    # Run migration
    print("\nRunning migration...")
    success = add_company_fields()
    
    # Create logo directory
    create_logo_directory()
    
    if success:
        print("\n✅ Migration completed successfully!")
        if backup_file:
            print(f"Note: Backup saved as {backup_file}")
    else:
        print("\n❌ Migration failed!")
        if backup_file:
            print(f"Note: You can restore from backup: {backup_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()