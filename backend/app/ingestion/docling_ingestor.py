from __future__ import annotations

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

            collection = file_path.relative_to(data_root).parts[0]
            access_roles = [role.value for role in self._roles_for_collection(collection)]
            print(f"Ingesting {file_path.relative_to(data_root)}", flush=True)
            chunks.extend(self.ingest_file(file_path, collection, access_roles))
        return chunks

    def ingest_file(self, file_path: Path, collection: str, access_roles: list[str]) -> list[Chunk]:
        if file_path.suffix.lower() == ".md":
            markdown_text = file_path.read_text(encoding="utf-8")
        elif file_path.suffix.lower() == ".pdf":
            markdown_text = self._convert_pdf_to_markdown(file_path)
        else:
            return []

        return self._chunk_markdown(
            markdown_text=markdown_text,
            source_document=file_path.name,
            collection=collection,
            access_roles=access_roles,
        )

    def _convert_pdf_to_markdown(self, file_path: Path) -> str:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "Docling is required to ingest PDF knowledge-base files. "
                "Install docling in the backend environment before preparing Qdrant."
            ) from exc

        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        document = getattr(result, "document", result)
        export_markdown = getattr(document, "export_to_markdown", None)
        if export_markdown is None:
            raise RuntimeError("Docling conversion result does not expose export_to_markdown()")
        return export_markdown()

    def _chunk_markdown(
        self,
        markdown_text: str,
        source_document: str,
        collection: str,
        access_roles: list[str],
    ) -> list[Chunk]:
        root_title = Path(source_document).stem.replace("_", " ").title()
        chunks: list[Chunk] = []
        current_headings: list[str] = [root_title]
        current_lines: list[str] = []
        chunk_index = 0

        def flush_current() -> None:
            nonlocal chunk_index
            body = "\n".join(line for line in current_lines if line.strip()).strip()
            if not body:
                return

            section_title = " > ".join(current_headings)
            chunks.append(
                Chunk(
                    id=f"{collection}/{source_document}::{chunk_index}",
                    content=f"Section: {section_title}\n\nContent:\n{body}",
                    metadata=ChunkMetadata(
                        source_document=source_document,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=section_title,
                        chunk_type=self._infer_chunk_type(body),
                    ),
                )
            )
            chunk_index += 1

        for raw_line in markdown_text.splitlines():
            heading_match = _HEADING_RE.match(raw_line.strip())
            if heading_match:
                flush_current()
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                current_headings = current_headings[:level]
                if len(current_headings) < level:
                    current_headings.extend([root_title] * (level - len(current_headings)))
                current_headings[level - 1 :] = [heading_text]
                current_lines = []
                continue

            current_lines.append(raw_line)
            if len("\n".join(current_lines)) >= 1400:
                flush_current()
                current_lines = []

        flush_current()

        if not chunks:
            section_title = root_title
            chunks.append(
                Chunk(
                    id=f"{collection}/{source_document}::0",
                    content=f"Section: {section_title}\n\nContent:\n{markdown_text.strip()}",
                    metadata=ChunkMetadata(
                        source_document=source_document,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=section_title,
                        chunk_type=self._infer_chunk_type(markdown_text),
                    ),
                )
            )

        return chunks

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
