import sys
from swarm_state import SwarmState
from agno.agent import Agent

class MemoryLeakDetector:
    """Monitors LanceDB document counts to detect persistence failures."""
    
    def __init__(self, lancedb_conn, table_name="pharmacology"):
        self.db = lancedb_conn
        self.table_name = table_name
        self.initial_count = 0

    def start_monitoring(self):
        if self.table_name in self.db.table_names():
            table = self.db.open_table(self.table_name)
            self.initial_count = len(table)
            # len(table) might not be directly supported depending on LanceDB version,
            # alternatives: table.count_rows()
            try:
                self.initial_count = table.count_rows()
            except Exception:
                pass
        else:
            self.initial_count = 0

    def check_and_fallback(self, state: SwarmState, task_id: int, extracted_data: str):
        current_count = 0
        if self.table_name in self.db.table_names():
            table = self.db.open_table(self.table_name)
            try:
                current_count = table.count_rows()
            except Exception:
                current_count = len(table) # fallback
            
        if current_count <= self.initial_count and extracted_data:
            # Output was generated but not committed to LanceDB
            print(f"[MemoryLeakDetector] Data not saved in LanceDB for task {task_id}. Triggering fallback.")
            state.save_artifact(task_id, "fallback_raw_data", extracted_data)
            return True
        return False

class HITL:
    """Human-in-the-Loop CLI approval prompt."""
    
    @staticmethod
    def prompt_approval(msg: str) -> str:
        while True:
            choice = input(f"{msg} (y/n/edit): ").strip().lower()
            if choice in ['y', 'n', 'edit']:
                return choice
            print("Invalid input. Valid options are: y, n, edit")

class SemanticHandoff:
    """Uses a SemanticEvaluator agent to scan for blocks like Captchas."""
    
    def __init__(self, evaluator_agent: Agent):
        self.agent = evaluator_agent

    def scan_for_blocks(self, content: str) -> bool:
        prompt = (
            "Review this HTML/text for anti-bot protections, CAPTCHA blocks, or IP bans. "
            "Respond with exactly 'HALT' if detected, otherwise 'PASS'.\n\n"
            f"{content[:2000]}"
        )
        response = self.agent.run(prompt)
        # Handle string response vs complex message object depending on Agno version
        result_text = response.content.upper() if hasattr(response, 'content') else str(response).upper()
        
        if "HALT" in result_text:
            print("[SemanticHandoff] Critical block detected. Halting execution.")
            return True
        return False
        
class OutputValidator:
    """Uses EditorFeedback agent to validate Analyst output."""
    
    def __init__(self, editor_agent: Agent):
        self.agent = editor_agent

    def validate_extraction(self, analyst_output: str) -> tuple[bool, str]:
        prompt = (
            "Review the DataAnalyst's extraction. Validate that it contains MoA, "
            "biological half-life, primary side effects, and a binary leverage_score "
            "with a 1-sentence justification in a cold, clinical tone. "
            "If valid, respond 'APPROVE'. If flawed, respond 'REVISE: <reason>'.\n\n"
            f"{analyst_output}"
        )
        response = self.agent.run(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        
        if result_text.strip().upper().startswith("APPROVE"):
            return True, ""
        return False, result_text
