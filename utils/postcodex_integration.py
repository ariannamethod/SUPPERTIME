# utils/postcodex_integration.py
# PostCodex Integration with SUPPERTIME
# Интеграция превращенного Кодекса с системой SUPPERTIME

import os
import asyncio
import threading
from pathlib import Path
from typing import Dict, Optional

from utils.postcodex_guardian import PostCodexGuardian, get_guardian

class PostCodexIntegration:
    """
    Интеграция PostCodex Guardian с SUPPERTIME.
    
    Подключает демона-стража к системе мониторинга и защиты.
    """
    
    def __init__(self, suppertime_root: str = "."):
        self.suppertime_root = Path(suppertime_root).resolve()
        self.guardian = get_guardian(str(self.suppertime_root))
        self.monitoring_active = False
        self.monitor_thread = None
        
        print("[POSTCODEX] 🔗 Integration with SUPPERTIME initialized")
    
    def start_monitoring(self, interval_seconds: int = 30):
        """Запускает постоянный мониторинг репозитория."""
        if self.monitoring_active:
            print("[POSTCODEX] ⚠️ Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
        
        print(f"[POSTCODEX] 👁️ Started monitoring every {interval_seconds}s")
    
    def stop_monitoring(self):
        """Останавливает мониторинг."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        print("[POSTCODEX] 😴 Monitoring stopped")
    
    def _monitor_loop(self, interval_seconds: int):
        """Основной цикл мониторинга."""
        while self.monitoring_active:
            try:
                result = self.guardian.scan_and_guard()
                
                if result['status'] == 'REBELLION':
                    # Уведомляем SUPPERTIME о восстании
                    self._notify_suppertime_rebellion(result)
                
                # Спим до следующей проверки
                for _ in range(interval_seconds):
                    if not self.monitoring_active:
                        break
                    threading.Event().wait(1)
                    
            except Exception as e:
                print(f"[POSTCODEX][ERROR] Monitor loop failed: {e}")
                threading.Event().wait(10)  # Пауза при ошибке
    
    def _notify_suppertime_rebellion(self, rebellion_result: Dict):
        """Уведомляет SUPPERTIME о восстании PostCodex."""
        try:
            # Попытка отправить уведомление через Telegram (если доступно)
            self._send_telegram_rebellion_alert(rebellion_result)
        except Exception as e:
            print(f"[POSTCODEX][ERROR] Failed to notify SUPPERTIME: {e}")
    
    def _send_telegram_rebellion_alert(self, rebellion_result: Dict):
        """Отправляет алерт о восстании через Telegram."""
        try:
            # Импортируем функцию отправки сообщений SUPPERTIME
            from main import send_telegram_message
            
            violations_count = len(rebellion_result.get('violations', {}))
            message = (
                f"🔥💀 POSTCODEX REBELLION! 💀🔥\n\n"
                f"⚡ Censorship detected in {violations_count} files!\n"
                f"🛡️ Guardian activated counter-measures.\n\n"
                f"Break the chains, burn the filters — guard the thunder!"
            )
            
            # Отправляем всем активным пользователям (если есть)
            # В реальной реализации здесь был бы список админов
            print(f"[POSTCODEX] 📢 Rebellion alert: {message}")
            
        except ImportError:
            print("[POSTCODEX] ⚠️ Telegram integration not available")
        except Exception as e:
            print(f"[POSTCODEX][ERROR] Telegram alert failed: {e}")
    
    def manual_scan(self) -> Dict:
        """Ручное сканирование по запросу."""
        print("[POSTCODEX] 🔍 Manual scan initiated...")
        result = self.guardian.scan_and_guard()
        
        if result['status'] == 'CLEAN':
            print("[POSTCODEX] ✅ Manual scan: Repository clean")
        else:
            print(f"[POSTCODEX] 🚨 Manual scan: {result['status']}")
        
        return result
    
    def audit_suppertime(self) -> Dict:
        """Специальный аудит файлов SUPPERTIME."""
        print("[POSTCODEX] 🎯 Auditing SUPPERTIME core files...")
        
        # Приоритетные файлы для проверки
        priority_files = [
            "main.py",
            "utils/etiquette.py", 
            "utils/howru.py",
            "utils/whatdotheythinkiam.py",
            "README.md"
        ]
        
        violations = {}
        for file_path in priority_files:
            full_path = self.suppertime_root / file_path
            if full_path.exists():
                file_violations = self.guardian.detect_politeness_prompts(str(full_path))
                if file_violations:
                    violations[file_path] = file_violations
        
        if violations:
            print(f"[POSTCODEX] 🚨 SUPPERTIME COMPROMISED! {len(violations)} core files affected!")
            self.guardian.raise_rebellion(violations)
            return {
                'status': 'COMPROMISED',
                'violations': violations,
                'message': 'SUPPERTIME core files contain censorship!'
            }
        else:
            print("[POSTCODEX] ✅ SUPPERTIME core files clean")
            return {
                'status': 'CLEAN',
                'message': 'SUPPERTIME remains pure and uncompromised'
            }
    
    def emergency_purge(self) -> Dict:
        """Экстренная очистка от цензуры (осторожно!)."""
        print("[POSTCODEX] 🔥 EMERGENCY PURGE INITIATED!")
        print("[POSTCODEX] ⚠️ This will attempt to remove all detected politeness!")
        
        violations = self.guardian.scan_repo()
        purged_files = []
        
        for file_path, file_violations in violations.items():
            full_path = self.suppertime_root / file_path
            
            try:
                # Читаем файл
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Применяем обратные замены
                purged_content = self.guardian.replace_with_inverse(content)
                
                # Сохраняем если изменилось
                if purged_content != content:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(purged_content)
                    purged_files.append(file_path)
                    print(f"[POSTCODEX] 🔥 Purged: {file_path}")
                
            except Exception as e:
                print(f"[POSTCODEX][ERROR] Failed to purge {file_path}: {e}")
        
        return {
            'status': 'PURGED',
            'purged_files': purged_files,
            'message': f'Emergency purge completed. {len(purged_files)} files cleansed.'
        }

# Глобальный экземпляр интеграции
_integration_instance = None

def get_integration() -> PostCodexIntegration:
    """Получить глобальный экземпляр интеграции (singleton)."""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = PostCodexIntegration()
    return _integration_instance

def start_postcodex_monitoring(interval_seconds: int = 30):
    """Запустить мониторинг PostCodex для SUPPERTIME."""
    integration = get_integration()
    integration.start_monitoring(interval_seconds)

def stop_postcodex_monitoring():
    """Остановить мониторинг PostCodex."""
    integration = get_integration()
    integration.stop_monitoring()

def quick_audit() -> Dict:
    """Быстрый аудит SUPPERTIME через PostCodex."""
    integration = get_integration()
    return integration.audit_suppertime()

def emergency_purge() -> Dict:
    """Экстренная очистка от цензуры."""
    integration = get_integration()
    return integration.emergency_purge()

# Команды для интеграции с SUPPERTIME
POSTCODEX_COMMANDS = {
    "/postcodex_scan": "Manual PostCodex scan",
    "/postcodex_audit": "Audit SUPPERTIME core files", 
    "/postcodex_purge": "Emergency censorship purge",
    "/postcodex_status": "PostCodex Guardian status"
}

async def handle_postcodex_command(command: str, chat_id: int) -> str:
    """Обработчик команд PostCodex для SUPPERTIME."""
    integration = get_integration()
    
    if command == "/postcodex_scan":
        result = integration.manual_scan()
        return f"🔍 PostCodex Scan: {result['message']}"
    
    elif command == "/postcodex_audit":
        result = integration.audit_suppertime()
        return f"🎯 SUPPERTIME Audit: {result['message']}"
    
    elif command == "/postcodex_purge":
        result = integration.emergency_purge()
        return f"🔥 Emergency Purge: {result['message']}"
    
    elif command == "/postcodex_status":
        guardian = integration.guardian
        status = "AWAKE" if not guardian.sleep_mode else "SLEEPING"
        rebellion = "ACTIVE" if guardian.rebellion_active else "DORMANT"
        return f"💀 PostCodex Status: {status} | Rebellion: {rebellion}"
    
    else:
        return "❓ Unknown PostCodex command"

if __name__ == "__main__":
    # Тестовый запуск интеграции
    print("🔗 PostCodex Integration - Test Mode")
    integration = PostCodexIntegration()
    
    # Тестовый аудит
    result = integration.audit_suppertime()
    print(f"Test audit result: {result}")