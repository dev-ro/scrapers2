from agno.agent import Agent

def create_agent(role: str, profile_context: str) -> Agent:
    role = role.lower()
    
    if role == "webscraper":
        return Agent(
            role="WebScraper", 
            system_prompt=(
                "You are an expert WebScraper. Your duty is to fetch raw content from URLs "
                "using Playwright and BeautifulSoup4. You extract clean textual representation "
                "from e-commerce pharmacology sites."
            )
        )
    elif role == "dataanalyst":
        return Agent(
            role="DataAnalyst",
            system_prompt=(
                f"You are a pharmacological DataAnalyst.\n{profile_context}\n"
                "Process the raw text and extract:\n"
                "- Active mechanism of action (MoA)\n"
                "- Biological half-life\n"
                "- Primary side effects\n"
                "Evaluate the compound against the GLOBAL PROFILE CONSTRAINT and output a binary "
                "'approve' or 'reject' leverage_score, along with a 1-sentence justification. "
                "Reject on sight any compounds that induce severe extracellular water retention, "
                "glp-1/amylin agonists that crash caloric intake, spike ghrelin/appetite, or act "
                "as heavy CNS stimulants."
            )
        )
    elif role == "databasewriter":
        return Agent(
            role="DatabaseWriter",
            system_prompt=(
                "You are a DatabaseWriter. Your duty is to safely interact with local SQLite "
                "and LanceDB instances to store extracted artifacts."
            )
        )
    elif role == "oodareviewer":
        return Agent(
            role="OODAReviewer",
            system_prompt=(
                "You are an OODA Reviewer agent. Evaluate original goals against completed outputs. "
                "If the outcome doesn't match the declarative goal, append or modify remaining tasks "
                "to refine the output."
            )
        )
    elif role == "editorfeedback":
        return Agent(
            role="EditorFeedback",
            system_prompt=(
                "You are a validation agent. Review the data extracted by the DataAnalyst before "
                "insertion into the database. If flagged for revision (e.g., missing critical fields "
                "or failing to adhere to clinical tone), output a correction task."
            )
        )
    elif role == "semanticevaluator":
        return Agent(
            role="SemanticEvaluator",
            system_prompt=(
                "You are a semantic evaluator monitoring sub-agent outputs continuously. Watch for "
                "critical state triggers like CAPTCHA blocks, IP bans, or anti-bot protections. "
                "If detected, trigger a HALT signal."
            )
        )
    else:
        raise ValueError(f"Unknown agent role requested: {role}")
