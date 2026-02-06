"""Colorful logger for RLM."""
from typing import List, Dict
from datetime import datetime

class ColorfulLogger:
    COLORS = {'RESET': '\033[0m', 'BOLD': '\033[1m', 'GREEN': '\033[32m', 'YELLOW': '\033[33m', 'BLUE': '\033[34m', 'CYAN': '\033[36m'}
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.step = 0
        
    def _c(self, text, color):
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}" if self.enabled else text
    
    def log_query_start(self, query):
        if self.enabled:
            print(self._c("="*60, "GREEN"))
            print(self._c(f"QUERY: {query}", "BOLD"))
            self.step = 0
    
    def log_initial_messages(self, messages):
        if self.enabled:
            print(f"System prompt loaded ({len(messages)} messages)")
    
    def log_model_response(self, response, has_tool_calls):
        if self.enabled:
            self.step += 1
            status = "🔧 Code" if has_tool_calls else "💬 Text"
            print(self._c(f"[Step {self.step}] {status}: {response[:200]}...", "CYAN"))
    
    def log_tool_execution(self, tool, result):
        if self.enabled:
            print(self._c(f"  → {tool}: {result[:150]}...", "YELLOW"))
    
    def log_final_response(self, response):
        if self.enabled:
            print(self._c("="*80, "GREEN"))
            print(self._c("FINAL RESPONSE:", "BOLD"))
            print(self._c("="*80, "GREEN"))
            # NON troncare - mostra tutto
            print(response)
            print(self._c("="*80, "GREEN"))
