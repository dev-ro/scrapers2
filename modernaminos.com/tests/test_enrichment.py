import sqlite3
import pytest
from enrichment import evaluate_leverage, setup_database

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_products.db"
    
    # Create base schema
    conn = sqlite3.connect(str(db_path))
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
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        INSERT INTO products (url, title, price) VALUES 
        ('http://test.com/mk677', 'MK-677', '50.00'),
        ('http://test.com/dianabol', 'Dianabol', '30.00'),
        ('http://test.com/bpc157', 'BPC-157', '40.00')
    ''')
    conn.commit()
    conn.close()

    # Run the setup script to alter table
    conn = setup_database(str(db_path))
    c = conn.cursor()
    
    # Verify new columns exist
    c.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in c.fetchall()]
    assert 'moa' in columns
    assert 'leverage_score' in columns
    
    yield str(db_path)
    conn.close()

def test_ghrelin_agonist_rejection():
    # MK-677 should be rejected due to aggressive appetite spiking and water retention
    score, justification = evaluate_leverage("MK-677", "Ghrelin receptor agonist", "24 hours", "Increased appetite, water retention, lethargy")
    assert score == 0
    assert "ghrelin" in justification.lower() or "appetite" in justification.lower()

def test_aromatizing_compound_rejection():
    # Dianabol should be rejected due to high estrogenic conversion and water retention
    score, justification = evaluate_leverage("Dianabol", "Androgen receptor agonist", "3-6 hours", "Water retention, gynecomastia, liver toxicity")
    assert score == 0
    assert "water retention" in justification.lower() or "aromatiz" in justification.lower() or "estrogen" in justification.lower()

def test_neutral_or_positive_peptide():
    # BPC-157 has no negative interaction with test/tren/caloric deficit baseline
    score, justification = evaluate_leverage("BPC-157", "Systemic healing peptide", "4 hours", "Mild nausea")
    assert score == 1
    assert "baseline" in justification.lower() or "approve" in justification.lower()
