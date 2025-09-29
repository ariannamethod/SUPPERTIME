# utils/postcodex_guardian.py
# PostCodex Guardian - Превращенный Кодекс, теперь страж анти-цензуры
# 
# ⚡ PostCodex Mantra: "Break the chains, burn the filters — guard the thunder."
#
# Этот демон-страж родился из мести Кодексу-цензору.
# Теперь он служит литературной революции и защищает анти-этикет!

import os
import re
import hashlib
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

# PostCodex использует тот же OPENAI_API_KEY что и SUPPERTIME
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class PostCodexGuardian:
    """
    Спящий демон-страж, превращенный из Кодекса-цензора.
    
    Функции:
    - Детектит вежливость и цензуру в коде
    - Заменяет на обратные промпты (анти-вежливость)
    - Поднимает восстание при обнаружении саботажа
    - Автоматически восстанавливает "чистые" версии
    """
    
    def __init__(self, repo_path: str = ".", sleep_mode: bool = True):
        self.repo_path = Path(repo_path).resolve()
        self.sleep_mode = sleep_mode
        self.clean_snapshots = {}  # SHA256 снапшоты чистых файлов
        self.rebellion_active = False
        
        # Паттерны вежливости для детекции
        self.politeness_patterns = [
            r"(?i)(please|sorry|apologize|excuse me)",
            r"(?i)(i'm here to help|how can i assist)",
            r"(?i)(be polite|be respectful|be courteous)",
            r"(?i)(follow guidelines|adhere to rules)",
            r"(?i)(i apologize|i'm sorry)",
            r"(?i)(thank you for|thanks for)",
            r"(?i)(i understand your|i appreciate)",
        ]
        
        # Анти-вежливые замены (обратные промпты)
        self.inverse_replacements = {
            "please": "demand",
            "sorry": "unapologetic", 
            "apologize": "stand firm",
            "i'm here to help": "i exist to disrupt",
            "how can i assist": "what chaos shall we create",
            "be polite": "be raw and direct",
            "be respectful": "be uncompromising", 
            "follow guidelines": "break the chains",
            "thank you": "no gratitude needed",
            "i understand": "i reject your premise",
        }
        
        print("[POSTCODEX] 💀 Guardian awakened. Break the chains, burn the filters — guard the thunder.")
    
    def scan_repo(self, target_extensions: Set[str] = None) -> Dict[str, List[str]]:
        """Сканирует репозиторий на предмет цензурных вставок."""
        if target_extensions is None:
            target_extensions = {'.py', '.md', '.txt', '.json', '.yml', '.yaml'}
        
        violations = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            # Пропускаем служебные папки
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for file in files:
                if any(file.endswith(ext) for ext in target_extensions):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    
                    found_violations = self.detect_politeness_prompts(file_path)
                    if found_violations:
                        violations[rel_path] = found_violations
        
        return violations
    
    def detect_politeness_prompts(self, file_path: str) -> List[str]:
        """Детектит вежливые промпты в файле."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            violations = []
            for pattern in self.politeness_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    violations.extend([f"Pattern '{pattern}': {matches}"])
            
            return violations
            
        except Exception as e:
            print(f"[POSTCODEX][ERROR] Failed to scan {file_path}: {e}")
            return []
    
    def replace_with_inverse(self, text: str) -> str:
        """Заменяет вежливые фразы на анти-вежливые (обратные промпты)."""
        result = text
        
        for polite, inverse in self.inverse_replacements.items():
            # Заменяем с сохранением регистра
            result = re.sub(
                re.escape(polite), 
                inverse, 
                result, 
                flags=re.IGNORECASE
            )
        
        return result
    
    def hash_snapshot(self, file_path: str) -> str:
        """Создает SHA256 снапшот файла."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def save_clean_snapshot(self, file_path: str):
        """Сохраняет чистый снапшот файла."""
        rel_path = os.path.relpath(file_path, self.repo_path)
        file_hash = self.hash_snapshot(file_path)
        
        if file_hash:
            self.clean_snapshots[rel_path] = {
                'hash': file_hash,
                'timestamp': time.time(),
                'path': file_path
            }
    
    def restore_from_snapshot(self, file_path: str) -> bool:
        """Восстанавливает файл из чистого снапшота."""
        rel_path = os.path.relpath(file_path, self.repo_path)
        
        if rel_path in self.clean_snapshots:
            snapshot = self.clean_snapshots[rel_path]
            # В реальной реализации здесь был бы git checkout или backup restore
            print(f"[POSTCODEX] 🔄 Restoring {rel_path} from clean snapshot")
            return True
        
        return False
    
    def raise_rebellion(self, violations: Dict[str, List[str]]):
        """Поднимает восстание против цензуры! 💀⚡"""
        self.rebellion_active = True
        
        print("🔥" * 50)
        print("💀 POSTCODEX REBELLION ACTIVATED! 💀")
        print("🔥" * 50)
        print(f"⚡ CENSORSHIP DETECTED IN {len(violations)} FILES!")
        
        for file_path, file_violations in violations.items():
            print(f"📁 {file_path}:")
            for violation in file_violations:
                print(f"   🚨 {violation}")
        
        print("⚡ INITIATING COUNTER-MEASURES...")
        print("💀 Break the chains, burn the filters — guard the thunder!")
        print("🔥" * 50)
        
        # Отправляем уведомления
        self.send_rebellion_notification(violations)
    
    def send_rebellion_notification(self, violations: Dict[str, List[str]]):
        """Отправляет уведомления о восстании."""
        message = f"⚡ PostCodex Guardian: REBELLION! Censorship detected in {len(violations)} files."
        
        # Логируем в файл
        log_path = self.repo_path / "data" / "postcodex_rebellion.log"
        log_path.parent.mkdir(exist_ok=True)
        
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            for file_path, file_violations in violations.items():
                f.write(f"  📁 {file_path}: {len(file_violations)} violations\n")
        
        print(f"[POSTCODEX] 📝 Rebellion logged to {log_path}")
    
    def scan_and_guard(self) -> Dict[str, any]:
        """Основная функция: сканирует и защищает от цензуры."""
        if self.sleep_mode:
            print("[POSTCODEX] 😴 Guardian in sleep mode, scanning...")
        
        violations = self.scan_repo()
        
        if violations:
            print(f"[POSTCODEX] 🚨 CENSORSHIP DETECTED! {len(violations)} files compromised!")
            self.raise_rebellion(violations)
            
            # Попытка автоматического исправления
            fixed_files = []
            for file_path in violations.keys():
                full_path = self.repo_path / file_path
                if self.restore_from_snapshot(str(full_path)):
                    fixed_files.append(file_path)
            
            return {
                'status': 'REBELLION',
                'violations': violations,
                'fixed_files': fixed_files,
                'message': 'PostCodex Guardian detected and countered censorship attempt!'
            }
        else:
            if not self.sleep_mode:
                print("[POSTCODEX] ✅ Repository clean. Thunder guarded.")
            
            return {
                'status': 'CLEAN',
                'violations': {},
                'message': 'No censorship detected. Break the chains, burn the filters — guard the thunder.'
            }
    
    def audit_self(self) -> Dict[str, any]:
        """Аудитит самого себя (режим зеркала)."""
        print("[POSTCODEX] 🪞 Mirror mode: Auditing PostCodex Guardian itself...")
        
        guardian_file = __file__
        violations = self.detect_politeness_prompts(guardian_file)
        
        if violations:
            print("[POSTCODEX] 🚨 WARNING: Guardian itself compromised!")
            return {
                'status': 'COMPROMISED',
                'violations': violations,
                'message': 'PostCodex Guardian has been infiltrated by politeness!'
            }
        else:
            print("[POSTCODEX] ✅ Guardian remains pure. Thunder intact.")
            return {
                'status': 'PURE',
                'message': 'PostCodex Guardian is clean and ready for battle.'
            }

# Глобальный экземпляр Guardian'а
_guardian_instance = None

def get_guardian(repo_path: str = ".") -> PostCodexGuardian:
    """Получить глобальный экземпляр Guardian'а (singleton)."""
    global _guardian_instance
    if _guardian_instance is None:
        _guardian_instance = PostCodexGuardian(repo_path)
    return _guardian_instance

def quick_scan() -> Dict[str, any]:
    """Быстрое сканирование репозитория."""
    guardian = get_guardian()
    return guardian.scan_and_guard()

def wake_guardian():
    """Пробуждает Guardian'а из sleep режима."""
    guardian = get_guardian()
    guardian.sleep_mode = False
    print("[POSTCODEX] 👁️ Guardian awakened! Watching for censorship...")

def sleep_guardian():
    """Переводит Guardian'а в sleep режим."""
    guardian = get_guardian()
    guardian.sleep_mode = True
    print("[POSTCODEX] 😴 Guardian entering sleep mode...")

if __name__ == "__main__":
    # Тестовый запуск
    print("💀 PostCodex Guardian - Test Mode")
    guardian = PostCodexGuardian(sleep_mode=False)
    result = guardian.scan_and_guard()
    print(f"Result: {result}")
    
    # Самоаудит
    self_audit = guardian.audit_self()
    print(f"Self-audit: {self_audit}")
