import sqlite3
import time
from duckduckgo_search import DDGS
from swarm_manager import SwarmManager
import json
from dotenv import load_dotenv

load_dotenv('../.env')
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

def extract_compound_context(compound_name: str) -> str:
    """
    Queries DDG for Mechanism of Action, Half-Life, and Side Effects.
    Returns combined raw text context for the LLM.
    """
    queries = [
        f"{compound_name} mechanism of action pharmacology",
        f"{compound_name} biological half life",
        f"{compound_name} primary side effects bodybuilding"
    ]
    
    combined_context = ""
    
    try:
        with DDGS(timeout=10) as ddgs:
            for query in queries:
                time.sleep(2) # rate limit protection
                search_results = list(ddgs.text(query, max_results=3))
                if search_results:
                    body = " ".join([r.get("body", "") for r in search_results])
                    combined_context += body + " "
    except Exception as e:
        print(f"Extraction failed for {compound_name}: {e}")
        
    return combined_context

def process_un_enriched_compounds(db_path: str):
    """
    Main orchestration function to fetch null records, extract data,
    evaluate leverage, and update the database.
    """
    conn = setup_database(db_path)
    c = conn.cursor()
    
    # Fetch records that need enrichment (now fetching all to overwrite bad data)
    c.execute("SELECT id, title FROM products")
    records = c.fetchall()
    
    manager = SwarmManager(db_path)
    analyst = manager.get_agent("dataanalyst")
    
    for record_id, title in records:
        safe_title = title.encode('ascii', 'replace').decode('ascii')
        print(f"Processing: {safe_title}")
        
        # 1. Extract raw context from web
        raw_context = extract_compound_context(title)
        
        if not raw_context.strip():
            print(f"No context found for {safe_title}. Skipping.")
            continue
            
        # 2. Evaluate against baseline using LLM Swarm Agent
        prompt = (
            f"Extract pharmacological data in JSON format for the compound '{title}' "
            f"from this text:\n\n{raw_context}\n\n"
            "Your response must be exclusively valid JSON with these EXACT keys:\n"
            '{"moa": "...", "half_life": "...", "side_effects": "...", "leverage_score": 1_or_0, "justification": "..."}'
        )
        
        try:
            print(f"Sending prompt to LLM for {safe_title}...")
            analysis_resp = analyst.run(prompt)
            analysis_text = analysis_resp.content if hasattr(analysis_resp, 'content') else str(analysis_resp)
            
            print(f"LLM Response received:\n{analysis_text[:200]}...")
            
            clean_json = analysis_text.strip()
            if clean_json.startswith('```json'):
                clean_json = clean_json.split('```json')[1].split('```')[0].strip()
            elif clean_json.startswith('```'):
                clean_json = clean_json.split('```')[1].split('```')[0].strip()
                
            data = json.loads(clean_json)
            
            moa = data.get('moa', 'Unknown')
            half_life = data.get('half_life', 'Unknown')
            side_effects = data.get('side_effects', 'Unknown')
            
            # Handle leverage score coercion (e.g. from string "reject" to int 0)
            score_val = data.get('leverage_score', 0)
            if isinstance(score_val, str):
                score = 1 if score_val.lower() == 'approve' else 0
            else:
                score = int(score_val)
                
            justification = data.get('justification', 'Unknown')
            
            # 3. Update database
            c.execute('''
                UPDATE products 
                SET moa = ?, half_life = ?, side_effects = ?, leverage_score = ?, justification = ?
                WHERE id = ?
            ''', (moa, half_life, side_effects, score, justification, record_id))
            
            conn.commit()
            print(f"Successfully evaluated DB update for {safe_title}: Score {score}")
            time.sleep(1) # Base rate limit between compounds
            
        except Exception as e:
            print(f"Failed to evaluate {safe_title} with LLM: {str(e)}")
            continue
            
    print("Enrichment process completed.")
    conn.close()




if __name__ == "__main__":
    import sys
    db_path = "products.db" if len(sys.argv) == 1 else sys.argv[1]
    process_un_enriched_compounds(db_path)

