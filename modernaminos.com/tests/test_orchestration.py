import sqlite3
import pytest
from enrichment import process_un_enriched_compounds, setup_database

def test_process_un_enriched_compounds(monkeypatch, tmp_path):
    class MockDDGS:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def text(self, query, max_results=1):
            if "mk-677 mechanism" in query.lower():
                return [{"body": "ghrelin receptor agonist"}]
            if "mk-677 biological half" in query.lower():
                return [{"body": "24 hours"}]
            if "mk-677 primary side" in query.lower():
                return [{"body": "appetite increase"}]
            return []

    import enrichment
    monkeypatch.setattr(enrichment, "DDGS", MockDDGS)
    
    # 0 sec sleep for tests
    import time
    monkeypatch.setattr(time, "sleep", lambda x: None)
    
    db_path = tmp_path / "test_products.db"
    conn = setup_database(str(db_path))
    c = conn.cursor()
    c.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            price TEXT,
            categories TEXT,
            description TEXT,
            image_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            moa TEXT,
            half_life TEXT,
            side_effects TEXT,
            leverage_score INTEGER,
            justification TEXT
        )
    ''')
    c.execute('''
        INSERT INTO products (url, title, price) VALUES 
        ('http://test.com/mk677', 'MK-677', '50.00')
    ''')
    conn.commit()
    conn.close()

    process_un_enriched_compounds(str(db_path))

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT moa, leverage_score FROM products WHERE title = 'MK-677'")
    row = c.fetchone()
    
    assert row is not None
    assert "ghrelin" in row[0]
    assert row[1] == 0 # Should be rejected due to ghrelin
    conn.close()
