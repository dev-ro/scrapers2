import os
import sqlite3
import pytest
from swarm_state import SwarmState
from swarm_manager import SwarmManager, ExecutivePlanner

@pytest.fixture
def test_manager(tmp_path):
    # Set up temporary databases
    db_path = str(tmp_path / "test_products.db")
    
    # Initialize basic DB schema required by SwarmState
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            category TEXT,
            price TEXT,
            availability TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

    # Pre-populate one test URL
    state = SwarmState(db_path)
    with state.get_db() as db:
        db.execute(
            "INSERT INTO products (name, url) VALUES (?, ?)",
            ("Test Compound", "https://example.com/test-compound")
        )
    
    manager = SwarmManager(db_path=db_path)
    # Redirect LanceDB to tmp path so we don't pollute local
    manager.lancedb_path = str(tmp_path / "test_lancedb")
    # Actually wait, Manager's init already calls lancedb.connect("lancedb_vector_store")
    # Let's monkeypatch it after creation or adjust Manager to accept lancedb_path
    
    yield manager

def test_enrichment_loop(test_manager, monkeypatch):
    # Mock HITL to automatically approve
    from swarm_resilience import HITL
    from agno.agent import Agent
    
    monkeypatch.setattr(HITL, "prompt_approval", lambda msg: "y")
    
    class MockResponse:
        def __init__(self, content):
            self.content = content
            
    def mock_run(self, prompt, *args, **kwargs):
        if self.role == "WebScraper":
            return MockResponse("Mocked HTML content")
        elif self.role == "DataAnalyst":
            return MockResponse(
                '{"moa": "Mocked MoA", "half_life": "24h", "side_effects": "None", "leverage_score": "approve", "justification": "Test"}'
            )
        elif self.role == "SemanticEvaluator":
            return MockResponse("PASS")
        elif self.role == "EditorFeedback":
            return MockResponse("APPROVE")
        else:
            return MockResponse("OK")
            
    monkeypatch.setattr(Agent, "run", mock_run)
    
    planner = ExecutivePlanner(test_manager)
    
    # Execute the loop
    planner.run_enrichment_loop()
    
    # Verify that the URL was processed (leverage_score populated)
    # The SwarmManager loop should update products.leverage_score
    with test_manager.state.get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id=1").fetchone()
        assert product['leverage_score'] is not None
        assert product['moa'] is not None
        assert product['half_life'] is not None
        assert product['side_effects'] is not None
        assert product['justification'] is not None
