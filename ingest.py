import os
import json
import argparse
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Load environment variables from .env
load_dotenv()

def get_embeddings(force_local=False):
    """
    Get embedding model. If OPENAI_API_KEY is available and not a placeholder,
    uses OpenAI text-embedding-3-small. Otherwise, falls back to a lightweight, 
    free local HuggingFace model.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if force_local or not openai_key or openai_key == "your_openai_api_key_here":
        print("\n--> [Config] Using FREE local HuggingFace Embeddings ('all-MiniLM-L6-v2')...")
        print("    (Note: The model will be downloaded automatically if not present locally.)")
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    else:
        print("\n--> [Config] Using OpenAI Embeddings (text-embedding-3-small)...")
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")

def main():
    parser = argparse.ArgumentParser(description="Ingest Bhashini API documentation segments into Chroma DB.")
    parser.parse_args()

    segments_path = os.path.join("docs", "bhashini_segments.json")
    if not os.path.exists(segments_path):
        print(f"Error: {segments_path} not found. Please run segment_chunks.py or check the docs directory.")
        return

    print(f"Loading document segments from: {segments_path}")
    with open(segments_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    # Convert segments to LangChain Document objects
    documents = []
    for idx, segment in enumerate(segments):
        metadata = {
            "source": ", ".join(segment["metadata"]["pages_used"]),
            "topic": segment["metadata"]["document_topic"],
            "segment_name": segment["segment_name"],
            "segment_id": segment["id"]
        }
        doc = Document(page_content=segment["text"], metadata=metadata)
        documents.append(doc)

    print(f"Loaded {len(documents)} document segments.")

    # Split documents into chunks for more precise retrieval
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True
    )
    splits = text_splitter.split_documents(documents)
    print(f"Created {len(splits)} chunks from the documents.")

    # Select embedding model
    embeddings = get_embeddings()

    # Create and persist Vector Store
    db_dir = "./chroma_db"
    print(f"Indexing chunks and saving Chroma DB to: {db_dir}...")
    
    # Initialize Chroma Vectorstore and persist it
    db = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=db_dir
    )
    
    print("\n[SUCCESS] Ingestion completed. Vector database is ready at ./chroma_db!")

if __name__ == "__main__":
    main()
