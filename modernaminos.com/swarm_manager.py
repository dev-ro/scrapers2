import os
import lancedb
from swarm_state import SwarmState

class SwarmManager:
    def __init__(self, db_path="products.db", profile_path="myprofile.txt"):
        self.state = SwarmState(db_path)
        self.profile_path = profile_path
        self._profile_context = None
        self._agents = {}
        
        # Initialize LanceDB
        self.lancedb_path = "lancedb_vector_store"
        self.vector_db = lancedb.connect(self.lancedb_path)

    @property
    def profile_context(self):
        if self._profile_context is None:
            if os.path.exists(self.profile_path):
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = "No biological profile strictly enforced."
            
            self._profile_context = f"GLOBAL PROFILE CONSTRAINT:\n{content}\n"
            
        return self._profile_context

    def get_agent(self, role: str):
        """Lazy loads sub-agents exclusively when required."""
        if role not in self._agents:
            # Lazy load agents from swarm_agents to avoid circular imports / load overhead
            from swarm_agents import create_agent
            self._agents[role] = create_agent(role, self.profile_context)
        return self._agents[role]

class ExecutivePlanner:
    def __init__(self, manager: SwarmManager):
        self.manager = manager

    def run_enrichment_loop(self):
        """
        Executive loop to pull pending URLs, dispatch WebScraper -> DataAnalyst -> DatabaseWriter
        with resilience layers (OODA reviewer, Editor Feedback, Semantic Handoff).
        """
        urls_to_process = self.manager.state.get_pending_urls()
        
        if not urls_to_process:
            print("No pending URLs left to process.")
            return

        plan_id = self.manager.state.create_plan(f"Enrichment Loop for {len(urls_to_process)} URLs")
        
        try:
            for item in urls_to_process:
                # Stub out orchestration logic
                url_id = item['id']
                url = item['url']
                
                # Fetching...
                # Analyzing...
                # Saving...
                pass
            
            self.manager.state.update_plan_status(plan_id, "completed")
        except Exception as e:
            self.manager.state.update_plan_status(plan_id, "failed")
            raise e
