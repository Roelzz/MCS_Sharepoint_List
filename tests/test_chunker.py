import pytest
from src.pipeline.chunker import Chunker

def test_no_chunking_needed():
    chunker = Chunker(chunk_size=10, overlap=2, threshold=20)
    text = "Short text"
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert "Short text" in chunks[0]

def test_chunking_with_metadata():
    chunker = Chunker(chunk_size=10, overlap=2, threshold=5) # Small threshold to force chunking
    text = "This is a longer text that should be chunked"
    metadata = "Title: Test"
    
    # Mock tokenizer to return simple length for predictability if possible, 
    # but we are using tiktoken. Let's trust the logic structure.
    # Just ensure multiple chunks returned.
    
    chunks = chunker.chunk_text(text, metadata)
    assert len(chunks) > 1
    assert all(metadata in c for c in chunks)
    
def test_metadata_too_long():
    chunker = Chunker(chunk_size=5, overlap=0, threshold=1) # Threshold 1 forces chunking
    text = "Content"
    metadata = "Metadata is way too long for chunk size " * 10 # Force it to be long
    
    with pytest.raises(ValueError):
        chunker.chunk_text(text, metadata)
