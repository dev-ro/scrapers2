import sqlite3

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
        
    return 1, "Approved: Compound presents positive or neutral leverage against the physiological baseline."

