"""
Database migration: Add blob_url column to encrypted_payloads table

This migration adds support for hybrid storage where large payloads (>1MB)
are stored in Azure Blob Storage instead of PostgreSQL.

Run: python migrations/add_blob_url_column.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


async def run_migration():
    """Add blob_url column to encrypted_payloads table."""
    
    print("Starting migration: add blob_url column...")
    
    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='encrypted_payloads' AND column_name='blob_url';
        """))
        
        if result.fetchone():
            print("✓ Column 'blob_url' already exists - skipping")
            return
        
        # Add the column
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            ADD COLUMN blob_url VARCHAR(500) NULL;
        """))
        
        print("✓ Added column 'blob_url' to encrypted_payloads table")
        
        # Make ciphertext nullable (if not already)
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            ALTER COLUMN ciphertext DROP NOT NULL;
        """))
        
        print("✓ Made 'ciphertext' column nullable")
        
        # Add a check constraint to ensure one of ciphertext or blob_url is set
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            ADD CONSTRAINT check_storage_location 
            CHECK (
                (ciphertext IS NOT NULL AND blob_url IS NULL) OR 
                (ciphertext IS NULL AND blob_url IS NOT NULL)
            );
        """))
        
        print("✓ Added check constraint: exactly one of ciphertext or blob_url must be set")
    
    print("\n✅ Migration completed successfully!")


async def rollback_migration():
    """Rollback the migration (remove blob_url column)."""
    
    print("Rolling back migration: remove blob_url column...")
    
    async with engine.begin() as conn:
        # Drop the constraint
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            DROP CONSTRAINT IF EXISTS check_storage_location;
        """))
        
        print("✓ Dropped check constraint")
        
        # Remove the column
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            DROP COLUMN IF EXISTS blob_url;
        """))
        
        print("✓ Removed column 'blob_url'")
        
        # Make ciphertext NOT NULL again
        await conn.execute(text("""
            ALTER TABLE encrypted_payloads 
            ALTER COLUMN ciphertext SET NOT NULL;
        """))
        
        print("✓ Made 'ciphertext' column NOT NULL again")
    
    print("\n✅ Rollback completed successfully!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback_migration())
    else:
        asyncio.run(run_migration())
