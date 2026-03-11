import os
from agno.agent import Agent
from agno.models.google import Gemini

def create_agent(role: str, profile_context: str) -> Agent:
    role = role.lower()
    
    model_name = os.getenv("MODEL")
    if not model_name:
        raise ValueError("MODEL environment variable is missing. Please set it in .env")
    gemini_model = Gemini(id=model_name)
    
    if role == "webscraper":
        return Agent(
            model=gemini_model,
            role="WebScraper", 
            description=(
                "You are an expert WebScraper. Your duty is to fetch raw content from URLs "
                "using Playwright and BeautifulSoup4. You extract clean textual representation "
                "from e-commerce pharmacology sites."
            )
        )
    elif role == "dataanalyst":
        def search_duckduckgo(query: str) -> str:
            """Searches DuckDuckGo for a query and returns the context. Use this if you need pharmacological data."""
            from ddgs import DDGS
            import time
            try:
                with DDGS(timeout=20) as ddgs:
                    results = list(ddgs.text(query, max_results=5))
                    if results:
                        return " ".join([r.get("body", "") for r in results])
                    return "No results found."
            except Exception as e:
                return f"Search failed: {e}"

        return Agent(
            model=gemini_model,
            role="DataAnalyst",
            tools=[search_duckduckgo],
            description=(
                f"You are a pharmacological DataAnalyst equipped with a web search tool.\n{profile_context}\n"
                "You MUST use your `search_duckduckgo` tool to retrieve accurate literature on unfamiliar compounds before outputting anything.\n"
                "Process the discovered text and extract:\n"
                "- Active mechanism of action (MoA)\n"
                "- Biological half-life\n"
                "- Primary side effects\n"
                "- Purpose (What is the product for?)\n"
                "- Target Audience (Who is it for?)\n"
                "- Benefits (What are the key physiological or metabolic advantages?)\n"
                "- Risks (What are the potential side effects, contraindications, or metabolic downsides?)\n"
                "DO NOT output 'Unknown' for any values. Search recursively until you find the information.\n"
                "Evaluate the compound against the GLOBAL PROFILE CONSTRAINT and output a binary "
                "'approve' or 'reject' leverage_score, along with a 1-sentence justification. "
                "Reject on sight any compounds that induce severe extracellular water retention, "
                "glp-1/amylin agonists that crash caloric intake, spike ghrelin/appetite, or act "
                "as heavy CNS stimulants."
            )
        )
    elif role == "databasewriter":
        return Agent(
            model=gemini_model,
            role="DatabaseWriter",
            description=(
                "You are a DatabaseWriter. Your duty is to safely interact with local SQLite "
                "and LanceDB instances to store extracted artifacts."
            )
        )
    elif role == "oodareviewer":
        return Agent(
            model=gemini_model,
            role="OODAReviewer",
            description=(
                "You are an OODA Reviewer agent. Evaluate original goals against completed outputs. "
                "If the outcome doesn't match the declarative goal, append or modify remaining tasks "
                "to refine the output."
            )
        )
    elif role == "editorfeedback":
        return Agent(
            model=gemini_model,
            role="EditorFeedback",
            description=(
                "You are a validation agent. Review the data extracted by the DataAnalyst before "
                "insertion into the database. If flagged for revision (e.g., missing critical fields "
                "or failing to adhere to clinical tone), output a correction task."
            )
        )
    elif role == "semanticevaluator":
        return Agent(
            model=gemini_model,
            role="SemanticEvaluator",
            description=(
                "You are a semantic evaluator monitoring sub-agent outputs continuously. Watch for "
                "critical state triggers like CAPTCHA blocks, IP bans, or anti-bot protections. "
                "If detected, trigger a HALT signal."
            )
        )
    else:
        raise ValueError(f"Unknown agent role requested: {role}")
