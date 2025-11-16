"""
Batch Processing Module
Handles batch processing of multiple requests for OpenAI API.
Supports efficient batch operations and request queuing.
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class BatchRequest:
    """
    Represents a single request in a batch.
    
    Attributes:
        id: Unique request identifier
        data: Request data
        callback: Optional callback function for result
        timestamp: When the request was created
    """
    id: str
    data: Dict[str, Any]
    callback: Optional[Callable] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BatchProcessor:
    """
    Processes multiple requests in batches for efficiency.
    Supports configurable batch size and timeout.
    """
    
    def __init__(
        self,
        batch_size: int = 10,
        timeout: float = 30.0,
        max_workers: int = 4
    ):
        """
        Initialize BatchProcessor.
        
        Args:
            batch_size: Maximum number of requests per batch
            timeout: Timeout in seconds for batch processing
            max_workers: Maximum number of worker threads
        """
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_workers = max_workers
        self.pending_requests: List[BatchRequest] = []
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def add_request(
        self,
        request_id: str,
        data: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> None:
        """
        Add a request to the batch queue.
        
        Args:
            request_id: Unique request identifier
            data: Request data
            callback: Optional callback function for result
        """
        request = BatchRequest(
            id=request_id,
            data=data,
            callback=callback
        )
        self.pending_requests.append(request)
    
    def process_batch(
        self,
        processor_func: Callable[[Dict[str, Any]], Any]
    ) -> List[Dict[str, Any]]:
        """
        Process all pending requests in batches.
        
        Args:
            processor_func: Function to process each request
            
        Returns:
            List of results for all requests
        """
        if not self.pending_requests:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Split requests into batches
        batches = [
            self.pending_requests[i:i + self.batch_size]
            for i in range(0, len(self.pending_requests), self.batch_size)
        ]
        
        # Process each batch
        for batch in batches:
            batch_results = self._process_single_batch(batch, processor_func)
            results.extend(batch_results)
        
        # Clear pending requests
        self.pending_requests.clear()
        
        return results
    
    def _process_single_batch(
        self,
        batch: List[BatchRequest],
        processor_func: Callable[[Dict[str, Any]], Any]
    ) -> List[Dict[str, Any]]:
        """
        Process a single batch of requests.
        
        Args:
            batch: List of batch requests
            processor_func: Function to process each request
            
        Returns:
            List of results
        """
        results: List[Dict[str, Any]] = []
        futures = []
        
        # Submit all requests in batch
        for request in batch:
            future = self.executor.submit(processor_func, request.data)
            futures.append((request, future))
        
        # Collect results
        for request, future in futures:
            try:
                result = future.result(timeout=self.timeout)
                result_data = {
                    "id": request.id,
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Call callback if provided
                if request.callback:
                    try:
                        request.callback(result_data)
                    except Exception as e:
                        print(f"Error in callback for request {request.id}: {e}")
                
                results.append(result_data)
            except Exception as e:
                error_data = {
                    "id": request.id,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                results.append(error_data)
        
        return results
    
    def clear_pending(self) -> None:
        """Clear all pending requests."""
        self.pending_requests.clear()
    
    def get_pending_count(self) -> int:
        """Get number of pending requests."""
        return len(self.pending_requests)
    
    def shutdown(self) -> None:
        """Shutdown the batch processor and executor."""
        self.executor.shutdown(wait=True)

