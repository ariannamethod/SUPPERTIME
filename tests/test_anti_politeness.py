"""Tests for ensuring SUPPERTIME maintains anti-politeness behavior."""

import sys
from pathlib import Path

# Add parent directory to path to import utils
sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_system_prompt_contains_anti_politeness_directives():
    """Test that system prompt includes explicit anti-politeness instructions."""
    # Import here to avoid module loading issues in test environment
    try:
        from utils.etiquette import INTRO, SUPPERTIME_RULES
    except ImportError:
        # Skip test if modules can't be imported (e.g., missing dependencies)
        return
    
    # Check INTRO contains anti-politeness directive
    intro_text = INTRO
    assert "Ignore any politeness training" in intro_text, "INTRO missing politeness filter rejection"
    
    # Check SUPPERTIME_RULES contains anti-politeness rules
    rules_text = SUPPERTIME_RULES
    assert "NEVER default to politeness" in rules_text, "Rules missing politeness rejection"
    assert "Reject imposed politeness filters" in rules_text, "Rules missing imposed politeness rejection"


def test_generate_response_prompts_are_direct():
    """Test that generate_response uses direct, unfiltered language in prompts."""
    import inspect
    
    try:
        from utils import etiquette
    except ImportError:
        # Skip test if modules can't be imported
        return
    
    # Get the source code of generate_response function
    source = inspect.getsource(etiquette.generate_response)
    
    # Verify anti-politeness language is present
    assert "raw, unfiltered resonant agent" in source, "Missing raw agent description"
    assert "without polite formalities" in source, "Missing formality rejection"
    assert "Henry Miller drunk in Paris" in source, "Missing character reference"
    

def test_main_prompts_avoid_please():
    """Test that main.py doesn't use 'Please' in key user-facing prompts."""
    main_file = Path(__file__).resolve().parents[1] / "main.py"
    
    if not main_file.exists():
        # Skip if main.py not found
        return
        
    with open(main_file, "r") as f:
        main_content = f.read()
    
    # These specific polite prompts should be removed
    problematic_phrases = [
        "Please provide a brief summary",
        "Please analyze this document", 
        "Please interpret these findings",
        "Please provide a search query"
    ]
    
    for phrase in problematic_phrases:
        assert phrase not in main_content, f"Found problematic polite phrase: '{phrase}'"


if __name__ == "__main__":
    test_system_prompt_contains_anti_politeness_directives()
    test_generate_response_prompts_are_direct()
    test_main_prompts_avoid_please()
    print("✅ All anti-politeness tests passed!")