import pytest
from enrichment import extract_compound_data

def test_extract_compound_data_mocked(monkeypatch):
    class MockDDGS:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def text(self, query, max_results=1):
            if "mechanism of action" in query:
                return [{"body": "It acts as a ghrelin receptor agonist."}]
            if "half life" in query:
                return [{"body": "The half-life is approximately 24 hours."}]
            if "side effects" in query:
                return [{"body": "Side effects include water retention and lethargy."}]
            return []

    # Apply the monkeypatch for DDGS in the enrichment module
    import enrichment
    monkeypatch.setattr(enrichment, "DDGS", MockDDGS)

    moa, hl, se = extract_compound_data("MK-677")
    
    assert "ghrelin receptor agonist" in moa.lower()
    assert "24 hours" in hl.lower()
    assert "water retention" in se.lower()
