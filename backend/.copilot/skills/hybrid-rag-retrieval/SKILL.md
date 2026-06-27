---
name: hybrid-rag-retrieval
description: guide to use hybrid rag retrieval skill based on below code snippets
---

To use the hybrid RAG retrieval skill, follow this process, using the code snippets provided:
1. Create a hybrid retriever using both dense and sparse embeddings using the approach in below code snippet.
2. Avoid any fallbacks as code to reduce code size.
3. Make sure to apply reranking using cross-encoder to improve the quality of retrieved documents.
4. Use the `ContextualCompressionRetriever` to filter and compress the initial output of the base retriever, so that only the most relevant information is returned.
5. Finally, create a retrieval chain that combines the hybrid retriever and the reranking retriever to get the best results.
6. You can also use the Qdrant client to filter results based on specific metadata fields, as shown in the last code snippet.
7. Make sure to adjust the parameters such as `k` for the number of documents to retrieve and `top_n` for the number of documents to keep after reranking, based on your specific use case and performance requirements.
8. The code snippets provided are designed to be run in a Python environment with the necessary libraries installed, including LangChain, HuggingFace, and Qdrant.


--code snippet--

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse

# Dense embeddings — semantic understanding
dense_embeddings = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},      # change to "cuda" if you have a GPU
    encode_kwargs={"normalize_embeddings": True}
)

# Sparse embeddings — BM25 keyword matching (via FastEmbed)
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)

print("Dense embedding model:", EMBED_MODEL)
print("Sparse embedding model: Qdrant/BM25")

from langchain_qdrant import QdrantVectorStore, RetrievalMode

# RetrievalMode.HYBRID stores BOTH dense and sparse vectors
vectorstore = QdrantVectorStore.from_documents(
    documents=all_docs,
    embedding=dense_embeddings,
    sparse_embedding=sparse_embeddings,
    path="/tmp/my_lang_vs",
    collection_name=COLLECTION_NAME,
    retrieval_mode=RetrievalMode.HYBRID,
)

from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# Create a retriever in HYBRID mode
hybrid_retriever = vectorstore.as_retriever(
    search_kwargs={"k": 5}       # retrieve top-5 docs
)

# Build the chain
question_answer_chain = create_stuff_documents_chain(llm, prompt)
hybrid_rag_chain = create_retrieval_chain(hybrid_retriever, question_answer_chain)

# Re-ranking
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

# Load cross-encoder model (downloads ~270MB on first run)
cross_encoder = HuggingFaceCrossEncoder(
    model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# Wrap it as a LangChain document compressor
reranker = CrossEncoderReranker(
    model=cross_encoder,
    top_n=3           # keep only top-3 after reranking
)

print("✅ Cross-encoder reranker ready")
print("Model: cross-encoder/ms-marco-MiniLM-L-6-v2")

"""First, a broad retriever: fetch more candidates for the reranker to work with.

The `ContextualCompressionsRetriever` is a wrapper for another retriever that iterates over the initial output of the base retriever and filters and compresses those initial documents, so that only the most relevant information is returned.
"""

broad_retriever = vectorstore.as_retriever(
    search_kwargs={"k": 10}    # fetch 10, rerank down to 3
)

reranking_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=broad_retriever
)

print("Retrieval pipeline:")
print("  1. Hybrid search → Top-10 candidates")
print("  2. Cross-encoder reranker → Top-3 best documents")

"""Create the retrieval chain."""

reranking_rag_chain = create_retrieval_chain(
    reranking_retriever,
    create_stuff_documents_chain(llm, prompt)
)

print("✅ Hybrid RAG + Reranking chain ready")

"""Let's see what the cross-encoder scores look like directly"""

query = "How do I check my data balance?"
candidates = broad_retriever.invoke(query)

print(f"Retrieved {len(candidates)} candidates. Now scoring each with cross-encoder...\n")

pairs = [[query, doc.page_content] for doc in candidates]
scores = cross_encoder.score(pairs)

scored = sorted(zip(scores, candidates), reverse=True)

for rank, (score, doc) in enumerate(scored, 1):
    cat = doc.metadata.get("category", "")
    print(f"Rank {rank}  score={score:.4f}  category={cat}")
    print(f"  {doc.page_content[:100]}...")
    print()

# Filterps with quadrant
client = QdrantClient(path="/tmp/my_qdrant")
results = client.query_points(
    collection_name="my_collection",
    query=model.encode("astronomy and stars").tolist(),
    query_filter=Filter(
        must=[
            FieldCondition(key="category", match=MatchValue(value="science")),
            FieldCondition(key="role",     match=MatchValue(value="public"))
        ]
    ),
    limit=5
)
for r in results.points:
    print(f"Score: {r.score:.4f} | {r.payload['text'][:60]}")