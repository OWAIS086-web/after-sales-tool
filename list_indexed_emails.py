"""List all indexed Gmail emails from vector store"""
from ai.email.email_vector_store import EmailVectorStore

store = EmailVectorStore()
all_docs = store.vector_store.collection.get()

print(f'\n=== TOTAL INDEXED EMAILS: {len(all_docs["ids"])} ===\n')

for i, (doc_id, metadata, document) in enumerate(zip(all_docs['ids'], all_docs['metadatas'], all_docs['documents'])):
    sender = metadata.get('sender_name', 'Unknown')
    sender_email = metadata.get('sender_email', 'N/A')
    date = metadata.get('date', 'N/A')
    subject = metadata.get('subject', 'No Subject')[:60]
    email_id = metadata.get('email_id', 'N/A')
    thread_id = metadata.get('thread_id', 'N/A')
    gmail_link = metadata.get('gmail_link', 'N/A')
    
    print(f'{i+1}. [{date}] From: {sender} <{sender_email}>')
    print(f'   Subject: {subject}')
    print(f'   Email ID: {email_id}')
    print(f'   Gmail Link: {gmail_link}')
    print()
