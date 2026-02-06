"""REPL execution logger."""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CodeExecution:
    code: str
    stdout: str
    stderr: str
    execution_number: int
    execution_time: Optional[float] = None

class REPLEnvLogger:
    def __init__(self, max_output_length: int = 10000, enabled: bool = True):
        self.enabled = enabled
        self.executions: List[CodeExecution] = []
        self.count = 0
        self.max_len = max_output_length
    
    def log_execution(self, code, stdout, stderr="", exec_time=None):
        self.count += 1
        self.executions.append(CodeExecution(code, stdout, stderr, self.count, exec_time))
    
    def display_last(self):
        if self.enabled and self.executions:
            ex = self.executions[-1]
            print(f"[In {ex.execution_number}]: {ex.code[:300]}...")
            if ex.stdout:
                # Mostra più output per debug
                preview = ex.stdout[:2000] if len(ex.stdout) > 2000 else ex.stdout
                print(f"[Out {ex.execution_number}]: {preview}")
                if len(ex.stdout) > 2000:
                    print(f"  ... ({len(ex.stdout)} chars totali)")
            if ex.stderr:
                print(f"[Err]: {ex.stderr[:500]}")
    
    def clear(self):
        self.executions.clear()
        self.count = 0
