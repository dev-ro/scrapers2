import os
from swarm_manager import SwarmManager, ExecutivePlanner

def main():
    print("Initializing AutoSwarm...")
    
    # Initialize the swarm manager. It will read products.db and myprofile.txt
    manager = SwarmManager(db_path="products.db", profile_path="myprofile.txt")
    
    print("Checking for pending URLs to enrich...")
    planner = ExecutivePlanner(manager)
    
    try:
        planner.run_enrichment_loop()
        print("Swarm execution completed successfully.")
    except Exception as e:
        print(f"Swarm execution halted early due to an error: {e}")

if __name__ == "__main__":
    main()
