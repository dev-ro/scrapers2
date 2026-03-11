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
        
        from swarm_resilience import SemanticHandoff, OutputValidator, HITL, MemoryLeakDetector
        import json
        
        webscraper = self.manager.get_agent("webscraper")
        analyst = self.manager.get_agent("dataanalyst")
        
        semantic_eval = SemanticHandoff(self.manager.get_agent("semanticevaluator"))
        editor = OutputValidator(self.manager.get_agent("editorfeedback"))
        leak_detector = MemoryLeakDetector(self.manager.vector_db)
        
        try:
            for item in urls_to_process:
                url_id = item['id']
                url = item['url']
                task_id = self.manager.state.create_task(plan_id, url_id, "swarm_pipeline")
                
                try:
                    # 1. Scrape
                    scrape_resp = webscraper.run(f"Scrape this URL and return the raw text: {url}")
                    raw_text = scrape_resp.content if hasattr(scrape_resp, 'content') else str(scrape_resp)
                    
                    if semantic_eval.scan_for_blocks(raw_text):
                        self.manager.state.update_task_status(task_id, "failed", "CAPTCHA or Block detected.")
                        continue
                        
                    # 2. Analyze
                    analysis_resp = analyst.run(f"Extract pharmacological data in JSON format from this text:\n\n{raw_text}")
                    analysis_text = analysis_resp.content if hasattr(analysis_resp, 'content') else str(analysis_resp)
                    
                    is_valid, revision_task = editor.validate_extraction(analysis_text)
                    if not is_valid:
                        self.manager.state.update_task_status(task_id, "failed", f"Validation Failed: {revision_task}")
                        continue
                        
                    try:
                        clean_json = analysis_text.strip()
                        if clean_json.startswith('```json'):
                            clean_json = clean_json.split('```json')[1].split('```')[0].strip()
                        elif clean_json.startswith('```'):
                            clean_json = clean_json.split('```')[1].split('```')[0].strip()
                        data = json.loads(clean_json)
                    except json.JSONDecodeError as e:
                        self.manager.state.update_task_status(task_id, "failed", f"Analyst output was not valid JSON: {e}")
                        continue

                    # 3. DB Write Prep & Validation
                    approved = HITL.prompt_approval(f"Approve DB insertion for URL {url}?\nData: {data.get('leverage_score')}")
                    if str(approved) != "y":
                        self.manager.state.update_task_status(task_id, "failed", "HITL rejected.")
                        continue
                        
                    leak_detector.start_monitoring()
                    
                    with self.manager.state.get_db() as db:
                        db.execute(
                            "UPDATE products SET moa=?, half_life=?, side_effects=?, leverage_score=?, justification=? WHERE id=?",
                            (
                                data.get('moa', ''), 
                                data.get('half_life', ''), 
                                data.get('side_effects', ''), 
                                data.get('leverage_score', 'reject'), 
                                data.get('justification', ''), 
                                url_id
                            )
                        )
                        
                    try:
                        table_name = "pharmacology"
                        import pyarrow as pa
                        schema = pa.schema([
                            pa.field("vector", pa.list_(pa.float32(), 128)),
                            pa.field("url_id", pa.int32()),
                            pa.field("text", pa.string())
                        ])
                        
                        if table_name not in self.manager.vector_db.table_names():
                            self.manager.vector_db.create_table(table_name, [{"vector": [0.0]*128, "url_id": url_id, "text": analysis_text}], schema=schema)
                        else:
                            tbl = self.manager.vector_db.open_table(table_name)
                            tbl.add([{"vector": [0.0]*128, "url_id": url_id, "text": analysis_text}])
                    except Exception as e:
                        print(f"LanceDB error: {e}")
                        pass
                        
                    leak_detector.check_and_fallback(self.manager.state, task_id, analysis_text)
                    self.manager.state.update_task_status(task_id, "completed")
                    
                except Exception as e:
                    self.manager.state.update_task_status(task_id, "failed", str(e))
            
            self.manager.state.update_plan_status(plan_id, "completed")
        except Exception as e:
            self.manager.state.update_plan_status(plan_id, "failed")
            raise e
