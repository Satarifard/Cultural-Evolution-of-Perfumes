import ast
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns




# Function to parse and clean the 'perfumer' cell
def parse_perfumer(cell):
    if pd.isna(cell):
        return []
    try:
        # Convert string representation to list (e.g., '["Name1", "Name2"]')
        perfumers = ast.literal_eval(cell)
        if isinstance(perfumers, list):
            # Remove extra whitespace and drop empty names
            return [name.strip() for name in perfumers if name.strip() != ""]
        else:
            cleaned = str(perfumers).strip()
            return [cleaned] if cleaned != "" else []
    except Exception:
        # Fallback: if parsing fails, try splitting by commas
        return [name.strip() for name in cell.split(',') if name.strip() != ""]
    
def parse_notes(notes_str):
    try:
        notes_str = notes_str.replace('""', '"')
        return [list(item.keys())[0]          # keep only the note name
                for item in ast.literal_eval(notes_str)]
    except Exception:
        return []    
    
def parse_accords(a_str):
    """
    Convert the JSON‑like string in `accords` to a list of accord names.
    We only need the name to count one occurrence of the accord in this perfume.
    """
    try:
        return [k for k, v in ast.literal_eval(a_str).items() if v > 0]
    except Exception:
        return []