import sqlite3
import time
from ddgs import DDGS

def setup_database(db_path: str):
    """
    Connects to the database and ensures the schema has the new enrichment columns.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check existing columns
    c.execute("PRAGMA table_info(products)")
    columns = set(row[1] for row in c.fetchall())
    
    new_columns = [
        ("moa", "TEXT"),
        ("half_life", "TEXT"),
        ("side_effects", "TEXT"),
        ("leverage_score", "INTEGER"),
        ("justification", "TEXT")
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                c.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass # Column exists
                
    conn.commit()
    return conn

def extract_compound_data(compound_name: str) -> tuple[str, str, str]:
    """
    Queries DDG for Mechanism of Action, Half-Life, and Side Effects.
    """
    queries = {
        "moa": f"{compound_name} mechanism of action pharmacology",
        "half_life": f"{compound_name} biological half life",
        "side_effects": f"{compound_name} primary side effects bodybuilding"
    }
    
    results = {"moa": "Unknown", "half_life": "Unknown", "side_effects": "Unknown"}
    
    try:
        with DDGS() as ddgs:
            for key, query in queries.items():
                time.sleep(2) # rate limit protection
                search_results = list(ddgs.text(query, max_results=3))
                if search_results:
                    body = " ".join([r.get("body", "") for r in search_results])
                    if body:
                        results[key] = body[:250]
    except Exception as e:
        print(f"Extraction failed for {compound_name}: {e}")
        
    return results["moa"], results["half_life"], results["side_effects"]

def process_un_enriched_compounds(db_path: str):
    """
    Main orchestration function to fetch null records, extract data,
    evaluate leverage, and update the database.
    """
    conn = setup_database(db_path)
    c = conn.cursor()
    
    # Fetch records that need enrichment
    c.execute("SELECT id, title FROM products WHERE leverage_score IS NULL")
    records = c.fetchall()
    
    print(f"Found {len(records)} records requiring enrichment.")
    
    for record_id, title in records:
        print(f"Processing: {title}")
        
        # 1. Extract data from web
        moa, half_life, side_effects = extract_compound_data(title)
        
        # 2. Evaluate against baseline
        score, justification = evaluate_leverage(title, moa, half_life, side_effects)
        
        # 3. Update database
        c.execute('''
            UPDATE products 
            SET moa = ?, half_life = ?, side_effects = ?, leverage_score = ?, justification = ?
            WHERE id = ?
        ''', (moa, half_life, side_effects, score, justification, record_id))
        
        conn.commit()
        time.sleep(1) # Base rate limit between compounds
        
    print("Enrichment process completed.")
    conn.close()


def evaluate_leverage(title: str, moa: str, half_life: str, side_effects: str) -> tuple[int, str]:
    """
    Evaluates compound against baseline parameters:
    detrained male subject, 10-week testosterone/trenbolone enanthate, 2150 kcal deficit.
    Returns (score, justification).
    """
    combined_text = f"{moa} {side_effects} {title}".lower()
    
    # Negative leverage flags
    appetite_flags = ["ghrelin", "appetite", "hunger", "mk-677", "mk677"]
    water_flags = ["water retention", "aromatiz", "estrogen", "gynecomastia", "edema", "dianabol"]
    cardio_flags = ["cardiovascular strain", "liver toxicity", "hepatotoxic", "blood pressure spike"]
    
    if any(flag in combined_text for flag in appetite_flags):
        return 0, "Rejected: Compound induces aggressive appetite spiking (ghrelin agonism) incompatible with 2150 kcal deficit."
        
    if any(flag in combined_text for flag in water_flags):
        return 0, "Rejected: Compound induces heavy extracellular water retention or estrogenic conversion, contraindicating baseline fat loss goals."
        
    if any(flag in combined_text for flag in cardio_flags):
        return 0, "Rejected: Compound induces severe cardiovascular strain or liver toxicity, compounding trenbolone baseline stress."
        
    moa_summary = moa[:60] + "..." if len(moa) > 60 else moa
    se_summary = side_effects[:60] + "..." if len(side_effects) > 60 else side_effects
    
    if "unknown" in moa.lower() or "unknown" in side_effects.lower():
        return 0, "Rejected: Insufficient pharmacological data extracted to guarantee baseline safety."
        
    return 1, f"Approved. MoA: {moa_summary} | Sides: {se_summary}"

if __name__ == "__main__":
    import sys
    db_path = "products.db" if len(sys.argv) == 1 else sys.argv[1]
    process_un_enriched_compounds(db_path)

