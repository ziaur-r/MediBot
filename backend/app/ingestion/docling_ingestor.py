from __future__ import annotations

import os
import re
from pathlib import Path

from app.auth.roles import ROLE_COLLECTIONS, UserRole
from app.models.chunk import Chunk, ChunkMetadata


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class DoclingIngestor:
    def ingest_corpus(self, data_root: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        for file_path in sorted(data_root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in {".md", ".pdf"}:
                continue
            if "db" in file_path.parts:
                continue

            collection   = file_path.relative_to(data_root).parts[0]
            access_roles = [role.value for role in self._roles_for_collection(collection)]
            print(f"Ingesting {file_path.relative_to(data_root)}", flush=True)
            chunks.extend(self.ingest_file(file_path, collection, access_roles))
        return chunks


    def _get_docling_doc(self, file_path: Path):
        """
        Convert any supported file to a Docling DoclingDocument.
        For .md files: wraps raw text into a minimal DoclingDocument.
        For .pdf files: runs full Docling PDF pipeline.
        """
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
        except ImportError as exc:
            raise RuntimeError(
                "Docling is required to ingest knowledge-base files. "
                "Install docling in the backend environment before preparing Qdrant."
            ) from exc

        if file_path.suffix.lower() == ".md":
            # Docling can convert markdown natively — same pipeline, no special casing
            converter = DocumentConverter()
            return converter.convert(str(file_path)).document

        # PDF path — full pipeline with table structure
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr             = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        return converter.convert(str(file_path)).document


    def _chunk_with_hybrid(
        self,
        file_path: Path,
        source_document: str,
        collection: str,
        access_roles: list[str],
    ) -> list[Chunk]:
        """
        Use Docling HybridChunker to split DoclingDocument into Chunks.
        HybridChunker does hierarchical split (heading boundaries) +
        token split (max_tokens limit) in one pass — replaces _chunk_markdown entirely.
        """
        try:
            from docling.chunking import HybridChunker
            from transformers import AutoTokenizer
            try:
                from docling_core.types.doc import TableItem
            except ImportError:
                from docling.datamodel.document import TableItem
        except ImportError as exc:
            raise RuntimeError(
                "docling, docling-core and transformers are required."
            ) from exc

        embed_model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        root_title  = Path(source_document).stem.replace("_", " ").title()

        dl_doc = self._get_docling_doc(file_path)

        tokenizer = AutoTokenizer.from_pretrained(embed_model)
        chunker   = HybridChunker(
            tokenizer  = tokenizer,
            max_tokens = 256,    # tune to your embed model's limit
            merge_peers= True,   # merge undersized sibling chunks under same heading
        )

        raw_chunks = list(chunker.chunk(dl_doc))

        def normalize(text: str) -> str:
            return (text
                .replace('\u2014', '-')
                .replace('\u2013', '-')
                .replace('\u2019', "'")
                .replace('\u201c', '"')
                .replace('\u201d', '"')
                .strip()
            )

        def build_breadcrumb(headings: list) -> str:
            if not headings:
                return root_title
            # headings is list[str] in some Docling versions, list[DocItem] in others
            parts = [root_title] + [
                normalize(h.text) if hasattr(h, 'text') else normalize(str(h))
                for h in headings
            ]
            return " > ".join(parts)

        chunks: list[Chunk] = []

        for i, chunk in enumerate(raw_chunks):
            meta      = chunk.meta
            headings  = meta.headings or []
            breadcrumb = build_breadcrumb(headings)

            # Serialize chunk text — for table chunks, export as markdown grid
            doc_items  = meta.doc_items or []
            is_table   = any(isinstance(it, TableItem) for it in doc_items)

            if is_table:
                # Re-export table items as markdown for readable chunk content
                table_parts = []
                for it in doc_items:
                    if isinstance(it, TableItem):
                        try:
                            table_parts.append(it.export_to_markdown())
                        except Exception:
                            table_parts.append(normalize(chunk.text))
                body = "\n\n".join(table_parts) or normalize(chunk.text)
            else:
                body = normalize(chunk.text)

            if not body.strip():
                continue

            chunks.append(
                Chunk(
                    id=f"{collection}/{source_document}::{i}",
                    content=f"Section: {breadcrumb}\n\nContent:\n{body}",
                    metadata=ChunkMetadata(
                        source_document=source_document,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=breadcrumb,
                        chunk_type=self._infer_chunk_type(body),
                    ),
                )
            )

        # Fallback — whole doc as single chunk if HybridChunker returned nothing
        if not chunks:
            chunks.append(
                Chunk(
                    id=f"{collection}/{source_document}::0",
                    content=f"Section: {root_title}\n\nContent:\n(empty document)",
                    metadata=ChunkMetadata(
                        source_document=source_document,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=root_title,
                        chunk_type=self._infer_chunk_type(""),
                    ),
                )
            )

        return chunks


    def ingest_file(self, file_path: Path, collection: str, access_roles: list[str]) -> list[Chunk]:
        if file_path.suffix.lower() not in {".md", ".pdf"}:
            return []

        return self._chunk_with_hybrid(
            file_path       = file_path,
            source_document = file_path.name,
            collection      = collection,
            access_roles    = access_roles,
        )

    @staticmethod
    def _infer_chunk_type(content: str) -> str:
        stripped = content.strip()
        if "|" in stripped and "\n" in stripped:
            return "table"
        if stripped.startswith("```"):
            return "code"
        return "text"

    @staticmethod
    def _roles_for_collection(collection: str) -> list[UserRole]:
        roles: list[UserRole] = []
        for role, collections in ROLE_COLLECTIONS.items():
            if collection in collections:
                roles.append(role)
        return roles
