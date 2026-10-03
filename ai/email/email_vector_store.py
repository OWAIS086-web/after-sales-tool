"""
Email Vector Store
Specialized vector store for email documents with duplicate detection
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# LangChain Document import - handle different versions
try:
    from langchain_core.documents import Document
except ImportError:
    try:
        from langchain.docstore.document import Document
    except ImportError:
        from langchain.schema import Document

from ai.embeddings import BaseEmbedder, SentenceTransformerEmbedder
from ai.vector_store import ChromaVectorStore
from utils.logger import log_error


class EmailVectorStore:
    """
    Vector store specialized for email documents
    Extends ChromaVectorStore with email-specific features
    """
    
    def __init__(
        self,
        persist_path: str = "data/email_vector_store",
        collection_name: str = "email_documents",
        embedder: Optional[BaseEmbedder] = None
    ):
        """
        Initialize Email Vector Store
        
        Args:
            persist_path: Path to persist vector store
            collection_name: Name of the collection
            embedder: Embedder instance (defaults to SentenceTransformer)
        """
        self.persist_path = persist_path
        self.collection_name = collection_name
        
        print(f"[Email Vector Store] Initializing with persist_path={persist_path}, collection_name={collection_name}")
        
        # Ensure directory exists
        os.makedirs(persist_path, exist_ok=True)
        
        # Initialize embedder
        if embedder is None:
            self.embedder = SentenceTransformerEmbedder()
        else:
            self.embedder = embedder
        
        # Initialize vector store
        self.vector_store = ChromaVectorStore(
            persist_path=persist_path,
            collection_name=collection_name,
            embedder=self.embedder
        )
        
        print(f"[Email Vector Store] Collection name from vector_store: {self.vector_store.collection.name}")
        print(f"[Email Vector Store] Collection count: {self.vector_store.collection.count()}")
        
        # Track indexed email IDs in memory (loaded from metadata)
        self._indexed_email_ids: Set[str] = self._load_indexed_ids()
    
    def _load_indexed_ids(self) -> Set[str]:
        """
        Load indexed email IDs from vector store metadata
        
        Returns:
            Set of indexed email IDs
        """
        try:
            # Query all documents to get their email IDs
            all_docs = self.vector_store.collection.get()
            
            if not all_docs or 'metadatas' not in all_docs:
                return set()
            
            email_ids = set()
            for metadata in all_docs['metadatas']:
                if metadata and 'email_id' in metadata:
                    email_ids.add(metadata['email_id'])
            
            print(f"[Email Vector Store] Loaded {len(email_ids)} indexed email IDs")
            return email_ids
            
        except Exception as e:
            log_error(f"Error loading indexed IDs: {e}")
            return set()
    
    def is_indexed(self, email_id: str) -> bool:
        """
        Check if email is already indexed
        
        Args:
            email_id: Gmail message ID
            
        Returns:
            True if indexed, False otherwise
        """
        return email_id in self._indexed_email_ids
    
    def add_documents(
        self,
        documents: List[Document],
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Add email documents to vector store
        
        Args:
            documents: List of Langchain Document objects
            skip_duplicates: Skip already indexed emails
            
        Returns:
            Dictionary with indexing results
        """
        try:
            if not documents:
                return {
                    'success': True,
                    'total': 0,
                    'indexed': 0,
                    'skipped': 0,
                    'message': 'No documents to index'
                }
            
            # Filter duplicates if needed
            docs_to_index = []
            skipped_count = 0
            
            for doc in documents:
                email_id = doc.metadata.get('email_id')
                
                if skip_duplicates and email_id and self.is_indexed(email_id):
                    skipped_count += 1
                    continue
                
                docs_to_index.append(doc)
            
            # Index documents
            indexed_count = 0
            if docs_to_index:
                # Extract texts and metadatas
                texts = [doc.page_content for doc in docs_to_index]
                metadatas = [doc.metadata for doc in docs_to_index]
                
                # Generate embeddings
                embeddings = self.embedder.embed(texts)
                
                # Generate IDs
                ids = [f"email_{doc.metadata.get('email_id', i)}" for i, doc in enumerate(docs_to_index)]
                
                # Add to collection
                self.vector_store.collection.add(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                
                # Update indexed IDs
                for doc in docs_to_index:
                    email_id = doc.metadata.get('email_id')
                    if email_id:
                        self._indexed_email_ids.add(email_id)
                
                indexed_count = len(docs_to_index)
                print(f"[Email Vector Store] Indexed {indexed_count} emails, skipped {skipped_count} duplicates")
            
            return {
                'success': True,
                'total': len(documents),
                'indexed': indexed_count,
                'skipped': skipped_count,
                'message': f'Successfully indexed {indexed_count} emails'
            }
            
        except Exception as e:
            error_msg = f"Error adding documents: {e}"
            log_error(error_msg)
            return {
                'success': False,
                'total': len(documents),
                'indexed': 0,
                'skipped': 0,
                'error': str(e),
                'message': error_msg
            }
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant emails
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filters (e.g., sender, date range)
            
        Returns:
            List of search results with documents and scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed([query])[0]
            
            # Build where filter from metadata
            where_filter = None
            if filter_metadata:
                where_filter = {}
                for key, value in filter_metadata.items():
                    where_filter[key] = value
            
            # Query collection
            print(f"[Email Vector Store] Querying collection: {self.vector_store.collection.name}")
            print(f"[Email Vector Store] Collection count before query: {self.vector_store.collection.count()}")
            
            results = self.vector_store.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter if where_filter else None
            )
            
            print(f"[Email Vector Store] Query returned {len(results.get('documents', [[]])[0])} results")
            
            # Debug: Print first result metadata to verify source
            if results and 'metadatas' in results and results['metadatas'][0]:
                first_meta = results['metadatas'][0][0]
                print(f"[Email Vector Store] First result metadata: source={first_meta.get('source')}, email_id={first_meta.get('email_id')}, subject={first_meta.get('subject', 'N/A')[:50]}")
            
            # Format results
            formatted_results = []
            if results and 'documents' in results:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'document': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if 'metadatas' in results else {},
                        'distance': results['distances'][0][i] if 'distances' in results else 0.0,
                        'id': results['ids'][0][i] if 'ids' in results else None
                    })
            
            return formatted_results
            
        except Exception as e:
            log_error(f"Error searching: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            total_count = self.vector_store.collection.count()
            
            return {
                'total_indexed': total_count,
                'unique_emails': len(self._indexed_email_ids),
                'collection_name': self.collection_name,
                'persist_path': self.persist_path
            }
            
        except Exception as e:
            log_error(f"Error getting stats: {e}")
            return {
                'total_indexed': 0,
                'unique_emails': 0,
                'collection_name': self.collection_name,
                'persist_path': self.persist_path
            }
    
    def clear(self) -> bool:
        """
        Clear all documents from vector store
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete collection
            self.vector_store.client.delete_collection(self.collection_name)
            
            # Recreate empty collection
            self.vector_store.collection = self.vector_store.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            # Clear indexed IDs
            self._indexed_email_ids.clear()
            
            print(f"[Email Vector Store] Cleared collection: {self.collection_name}")
            return True
            
        except Exception as e:
            log_error(f"Error clearing vector store: {e}")
            return False
    
    def delete_by_email_id(self, email_id: str) -> bool:
        """
        Delete specific email from vector store
        
        Args:
            email_id: Gmail message ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete from collection
            self.vector_store.collection.delete(
                where={"email_id": email_id}
            )
            
            # Remove from indexed IDs
            self._indexed_email_ids.discard(email_id)
            
            print(f"[Email Vector Store] Deleted email: {email_id}")
            return True
            
        except Exception as e:
            log_error(f"Error deleting email: {e}")
            return False
    
    def get_indexed_email_ids(self) -> List[str]:
        """
        Get list of all indexed email IDs
        
        Returns:
            List of email IDs
        """
        return list(self._indexed_email_ids)
