"""Infrastructure ingestion package."""

from src.infrastructure.ingestion.document_loader import load_and_chunk
from src.infrastructure.ingestion.table_title_linker import link_tables_to_titles

__all__ = ["load_and_chunk", "link_tables_to_titles"]
