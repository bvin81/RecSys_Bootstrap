from app import get_db_connection

def show_database_structure():
    c = get_db_connection()
    cur = c.cursor()
    
    # Táblák listázása
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")
    tables = [row[0] for row in cur.fetchall()]
    print(f'📋 ÖSSZES TÁBLA ({len(tables)} darab):')
    for table in tables:
        print(f'  - {table}')
    
    # Tábla struktúrák
    print('\n🔍 TÁBLA STRUKTÚRÁK:')
    for table in tables:
        print(f'\n📊 {table.upper()}:')
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position;")
        for col in cur.fetchall():
            print(f'  - {col[0]}: {col[1]}')
    
    c.close()
    print('\n✅ Kész!')

if __name__ == "__main__":
    show_database_structure()
