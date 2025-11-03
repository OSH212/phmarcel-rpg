"""
Database initialization script

Run this script to create all database tables.
Usage: python init_db.py
"""
import asyncio
from app.core.database import engine, Base
from app.models import Client, Intake, Document, ChecklistItem


async def init_database():
    """Create all database tables"""
    print("Creating database tables...")
    
    async with engine.begin() as conn:
        # Drop all tables (useful for development)
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created successfully!")
    print("\nTables created:")
    print("  - clients")
    print("  - intakes")
    print("  - documents")
    print("  - checklist_items")


async def drop_database():
    """Drop all database tables"""
    print("Dropping all database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("✅ Database tables dropped successfully!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        asyncio.run(drop_database())
    else:
        asyncio.run(init_database())

