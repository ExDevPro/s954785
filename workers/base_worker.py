"""
Base worker class for Bulk Email Sender.

This module provides the base worker class for all background operations:
- Thread-safe execution
- Progress reporting
- Cancellation support
- Error handling
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future

from core.utils.logger import get_module_logger
from core.utils.exceptions import WorkerError, WorkerTimeoutError, WorkerCancelledException, handle_exception

logger = get_module_logger(__name__)


class WorkerStatus(Enum):
    """Worker status enumeration."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkerProgress:
    """Worker progress information."""
    current: int = 0
    total: int = 0
    message: str = ""
    percentage: float = 0.0
    estimated_remaining: Optional[float] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        
        # Calculate percentage
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100
        else:
            self.percentage = 0.0


class BaseWorker(ABC):
    """Base class for all worker threads."""
    
    def __init__(self, name: str, timeout: Optional[float] = None):
        """
        Initialize base worker.
        
        Args:
            name: Worker name for identification
            timeout: Optional timeout for worker execution
        """
        self.name = name
        self.timeout = timeout
        
        # Thread management
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.RLock()
        
        # Status and progress
        self._status = WorkerStatus.IDLE
        self._progress = WorkerProgress()
        self._result: Any = None
        self._error: Optional[Exception] = None
        
        # Callbacks
        self._progress_callbacks: List[Callable[[WorkerProgress], None]] = []
        self._status_callbacks: List[Callable[[WorkerStatus], None]] = []
        self._completion_callbacks: List[Callable[[Any, Optional[Exception]], None]] = []
        
        # Timing
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
        # Logger with context
        self._logger = get_module_logger(f"worker.{name}")
    
    @property
    def status(self) -> WorkerStatus:
        """Get current worker status."""
        with self._lock:
            return self._status
    
    @property
    def progress(self) -> WorkerProgress:
        """Get current worker progress."""
        with self._lock:
            return WorkerProgress(
                current=self._progress.current,
                total=self._progress.total,
                message=self._progress.message,
                percentage=self._progress.percentage,
                estimated_remaining=self._progress.estimated_remaining,
                details=self._progress.details.copy()
            )
    
    @property
    def result(self) -> Any:
        """Get worker result (only available after completion)."""
        with self._lock:
            return self._result
    
    @property
    def error(self) -> Optional[Exception]:
        """Get worker error (only available if failed)."""
        with self._lock:
            return self._error
    
    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self.status in [WorkerStatus.STARTING, WorkerStatus.RUNNING, WorkerStatus.PAUSED]
    
    @property
    def is_completed(self) -> bool:
        """Check if worker has completed (successfully or with error)."""
        return self.status in [WorkerStatus.COMPLETED, WorkerStatus.FAILED, WorkerStatus.CANCELLED]
    
    @property
    def duration(self) -> Optional[float]:
        """Get worker execution duration."""
        if self._start_time is None:
            return None
        
        end_time = self._end_time or time.time()
        return end_time - self._start_time
    
    def add_progress_callback(self, callback: Callable[[WorkerProgress], None]) -> None:
        """Add progress update callback."""
        with self._lock:
            self._progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[WorkerStatus], None]) -> None:
        """Add status change callback."""
        with self._lock:
            self._status_callbacks.append(callback)
    
    def add_completion_callback(self, callback: Callable[[Any, Optional[Exception]], None]) -> None:
        """Add completion callback."""
        with self._lock:
            self._completion_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[WorkerProgress], None]) -> None:
        """Remove progress update callback."""
        with self._lock:
            if callback in self._progress_callbacks:
                self._progress_callbacks.remove(callback)
    
    def remove_status_callback(self, callback: Callable[[WorkerStatus], None]) -> None:
        """Remove status change callback."""
        with self._lock:
            if callback in self._status_callbacks:
                self._status_callbacks.remove(callback)
    
    def remove_completion_callback(self, callback: Callable[[Any, Optional[Exception]], None]) -> None:
        """Remove completion callback."""
        with self._lock:
            if callback in self._completion_callbacks:
                self._completion_callbacks.remove(callback)
    
    def start(self, *args, **kwargs) -> None:
        """
        Start worker execution.
        
        Args:
            *args: Arguments to pass to worker
            **kwargs: Keyword arguments to pass to worker
        """
        with self._lock:
            if self.is_running:
                raise WorkerError(f"Worker '{self.name}' is already running")
            
            if self.is_completed:
                # Reset for restart
                self._reset_state()
            
            self._set_status(WorkerStatus.STARTING)
            self._start_time = time.time()
            self._end_time = None
            
            # Start worker thread
            self._thread = threading.Thread(
                target=self._run_worker,
                args=args,
                kwargs=kwargs,
                name=f"Worker-{self.name}",
                daemon=True
            )
            self._thread.start()
            
            self._logger.info(f"Worker '{self.name}' started")
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """
        Stop worker execution.
        
        Args:
            timeout: Timeout for stopping worker
            
        Returns:
            True if stopped successfully, False if timeout
        """
        with self._lock:
            if not self.is_running:
                return True
            
            self._set_status(WorkerStatus.STOPPING)
            self._stop_event.set()
        
        # Wait for worker to stop
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
            
            if self._thread.is_alive():
                self._logger.warning(f"Worker '{self.name}' did not stop within timeout")
                return False
        
        self._logger.info(f"Worker '{self.name}' stopped")
        return True
    
    def pause(self) -> None:
        """Pause worker execution."""
        with self._lock:
            if self.status == WorkerStatus.RUNNING:
                self._set_status(WorkerStatus.PAUSED)
                self._pause_event.set()
                self._logger.info(f"Worker '{self.name}' paused")
    
    def resume(self) -> None:
        """Resume worker execution."""
        with self._lock:
            if self.status == WorkerStatus.PAUSED:
                self._set_status(WorkerStatus.RUNNING)
                self._pause_event.clear()
                self._logger.info(f"Worker '{self.name}' resumed")
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for worker to complete.
        
        Args:
            timeout: Timeout for waiting
            
        Returns:
            True if completed, False if timeout
        """
        if not self._thread:
            return True
        
        self._thread.join(timeout)
        return not self._thread.is_alive()
    
    def _reset_state(self) -> None:
        """Reset worker state for restart."""
        self._stop_event.clear()
        self._pause_event.clear()
        self._progress = WorkerProgress()
        self._result = None
        self._error = None
        self._start_time = None
        self._end_time = None
    
    def _set_status(self, status: WorkerStatus) -> None:
        """Set worker status and notify callbacks."""
        old_status = self._status
        self._status = status
        
        if old_status != status:
            self._logger.debug(f"Worker status changed: {old_status.value} -> {status.value}")
            
            # Call status callbacks
            for callback in self._status_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    self._logger.exception(e, "in status callback")
    
    def _update_progress(self, current: int = None, total: int = None, 
                        message: str = None, details: Dict[str, Any] = None) -> None:
        """Update worker progress and notify callbacks."""
        with self._lock:
            if current is not None:
                self._progress.current = current
            if total is not None:
                self._progress.total = total
            if message is not None:
                self._progress.message = message
            if details is not None:
                self._progress.details.update(details)
            
            # Calculate percentage
            if self._progress.total > 0:
                self._progress.percentage = (self._progress.current / self._progress.total) * 100
            
            # Estimate remaining time
            if self._start_time and self._progress.percentage > 0:
                elapsed = time.time() - self._start_time
                estimated_total = elapsed / (self._progress.percentage / 100)
                self._progress.estimated_remaining = estimated_total - elapsed
            
            # Call progress callbacks
            progress_copy = self.progress
            for callback in self._progress_callbacks:
                try:
                    callback(progress_copy)
                except Exception as e:
                    self._logger.exception(e, "in progress callback")
    
    def _check_cancellation(self) -> None:
        """Check if worker should be cancelled."""
        if self._stop_event.is_set():
            raise WorkerCancelledException(f"Worker '{self.name}' was cancelled")
    
    def _check_pause(self) -> None:
        """Check if worker should be paused."""
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(0.1)
        
        # Check cancellation after pause
        self._check_cancellation()
    
    def _run_worker(self, *args, **kwargs) -> None:
        """Internal worker execution wrapper."""
        try:
            self._set_status(WorkerStatus.RUNNING)
            
            # Check timeout
            start_time = time.time()
            
            # Execute worker implementation
            result = self._execute(*args, **kwargs)
            
            # Check timeout
            if self.timeout and (time.time() - start_time) > self.timeout:
                raise WorkerTimeoutError(f"Worker '{self.name}' exceeded timeout of {self.timeout} seconds")
            
            # Success
            with self._lock:
                self._result = result
                self._end_time = time.time()
            
            self._set_status(WorkerStatus.COMPLETED)
            self._logger.info(f"Worker '{self.name}' completed successfully")
            
            # Call completion callbacks
            for callback in self._completion_callbacks:
                try:
                    callback(result, None)
                except Exception as e:
                    self._logger.exception(e, "in completion callback")
        
        except WorkerCancelledException as e:
            with self._lock:
                self._error = e
                self._end_time = time.time()
            
            self._set_status(WorkerStatus.CANCELLED)
            self._logger.info(f"Worker '{self.name}' was cancelled")
            
            # Call completion callbacks
            for callback in self._completion_callbacks:
                try:
                    callback(None, e)
                except Exception as e:
                    self._logger.exception(e, "in completion callback")
        
        except Exception as e:
            # Handle unexpected errors
            handled_error = handle_exception(e, {'worker': self.name})
            
            with self._lock:
                self._error = handled_error
                self._end_time = time.time()
            
            self._set_status(WorkerStatus.FAILED)
            self._logger.error(f"Worker '{self.name}' failed: {handled_error.message}")
            self._logger.exception(handled_error, f"in worker {self.name}")
            
            # Call completion callbacks
            for callback in self._completion_callbacks:
                try:
                    callback(None, handled_error)
                except Exception as e:
                    self._logger.exception(e, "in completion callback")
    
    @abstractmethod
    def _execute(self, *args, **kwargs) -> Any:
        """
        Execute worker implementation.
        
        This method must be implemented by subclasses.
        
        Args:
            *args: Arguments passed to worker
            **kwargs: Keyword arguments passed to worker
            
        Returns:
            Worker result
            
        Raises:
            Any exceptions should be handled by the base class
        """
        pass


class WorkerPool:
    """Manages multiple workers with resource limits."""
    
    def __init__(self, max_workers: int = 4, name: str = "WorkerPool"):
        """
        Initialize worker pool.
        
        Args:
            max_workers: Maximum number of concurrent workers
            name: Pool name for identification
        """
        self.name = name
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"{name}-Worker")
        self._futures: Dict[str, Future] = {}
        self._workers: Dict[str, BaseWorker] = {}
        self._lock = threading.RLock()
        
        self._logger = get_module_logger(f"pool.{name}")
    
    def submit_worker(self, worker: BaseWorker, *args, **kwargs) -> str:
        """
        Submit worker to pool.
        
        Args:
            worker: Worker instance to execute
            *args: Arguments to pass to worker
            **kwargs: Keyword arguments to pass to worker
            
        Returns:
            Worker ID for tracking
            
        Raises:
            WorkerError: If pool is full or worker cannot be submitted
        """
        with self._lock:
            worker_id = f"{worker.name}-{len(self._futures)}"
            
            if len(self._futures) >= self.max_workers:
                raise WorkerError(f"Worker pool '{self.name}' is full (max {self.max_workers} workers)")
            
            # Submit worker to executor
            future = self._executor.submit(worker._run_worker, *args, **kwargs)
            
            self._futures[worker_id] = future
            self._workers[worker_id] = worker
            
            self._logger.info(f"Submitted worker '{worker.name}' to pool (ID: {worker_id})")
            return worker_id
    
    def get_worker(self, worker_id: str) -> Optional[BaseWorker]:
        """Get worker by ID."""
        with self._lock:
            return self._workers.get(worker_id)
    
    def cancel_worker(self, worker_id: str, timeout: Optional[float] = None) -> bool:
        """
        Cancel a specific worker.
        
        Args:
            worker_id: Worker ID to cancel
            timeout: Timeout for cancellation
            
        Returns:
            True if cancelled successfully
        """
        with self._lock:
            if worker_id not in self._workers:
                return False
            
            worker = self._workers[worker_id]
            future = self._futures[worker_id]
            
            # Try to cancel future
            if future.cancel():
                self._logger.info(f"Cancelled worker '{worker_id}' (future cancelled)")
                return True
            
            # If future is running, stop worker
            success = worker.stop(timeout)
            if success:
                self._logger.info(f"Cancelled worker '{worker_id}' (worker stopped)")
            else:
                self._logger.warning(f"Failed to cancel worker '{worker_id}' within timeout")
            
            return success
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all workers to complete.
        
        Args:
            timeout: Timeout for waiting
            
        Returns:
            True if all completed, False if timeout
        """
        with self._lock:
            futures = list(self._futures.values())
        
        try:
            from concurrent.futures import wait, ALL_COMPLETED
            done, not_done = wait(futures, timeout=timeout, return_when=ALL_COMPLETED)
            return len(not_done) == 0
        except Exception as e:
            self._logger.exception(e, "waiting for worker completion")
            return False
    
    def get_active_workers(self) -> List[str]:
        """Get list of active worker IDs."""
        with self._lock:
            active = []
            for worker_id, worker in self._workers.items():
                if worker.is_running:
                    active.append(worker_id)
            return active
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            total_workers = len(self._workers)
            active_workers = len(self.get_active_workers())
            completed_workers = sum(1 for w in self._workers.values() if w.is_completed)
            
            return {
                'total_workers': total_workers,
                'active_workers': active_workers,
                'completed_workers': completed_workers,
                'max_workers': self.max_workers,
                'pool_utilization': (active_workers / self.max_workers) * 100 if self.max_workers > 0 else 0
            }
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> None:
        """
        Shutdown worker pool.
        
        Args:
            wait: Whether to wait for running workers to complete
            timeout: Timeout for shutdown
        """
        self._logger.info(f"Shutting down worker pool '{self.name}'")
        
        # Cancel all active workers
        with self._lock:
            active_worker_ids = self.get_active_workers()
        
        for worker_id in active_worker_ids:
            self.cancel_worker(worker_id, timeout=5.0)
        
        # Shutdown executor
        self._executor.shutdown(wait=wait, timeout=timeout)
        
        self._logger.info(f"Worker pool '{self.name}' shutdown complete")