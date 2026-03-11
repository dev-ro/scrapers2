import sqlite3
import time

from swarm_manager import SwarmManager
import json
import re
from dotenv import load_dotenv

# Try to load from current dir, then fallback to parent dir
if not load_dotenv('.env'):
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
        ("justification", "TEXT"),
        ("purpose", "TEXT"),
        ("target_audience", "TEXT"),
        ("benefits", "TEXT"),
        ("risks", "TEXT")
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                c.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass # Column exists
                
    conn.commit()
    return conn

import re

def parse_compound_components(compound_name: str) -> list[str]:
    """
    Extracts individual component names from blend strings like '4x Blend: A / B / C'.
    If not a blend, returns a single-item list with the compound_name.
    """
    if "blend" in compound_name.lower() or "/" in compound_name:
        name_only = re.sub(r'(?i)^.*blend[^a-z0-9]*', '', compound_name)
        components = [c.strip() for c in re.split(r'[/,]', name_only) if c.strip()]
        if components:
            return components
    return [compound_name.strip()]

# Removed hardcoded DDGS logic - agents handle search natively now.

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
        
        components = parse_compound_components(title)
        comp_results = []
        failed_any = False
        
        for comp in components:
            clean_name = re.sub(r'\([^\)]*\)', '', comp).strip()
            clean_name = re.sub(r'\d+(mg|mcg|ml)\b', '', clean_name, flags=re.IGNORECASE).strip()
            
            if not clean_name:
                continue
                
            # 2. Evaluate against baseline using LLM Swarm Agent with retry loop
            base_prompt = (
                f"You are responsible for finding the pharmacology data for the component '{clean_name}'. "
                f"Use your `search_duckduckgo` tool to dynamically research this compound.\n"
                "Your response must be exclusively valid JSON with these EXACT keys:\n"
                '{"moa": "...", "half_life": "...", "side_effects": "...", "leverage_score": 1_or_0, "justification": "...", "purpose": "...", "target_audience": "...", "benefits": "...", "risks": "..."}'
            )
            
            prompt = base_prompt
            max_retries = 3
            data = None
            
            for attempt in range(max_retries):
                try:
                    print(f"Sending prompt to LLM for {clean_name} (Attempt {attempt+1})...")
                    analysis_resp = analyst.run(prompt)
                    analysis_text = analysis_resp.content if hasattr(analysis_resp, 'content') else str(analysis_resp)
                    
                    clean_json = analysis_text.strip()
                    if clean_json.startswith('```json'):
                        clean_json = clean_json.split('```json')[1].split('```')[0].strip()
                    elif clean_json.startswith('```'):
                        clean_json = clean_json.split('```')[1].split('```')[0].strip()
                        
                    data = json.loads(clean_json)
                    
                    moa = str(data.get('moa', 'Unknown')).lower()
                    hl = str(data.get('half_life', 'Unknown')).lower()
                    se = str(data.get('side_effects', 'Unknown')).lower()
                    
                    if "unknown" in moa or "unknown" in hl or "unknown" in se:
                        print(f"Data contains unknowns. Retrying... {data}")
                        prompt = base_prompt + "\n\nWARNING: Your last output contained 'Unknown'. You MUST search more deeply to find the actual mechanism of action, half-life, and side effects. DO NOT GIVE UP. You have a search tool for a reason."
                        time.sleep(2)
                        data = None
                        continue
                        
                    break # Success
                    
                except Exception as e:
                    print(f"Failed to evaluate {clean_name} with LLM: {str(e)}")
                    time.sleep(2)
                    
            if not data:
                print(f"Failed to extract valid knowledge for {clean_name} after {max_retries} attempts.")
                failed_any = True
                break
                
            comp_results.append(data)
                
        if failed_any or not comp_results:
            print(f"Failed to fully process {safe_title}. Skipping DB update.")
            continue
            
        agg_moa = " / ".join([str(d.get('moa', 'Unknown')) for d in comp_results])
        agg_hl = " / ".join([str(d.get('half_life', 'Unknown')) for d in comp_results])
        agg_se = " / ".join([str(d.get('side_effects', 'Unknown')) for d in comp_results])
        agg_purpose = " / ".join([str(d.get('purpose', 'Unknown')) for d in comp_results])
        agg_audience = " / ".join([str(d.get('target_audience', 'Unknown')) for d in comp_results])
        agg_benefits = " / ".join([str(d.get('benefits', 'Unknown')) for d in comp_results])
        agg_risks = " / ".join([str(d.get('risks', 'Unknown')) for d in comp_results])
        
        scores = []
        for d in comp_results:
            score_val = d.get('leverage_score', 0)
            if isinstance(score_val, str):
                scores.append(1 if score_val.lower() == 'approve' else 0)
            elif isinstance(score_val, int):
                scores.append(score_val)
            elif isinstance(score_val, float):
                scores.append(int(score_val))
            else:
                scores.append(0)
                
        # Reject blend if any component is rejected
        final_score = 0 if 0 in scores else 1
        agg_just = " / ".join([str(d.get('justification', 'Unknown')) for d in comp_results])
        
        # 3. Update database
        c.execute('''
            UPDATE products 
            SET moa = ?, half_life = ?, side_effects = ?, leverage_score = ?, justification = ?,
                purpose = ?, target_audience = ?, benefits = ?, risks = ?
            WHERE id = ?
        ''', (agg_moa, agg_hl, agg_se, final_score, agg_just, 
              agg_purpose, agg_audience, agg_benefits, agg_risks, record_id))
        
        conn.commit()
        print(f"Successfully evaluated DB update for {safe_title}: Score {final_score}")
            
    print("Enrichment process completed.")
    conn.close()




if __name__ == "__main__":
    import sys
    db_path = "products.db" if len(sys.argv) == 1 else sys.argv[1]
    process_un_enriched_compounds(db_path)

