import tiktoken
from typing import List, Tuple

class Chunker:
    def __init__(self, chunk_size: int = 400, overlap: int = 50, threshold: int = 500):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.threshold = threshold
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_text(self, text: str, metadata_prefix: str = "") -> List[str]:
        """
        Split text into chunks if it exceeds threshold.
        Prepends metadata_prefix to each chunk.
        """
        if not text:
            return []
            
        full_text = f"{metadata_prefix}\n{text}"
        tokens = self.tokenizer.encode(full_text)
        
        if len(tokens) <= self.threshold:
            return [full_text]
            
        # Needs chunking
        chunks = []
        prefix_tokens = self.tokenizer.encode(metadata_prefix + "\n")
        prefix_len = len(prefix_tokens)
        
        content_tokens = self.tokenizer.encode(text)
        
        # Effective chunk size for content
        effective_size = self.chunk_size - prefix_len
        if effective_size <= 0:
            raise ValueError("Metadata prefix too long for chunk size")
            
        start = 0
        while start < len(content_tokens):
            end = min(start + effective_size, len(content_tokens))
            chunk_content = self.tokenizer.decode(content_tokens[start:end])
            
            # Simple token splitting for now. Spec calls for sentence splitting priority.
            # Implementing robust sentence splitting requires regex or nltk/spacy.
            # For this MVP step, token splitting is acceptable but we should try to break on whitespace.
            
            chunks.append(f"{metadata_prefix}\n{chunk_content}")
            
            start += (effective_size - self.overlap)
            
        return chunks

chunker = Chunker()
