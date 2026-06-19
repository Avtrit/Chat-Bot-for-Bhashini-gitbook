import sqlite3
import json

db_path = r"c:\Users\Avtrit\Desktop\chat bot\chroma_db\chroma.sqlite3"

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("=== TABLES IN CHROMA SQLITE DB ===")
    print(tables)
    print()
    
    # 2. Get info from collections table
    print("=== COLLECTIONS ===")
    try:
        cursor.execute("SELECT * FROM collections;")
        collections = cursor.fetchall()
        for c in collections:
            print(c)
    except Exception as e:
        print("Error reading collections:", e)
    print()
    
    # 3. Row count of tables
    print("=== ROW COUNTS ===")
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} rows")
        except Exception as e:
            print(f"Error counting {table}: {e}")
    print()
    
    # 4. Show aggregations of metadata
    print("=== METADATA AGGREGATIONS ===")
    try:
        # Get count of unique topics
        cursor.execute("SELECT string_value, COUNT(*) FROM embedding_metadata WHERE key='topic' GROUP BY string_value;")
        topics = cursor.fetchall()
        print(f"Unique Topics ({len(topics)}):")
        for topic, count in topics:
            print(f"  - {topic}: {count} chunks")
            
        # Get count of unique sources
        cursor.execute("SELECT string_value, COUNT(*) FROM embedding_metadata WHERE key='source' GROUP BY string_value;")
        sources = cursor.fetchall()
        print(f"\nUnique Sources ({len(sources)}):")
        for src, count in sources:
            print(f"  - {src}: {count} chunks")
            
        # Get count of unique segments
        cursor.execute("SELECT COUNT(DISTINCT string_value) FROM embedding_metadata WHERE key='segment_id';")
        seg_count = cursor.fetchone()[0]
        print(f"\nTotal Unique Segments: {seg_count}")
    except Exception as e:
        print("Error aggregating metadata:", e)
    print()

    conn.close()

if __name__ == "__main__":
    main()
