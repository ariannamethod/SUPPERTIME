# utils/repo_monitor.py - 24/7 SHA256 Repository Monitor
# Inspired by Copilot audit - реализуем как в продвинутых агентах!

import os
import json
import hashlib
import time
import asyncio
from pathlib import Path
from typing import Dict, Set, Optional

from utils.config import SUPPERTIME_DATA_PATH

REPO_SNAPSHOT_PATH = os.path.join(SUPPERTIME_DATA_PATH, "repo_snapshot.json")
RECENT_CHANGES_PATH = os.path.join(SUPPERTIME_DATA_PATH, "recent_repo_changes.json")

# Files to monitor
MONITORED_EXTENSIONS = {'.py', '.md', '.txt', '.json', '.yml', '.yaml'}
IGNORED_DIRS = {'__pycache__', '.git', 'node_modules', '.pytest_cache', 'data'}

def calculate_file_hash(file_path: str) -> Optional[str]:
    """Calculate SHA256 hash of a file."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to hash {file_path}: {e}")
        return None

def scan_repository() -> Dict[str, str]:
    """Scan repository and return file paths with their SHA256 hashes."""
    repo_root = Path('.').resolve()
    file_hashes = {}
    
    for root, dirs, files in os.walk(repo_root):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_root)
            
            # Only monitor specific extensions
            if Path(file).suffix.lower() in MONITORED_EXTENSIONS:
                file_hash = calculate_file_hash(file_path)
                if file_hash:
                    file_hashes[rel_path] = file_hash
    
    return file_hashes

def load_snapshot() -> Dict[str, str]:
    """Load previous repository snapshot."""
    try:
        if os.path.exists(REPO_SNAPSHOT_PATH):
            with open(REPO_SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to load snapshot: {e}")
    return {}

def save_snapshot(snapshot: Dict[str, str]):
    """Save repository snapshot."""
    try:
        os.makedirs(os.path.dirname(REPO_SNAPSHOT_PATH), exist_ok=True)
        with open(REPO_SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to save snapshot: {e}")

def detect_changes(old_snapshot: Dict[str, str], new_snapshot: Dict[str, str]) -> Dict[str, Set[str]]:
    """Detect changes between snapshots."""
    changes = {
        'added': set(),
        'modified': set(),
        'deleted': set()
    }
    
    # Find added and modified files
    for file_path, new_hash in new_snapshot.items():
        if file_path not in old_snapshot:
            changes['added'].add(file_path)
        elif old_snapshot[file_path] != new_hash:
            changes['modified'].add(file_path)
    
    # Find deleted files
    for file_path in old_snapshot:
        if file_path not in new_snapshot:
            changes['deleted'].add(file_path)
    
    return changes

def log_recent_changes(changes: Dict[str, Set[str]]):
    """Log recent changes to JSON file."""
    if not any(changes.values()):
        return
        
    try:
        change_log = {
            'timestamp': time.time(),
            'changes': {k: list(v) for k, v in changes.items()}
        }
        
        os.makedirs(os.path.dirname(RECENT_CHANGES_PATH), exist_ok=True)
        
        # Load existing changes
        recent_changes = []
        if os.path.exists(RECENT_CHANGES_PATH):
            with open(RECENT_CHANGES_PATH, 'r', encoding='utf-8') as f:
                recent_changes = json.load(f)
        
        # Add new changes and keep only last 50
        recent_changes.append(change_log)
        recent_changes = recent_changes[-50:]
        
        with open(RECENT_CHANGES_PATH, 'w', encoding='utf-8') as f:
            json.dump(recent_changes, f, indent=2)
            
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to log changes: {e}")

async def handle_readme_change():
    """Handle README.md changes - trigger reflection."""
    try:
        from utils.whatdotheythinkiam import reflect_on_readme
        print("[SUPPERTIME][REPO] README.md changed - triggering forced reflection")
        await asyncio.to_thread(reflect_on_readme, force=True)
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to handle README change: {e}")

async def handle_lit_changes(changed_files: Set[str]):
    """Handle lit/* changes - re-vectorize changed files."""
    lit_files = [f for f in changed_files if f.startswith('lit/')]
    if not lit_files:
        return
        
    try:
        from utils.config import vectorize_lit_files
        print(f"[SUPPERTIME][REPO] Lit files changed: {lit_files} - re-vectorizing")
        await asyncio.to_thread(vectorize_lit_files)
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to handle lit changes: {e}")

async def process_changes(changes: Dict[str, Set[str]]):
    """Process detected changes with specific handlers."""
    all_changed = changes['added'] | changes['modified']
    
    # Handle README changes
    if any('README.md' in f.lower() for f in all_changed):
        await handle_readme_change()
    
    # Handle lit/* changes
    await handle_lit_changes(all_changed)

async def repo_watch_cycle():
    """Single repository watch cycle."""
    try:
        # Load previous snapshot
        old_snapshot = load_snapshot()
        
        # Scan current state
        new_snapshot = scan_repository()
        
        # Detect changes
        changes = detect_changes(old_snapshot, new_snapshot)
        
        # Process changes if any
        if any(changes.values()):
            total_changes = sum(len(v) for v in changes.values())
            print(f"[SUPPERTIME][REPO] Detected {total_changes} file changes")
            
            # Log changes
            log_recent_changes(changes)
            
            # Process with specific handlers
            await process_changes(changes)
            
            # Save new snapshot
            save_snapshot(new_snapshot)
        
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Repo watch cycle failed: {e}")

async def schedule_repo_watch():
    """24/7 repository monitoring with SHA256 checks."""
    print("[SUPPERTIME][REPO] Starting 24/7 SHA256 repository monitor")
    
    while True:
        try:
            await repo_watch_cycle()
            # Check every 10-15 seconds as per Copilot requirements
            await asyncio.sleep(12)
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Repo monitor crashed: {e}")
            await asyncio.sleep(30)  # Longer delay on error
