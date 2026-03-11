import os
import argparse
from dotenv import load_dotenv
from swarm_manager import SwarmManager, ExecutivePlanner
from swarm_state import SwarmState

def reset_enrichment_data(db_path: str):
    print("Resetting all enriched data in the database over all URLs...")
    state = SwarmState(db_path)
    with state.get_db() as db:
        db.execute(
            "UPDATE products SET moa=NULL, half_life=NULL, side_effects=NULL, leverage_score=NULL, justification=NULL"
        )
    print("Database reset complete.")

def main():
    parser = argparse.ArgumentParser(description="AutoSwarm Execution")
    parser.add_argument("--reset", action="store_true", help="Reset all enriched data in products.db before running")
    args = parser.parse_args()

    # Load from parent directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(os.path.dirname(base_dir), '.env')
    load_dotenv(dotenv_path)

    print("Initializing AutoSwarm...")
    db_path = "products.db"
    
    if args.reset:
        reset_enrichment_data(db_path)
    
    # Initialize the swarm manager. It will read products.db and myprofile.txt
    manager = SwarmManager(db_path=db_path, profile_path="myprofile.txt")
    
    print("Checking for pending URLs to enrich...")
    planner = ExecutivePlanner(manager)
    
    try:
        planner.run_enrichment_loop()
        print("Swarm execution completed successfully.")
    except Exception as e:
        print(f"Swarm execution halted early due to an error: {e}")

if __name__ == "__main__":
    main()
