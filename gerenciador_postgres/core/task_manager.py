"""
Gerenciador de tarefas assíncronas com PyQt6
"""
from typing import Callable, Any, Optional
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QThreadPool, QRunnable
import traceback
from .logging import get_logger

logger = get_logger(__name__)

class TaskSignals(QObject):
    """Sinais para comunicação entre threads"""
    result = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(int)
    finished = pyqtSignal()

class AsyncWorker(QRunnable):
    """Worker para executar tarefas em background"""
    
    def __init__(self, task: Callable, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        
    def run(self):
        """Executa a tarefa"""
        try:
            logger.debug(f"Iniciando tarefa: {self.task.__name__}")
            result = self.task(*self.args, **self.kwargs)
            self.signals.result.emit(result)
            logger.debug(f"Tarefa concluída: {self.task.__name__}")
        except Exception as e:
            logger.error(f"Erro na tarefa {self.task.__name__}: {e}")
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class ProgressWorker(QRunnable):
    """Worker que suporta progresso"""
    
    def __init__(self, task: Callable, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        
    def run(self):
        """Executa a tarefa com callback de progresso"""
        try:
            def progress_callback(value: int):
                self.signals.progress.emit(value)
                
            logger.debug(f"Iniciando tarefa com progresso: {self.task.__name__}")
            result = self.task(progress_callback, *self.args, **self.kwargs)
            self.signals.result.emit(result)
            logger.debug(f"Tarefa com progresso concluída: {self.task.__name__}")
        except Exception as e:
            logger.error(f"Erro na tarefa {self.task.__name__}: {e}")
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class TaskManager:
    """
    Gerenciador central de tarefas assíncronas
    """
    
    def __init__(self):
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)  # Máximo de 4 threads simultâneas
        
    def run_async(self, 
                  task: Callable, 
                  on_success: Optional[Callable] = None,
                  on_error: Optional[Callable] = None,
                  on_finished: Optional[Callable] = None,
                  *args, **kwargs) -> AsyncWorker:
        """
        Executa tarefa em background
        
        Args:
            task: Função a ser executada
            on_success: Callback para sucesso (recebe resultado)
            on_error: Callback para erro (recebe exception)
            on_finished: Callback para finalização (sempre chamado)
        """
        worker = AsyncWorker(task, *args, **kwargs)
        
        if on_success:
            worker.signals.result.connect(on_success)
        if on_error:
            worker.signals.error.connect(on_error)
        if on_finished:
            worker.signals.finished.connect(on_finished)
            
        self.thread_pool.start(worker)
        return worker
        
    def run_with_progress(self,
                         task: Callable,
                         on_success: Optional[Callable] = None,
                         on_error: Optional[Callable] = None,
                         on_progress: Optional[Callable] = None,
                         on_finished: Optional[Callable] = None,
                         *args, **kwargs) -> ProgressWorker:
        """
        Executa tarefa com progresso
        
        Args:
            task: Função a ser executada (primeiro parâmetro deve ser progress_callback)
            on_success: Callback para sucesso
            on_error: Callback para erro
            on_progress: Callback para progresso (recebe int 0-100)
            on_finished: Callback para finalização
        """
        worker = ProgressWorker(task, *args, **kwargs)
        
        if on_success:
            worker.signals.result.connect(on_success)
        if on_error:
            worker.signals.error.connect(on_error)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_finished:
            worker.signals.finished.connect(on_finished)
            
        self.thread_pool.start(worker)
        return worker
        
    def wait_for_done(self, timeout_ms: int = 30000) -> bool:
        """Aguarda todas as tarefas terminarem"""
        return self.thread_pool.waitForDone(timeout_ms)
        
    def active_thread_count(self) -> int:
        """Retorna número de threads ativas"""
        return self.thread_pool.activeThreadCount()

# Singleton instance
_task_manager_instance = None

def get_task_manager() -> TaskManager:
    """Retorna a instância singleton do task manager"""
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = TaskManager()
    return _task_manager_instance
