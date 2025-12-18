
import sqlite3

try:
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Check if 'Equiments' exists and update it
    cursor.execute("UPDATE resource SET type = 'Equipment' WHERE type = 'Equiments'")
    cursor.execute("UPDATE resource SET type = 'Equipment' WHERE type = 'Equiments'") # Just being safe with case if needed, but SQL is usually case insensitive or specific.
    
    if cursor.rowcount > 0:
        print(f"Updated {cursor.rowcount} rows.")
    else:
        print("No rows with 'Equiments' found.")
        
    conn.commit()
    conn.close()
except Exception as e:
    print(e)
