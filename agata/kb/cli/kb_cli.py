"""
Knowledge Base CLI - Commands for syncing and managing knowledge base
"""
import click
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Load .env file if exists
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from agata.kb.services.mbox_parser import MboxParserService
from agata.kb.services.embedding_service import EmbeddingService
from agata.kb.services.vector_store import VectorStore
from agata.kb.services.parsers.text_parser import TextFileParserService
from agata.kb.services.parsers.markdown_parser import MarkdownParserService


@click.group()
def kb():
    """Knowledge Base management commands"""
    pass


@kb.command('parse-mbox')
@click.option(
    '--mbox-file',
    type=click.Path(exists=True),
    help='Single MBOX file to parse'
)
@click.option(
    '--mbox-dir',
    type=click.Path(exists=True, file_okay=False),
    help='Directory containing multiple MBOX files'
)
@click.option(
    '--label',
    default=None,
    help='Label/category for emails (e.g., INBOX, Sent, Important)'
)
@click.option(
    '--output-dir',
    default='/var/www/astrogen/kb_data/gmail_parsed',
    help='Output directory for parsed emails'
)
def parse_mbox(mbox_file, mbox_dir, label, output_dir):
    """
    Parse MBOX file(s) from Google Takeout and extract emails

    Examples:
        # Parse single MBOX file
        python -m agata.kb.cli.kb_cli parse-mbox --mbox-file=/path/to/Inbox.mbox --label=INBOX

        # Parse all MBOX files in directory
        python -m agata.kb.cli.kb_cli parse-mbox --mbox-dir=/path/to/mbox_files/
    """
    if not mbox_file and not mbox_dir:
        click.echo("Error: Must provide either --mbox-file or --mbox-dir", err=True)
        sys.exit(1)

    if mbox_file and mbox_dir:
        click.echo("Error: Cannot use both --mbox-file and --mbox-dir simultaneously", err=True)
        sys.exit(1)

    try:
        parser = MboxParserService(output_dir=output_dir)

        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - MBOX Parser")
        click.echo("=" * 60)

        if mbox_file:
            # Parse single file
            click.echo(f"\nParsing single MBOX file: {mbox_file}")
            stats = parser.parse_mbox_file(mbox_file, label=label)
        else:
            # Parse directory
            click.echo(f"\nParsing all MBOX files in: {mbox_dir}")
            stats = parser.parse_multiple_mbox_files(mbox_dir)

        # Display results
        click.echo("\n" + "=" * 60)
        click.echo("PARSING RESULTS")
        click.echo("=" * 60)

        if 'files_processed' in stats:
            click.echo(f"Files processed: {stats['files_processed']}")
        click.echo(f"Total messages: {stats['total_messages']}")
        click.echo(f"Successfully parsed: {stats['parsed_successfully']}")
        click.echo(f"Skipped (duplicates): {stats['skipped_duplicates']}")
        click.echo(f"Errors: {stats['errors']}")

        # Get overall summary
        summary = parser.get_indexed_emails_summary()
        click.echo("\n" + "=" * 60)
        click.echo("KNOWLEDGE BASE SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Total emails indexed: {summary['total_emails']}")
        click.echo(f"Last updated: {summary['last_updated']}")

        if summary['labels']:
            click.echo("\nEmails by label:")
            for label_name, count in sorted(summary['labels'].items()):
                click.echo(f"  {label_name}: {count}")

        if summary['date_range']['earliest']:
            click.echo(f"\nDate range:")
            click.echo(f"  Earliest: {summary['date_range']['earliest']}")
            click.echo(f"  Latest: {summary['date_range']['latest']}")

        click.echo("\n✓ Parsing complete!")
        click.echo(f"  Output directory: {output_dir}")

        # TODO: Update agata_kb_sync_status in database
        click.echo("\nNote: Database sync status not yet updated (run 'kb update-db-status' after migration)")

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('parse-document')
@click.option(
    '--file',
    type=click.Path(exists=True),
    required=True,
    help='File to parse (.txt or .md)'
)
@click.option(
    '--tags',
    default=None,
    help='Comma-separated tags (e.g., aavso,guidelines,submission)'
)
@click.option(
    '--title',
    default=None,
    help='Document title (optional, defaults to filename)'
)
@click.option(
    '--output-dir',
    default='/var/www/astrogen/kb_data/documents_parsed',
    help='Output directory for parsed documents'
)
def parse_document(file, tags, title, output_dir):
    """
    Parse a single text or markdown document

    Examples:
        # Parse text file
        python -m agata.kb parse-document --file=doc.txt --tags=aavso,guidelines

        # Parse markdown file with custom title
        python -m agata.kb parse-document --file=AAVSO.md --title="AAVSO Guidelines" --tags=aavso,submission
    """
    try:
        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - Document Parser")
        click.echo("=" * 60)

        file_path = Path(file)

        # Parse tags
        tags_list = [t.strip() for t in tags.split(',')] if tags else []

        # Determine parser based on file extension
        ext = file_path.suffix.lower()

        if ext == '.md':
            click.echo(f"\n📄 Parsing Markdown file: {file}")
            parser = MarkdownParserService(output_dir=output_dir)
            doc_data = parser.parse(file, tags=tags_list)
        elif ext == '.txt':
            click.echo(f"\n📄 Parsing Text file: {file}")
            parser = TextFileParserService(output_dir=output_dir)
            doc_data = parser.parse(file, tags=tags_list, title=title)
        else:
            click.echo(f"✗ Error: Unsupported file type '{ext}' (supported: .txt, .md)", err=True)
            sys.exit(1)

        # Display results
        click.echo("\n" + "=" * 60)
        click.echo("PARSING RESULTS")
        click.echo("=" * 60)
        click.echo(f"Document ID: {doc_data['id']}")
        click.echo(f"Title: {doc_data['title']}")
        click.echo(f"Type: {doc_data['doc_type']}")
        click.echo(f"Tags: {', '.join(doc_data.get('tags', []))}")
        click.echo(f"Content Length: {doc_data['content_length']} characters")
        click.echo(f"Saved to: {output_dir}/{doc_data['id']}.json")

        click.echo("\n✓ Document parsed successfully!")

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('parse-documents')
@click.option(
    '--input-dir',
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help='Directory containing documents to parse'
)
@click.option(
    '--extension',
    default='.txt',
    help='File extension to parse (e.g., .txt, .md)'
)
@click.option(
    '--recursive/--no-recursive',
    default=False,
    help='Recursively search subdirectories'
)
@click.option(
    '--tags',
    default=None,
    help='Comma-separated tags to add to all documents'
)
@click.option(
    '--output-dir',
    default='/var/www/astrogen/kb_data/documents_parsed',
    help='Output directory for parsed documents'
)
def parse_documents(input_dir, extension, recursive, tags, output_dir):
    """
    Parse multiple documents from a directory

    Examples:
        # Parse all .txt files in directory
        python -m agata.kb parse-documents --input-dir=/path/to/docs/ --extension=.txt

        # Parse .md files recursively with tags
        python -m agata.kb parse-documents --input-dir=/docs --extension=.md --recursive --tags=astronomy,research
    """
    try:
        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - Batch Document Parser")
        click.echo("=" * 60)

        input_path = Path(input_dir)
        click.echo(f"\n📁 Parsing documents from: {input_dir}")
        click.echo(f"   Extension: {extension}")
        click.echo(f"   Recursive: {recursive}")

        # Parse tags
        tags_list = [t.strip() for t in tags.split(',')] if tags else []

        # Find files
        pattern = f"**/*{extension}" if recursive else f"*{extension}"
        files = list(input_path.glob(pattern))

        if not files:
            click.echo(f"\n⚠️  No files found matching '{pattern}'")
            return

        click.echo(f"\n Found {len(files)} file(s) to parse\n")

        # Determine parser based on extension
        ext_lower = extension.lower()
        if ext_lower == '.md':
            parser_class = MarkdownParserService
        elif ext_lower == '.txt':
            parser_class = TextFileParserService
        else:
            click.echo(f"✗ Error: Unsupported extension '{extension}' (supported: .txt, .md)", err=True)
            sys.exit(1)

        parser = parser_class(output_dir=output_dir)

        # Parse each file
        success_count = 0
        error_count = 0

        for file_path in sorted(files):
            try:
                click.echo(f"  Parsing: {file_path.name}...", nl=False)
                doc_data = parser.parse(str(file_path), tags=tags_list)
                click.echo(f" ✓ ({doc_data['content_length']} chars)")
                success_count += 1
            except Exception as e:
                click.echo(f" ✗ Error: {e}")
                error_count += 1

        # Display summary
        click.echo("\n" + "=" * 60)
        click.echo("BATCH PARSING RESULTS")
        click.echo("=" * 60)
        click.echo(f"Successfully parsed: {success_count}")
        click.echo(f"Errors: {error_count}")
        click.echo(f"Output directory: {output_dir}")

        if success_count > 0:
            click.echo("\n✓ Batch parsing complete!")
        else:
            click.echo("\n✗ No documents parsed successfully")
            sys.exit(1)

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('status')
@click.option(
    '--output-dir',
    default='/var/www/astrogen/kb_data/gmail_parsed',
    help='Directory with parsed emails'
)
def status(output_dir):
    """Show knowledge base indexing status"""
    try:
        parser = MboxParserService(output_dir=output_dir)
        summary = parser.get_indexed_emails_summary()

        click.echo("=" * 60)
        click.echo("KNOWLEDGE BASE STATUS")
        click.echo("=" * 60)
        click.echo(f"Total emails indexed: {summary['total_emails']}")
        click.echo(f"Last updated: {summary['last_updated'] or 'Never'}")

        if summary['labels']:
            click.echo("\nEmails by label:")
            for label_name, count in sorted(summary['labels'].items(), key=lambda x: x[1], reverse=True):
                click.echo(f"  {label_name:20s} {count:>6d} emails")

        if summary['date_range']['earliest']:
            click.echo(f"\nDate range:")
            click.echo(f"  Earliest: {summary['date_range']['earliest']}")
            click.echo(f"  Latest: {summary['date_range']['latest']}")
        else:
            click.echo("\nNo emails indexed yet")

        click.echo(f"\nStorage location: {output_dir}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@kb.command('update-db-status')
@click.option(
    '--output-dir',
    default='/var/www/astrogen/kb_data/gmail_parsed',
    help='Directory with parsed emails'
)
def update_db_status(output_dir):
    """Update agata_kb_sync_status table with current indexing stats"""
    try:
        from agata.auth_models import db, KBSyncStatus
        from agata import create_app

        app = create_app()

        with app.app_context():
            parser = MboxParserService(output_dir=output_dir)
            summary = parser.get_indexed_emails_summary()

            # Find or create MBOX sync status record
            sync_status = KBSyncStatus.query.filter_by(
                source='mbox',
                user_id=None,
                association_id=None
            ).first()

            if not sync_status:
                sync_status = KBSyncStatus(
                    source='mbox',
                    sync_status='completed'
                )
                db.session.add(sync_status)

            # Update stats
            sync_status.total_items_indexed = summary['total_emails']
            sync_status.last_sync_at = datetime.now()
            sync_status.sync_status = 'completed'
            sync_status.config = {
                'output_dir': output_dir,
                'labels': summary['labels'],
                'date_range': summary['date_range']
            }

            db.session.commit()

            click.echo("✓ Database sync status updated")
            click.echo(f"  Total items: {summary['total_emails']}")
            click.echo(f"  Last sync: {sync_status.last_sync_at}")

    except ImportError:
        click.echo("Error: Database models not available. Run migration first:", err=True)
        click.echo("  mysql catalogo < migrations/create_kb_tables.sql")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('generate-embeddings')
@click.option(
    '--provider',
    default='sentence-transformers',
    type=click.Choice(['openai', 'voyage', 'sentence-transformers']),
    help='Embedding provider: openai (paid), voyage (free tier 100M tokens), sentence-transformers (local, free)'
)
@click.option(
    '--source',
    default='mbox',
    help='Source to generate embeddings for (mbox, teams, etc.)'
)
@click.option(
    '--input-dir',
    default='/var/www/astrogen/kb_data/gmail_parsed',
    help='Directory with parsed emails'
)
@click.option(
    '--batch-size',
    default=50,
    type=int,
    help='Number of emails to process in one batch'
)
@click.option(
    '--max-emails',
    default=None,
    type=int,
    help='Maximum number of emails to process (for testing)'
)
@click.option(
    '--chunk-size',
    default=500,
    type=int,
    help='Words per chunk for long emails'
)
def generate_embeddings(provider, source, input_dir, batch_size, max_emails, chunk_size):
    """
    Generate embeddings for parsed emails and store in vector database

    Examples:
        # Local, free, no API needed (DEFAULT)
        python -m agata.kb generate-embeddings --provider=sentence-transformers

        # Voyage AI (free tier 100M tokens/month)
        export VOYAGE_API_KEY=pa-...
        python -m agata.kb generate-embeddings --provider=voyage

        # OpenAI (paid)
        export OPENAI_API_KEY=sk-...
        python -m agata.kb generate-embeddings --provider=openai

        # Test with first 100 emails
        python -m agata.kb generate-embeddings --max-emails=100
    """
    import os
    import json
    from pathlib import Path

    # Check API keys based on provider
    if provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        click.echo("Error: OPENAI_API_KEY environment variable not set", err=True)
        click.echo("Export your OpenAI API key: export OPENAI_API_KEY=sk-...", err=True)
        sys.exit(1)

    if provider == 'voyage' and not os.getenv('VOYAGE_API_KEY'):
        click.echo("Error: VOYAGE_API_KEY environment variable not set", err=True)
        click.echo("Get your free Voyage AI key at: https://dash.voyageai.com/", err=True)
        click.echo("Then: export VOYAGE_API_KEY=pa-...", err=True)
        sys.exit(1)

    try:
        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - Embedding Generator")
        click.echo("=" * 60)

        # Initialize services
        click.echo(f"\nInitializing services (provider: {provider})...")
        embedding_service = EmbeddingService(provider=provider)
        vector_store = VectorStore()

        # Collect documents from multiple sources
        all_doc_ids = {}
        all_doc_files = {}

        # Source 1: Emails (MBOX)
        email_input_dir = input_dir
        email_index_file = Path(email_input_dir) / 'index.json'
        if email_index_file.exists():
            click.echo(f"Loading emails from: {email_input_dir}")
            try:
                with open(email_index_file, 'r') as f:
                    email_index_data = json.load(f)
                email_ids = list(email_index_data['emails'].keys())
                for doc_id in email_ids:
                    all_doc_ids[doc_id] = 'mbox'
                    all_doc_files[doc_id] = Path(email_input_dir) / f"{doc_id}.json"
                click.echo(f"  Found {len(email_ids)} parsed emails")
            except Exception as e:
                click.echo(f"  Warning: Could not load email index: {e}")
        else:
            click.echo(f"No email index found at {email_index_file}")

        # Source 2: Teams messages
        teams_input_dir = '/var/www/astrogen/kb_data/teams_parsed'
        teams_index_file = Path(teams_input_dir) / 'index.json'
        if teams_index_file.exists():
            click.echo(f"Loading Teams messages from: {teams_input_dir}")
            try:
                with open(teams_index_file, 'r') as f:
                    teams_index_data = json.load(f)
                teams_ids = list(teams_index_data.get('messages', {}).keys())
                for doc_id in teams_ids:
                    if doc_id not in all_doc_ids:
                        all_doc_ids[doc_id] = 'teams'
                        all_doc_files[doc_id] = Path(teams_input_dir) / f"{doc_id}.json"
                click.echo(f"  Found {len(teams_ids)} parsed Teams messages")
            except Exception as e:
                click.echo(f"  Warning: Could not load Teams index: {e}")

        # Source 3: Documents (Markdown, Text)
        doc_input_dir = '/var/www/astrogen/kb_data/documents_parsed'
        doc_index_file = Path(doc_input_dir) / 'index.json'
        if doc_index_file.exists():
            click.echo(f"Loading documents from: {doc_input_dir}")
            try:
                with open(doc_index_file, 'r') as f:
                    doc_index_data = json.load(f)
                doc_ids = list(doc_index_data['documents'].keys())
                for doc_id in doc_ids:
                    if doc_id not in all_doc_ids:  # Avoid duplicates
                        all_doc_ids[doc_id] = 'document'
                        all_doc_files[doc_id] = Path(doc_input_dir) / f"{doc_id}.json"
                click.echo(f"  Found {len(doc_ids)} parsed documents")
            except Exception as e:
                click.echo(f"  Warning: Could not load document index: {e}")
        else:
            click.echo(f"No document index found at {doc_index_file}")

        if not all_doc_ids:
            click.echo("\nError: No emails or documents found. Run 'parse-mbox' or 'parse-document' first.", err=True)
            sys.exit(1)

        click.echo(f"\nTotal items to embed: {len(all_doc_ids)}")

        # Check how many already have embeddings
        existing_vectors = vector_store.count_vectors()
        click.echo(f"Already embedded: {existing_vectors}")

        # Convert to list for processing
        doc_ids_list = list(all_doc_ids.keys())

        if max_emails:
            doc_ids_list = doc_ids_list[:max_emails]
            click.echo(f"Processing only first {max_emails} items (test mode)")

        # Process documents and emails
        click.echo(f"\nGenerating embeddings (batch size: {batch_size})...")
        click.echo("-" * 60)

        processed = 0
        skipped = 0
        errors = 0

        for i in range(0, len(doc_ids_list), batch_size):
            batch_ids = doc_ids_list[i:i + batch_size]

            for doc_id in batch_ids:
                try:
                    # Check if already embedded
                    existing_vec = vector_store.get_vector(doc_id)
                    if existing_vec is not None:
                        skipped += 1
                        continue

                    # Load document data
                    doc_file = all_doc_files[doc_id]
                    if not doc_file.exists():
                        click.echo(f"  Warning: File not found: {doc_id}", err=True)
                        errors += 1
                        continue

                    with open(doc_file, 'r') as f:
                        doc_data = json.load(f)

                    # Prepare text for embedding
                    text_parts = []

                    # Different handling based on document type
                    doc_type = all_doc_ids[doc_id]

                    if doc_type == 'mbox':
                        # Email format
                        if doc_data.get('subject'):
                            text_parts.append(f"Subject: {doc_data['subject']}")
                        from_info = doc_data.get('from', {})
                        if isinstance(from_info, dict) and from_info.get('name'):
                            text_parts.append(f"From: {from_info['name']}")
                        if doc_data.get('body_text'):
                            text_parts.append(doc_data['body_text'])
                    elif doc_type == 'teams':
                        # Teams message format
                        if doc_data.get('subject'):
                            text_parts.append(f"Subject: {doc_data['subject']}")
                        if doc_data.get('from_name'):
                            text_parts.append(f"From: {doc_data['from_name']}")
                        if doc_data.get('body_text'):
                            text_parts.append(doc_data['body_text'])
                    else:
                        # Document format (markdown, text)
                        if doc_data.get('title'):
                            text_parts.append(f"Title: {doc_data['title']}")
                        if doc_data.get('content'):
                            text_parts.append(doc_data['content'])

                    full_text = '\n\n'.join(text_parts)

                    if not full_text.strip():
                        click.echo(f"  Warning: Empty content: {doc_id}", err=True)
                        errors += 1
                        continue

                    # Generate embedding (chunks if needed)
                    if len(full_text.split()) > chunk_size:
                        # Long document - use chunking
                        chunks = embedding_service.embed_document(
                            doc_id,
                            full_text,
                            chunk_size=chunk_size,
                            overlap=50
                        )
                        # Use first chunk
                        embedding = chunks[0]['embedding']
                    else:
                        # Short document - single embedding
                        embedding = embedding_service.embed(full_text)

                    # Prepare metadata (unified format)
                    metadata = {
                        'source': all_doc_ids[doc_id],
                        'doc_id': doc_id,
                        'doc_type': doc_data.get('doc_type', 'unknown'),
                        'title': doc_data.get('title', doc_data.get('subject', '')),
                        'tags': doc_data.get('tags', []),
                        'date': doc_data.get('date'),
                    }

                    # Add source-specific fields
                    if doc_type == 'mbox':
                        from_info = doc_data.get('from', {})
                        metadata.update({
                            'from_email': from_info.get('email', '') if isinstance(from_info, dict) else '',
                            'from_name': from_info.get('name', '') if isinstance(from_info, dict) else '',
                            'subject': doc_data.get('subject', ''),
                            'label': doc_data.get('label', ''),
                            'body_text': doc_data.get('body_text', '')[:1500],
                            'body_length': doc_data.get('body_length', 0)
                        })
                    elif doc_type == 'teams':
                        metadata.update({
                            'from_name': doc_data.get('from_name', ''),
                            'subject': doc_data.get('subject', ''),
                            'star_id': doc_data.get('star_id'),
                            'variable_type': doc_data.get('variable_type'),
                            'body_text': doc_data.get('body_text', '')[:1500],
                            'body_length': doc_data.get('body_length', 0)
                        })
                    elif doc_type == 'document':
                        metadata.update({
                            'content_length': doc_data.get('content_length', 0),
                        })

                    # Store in vector database
                    vector_store.store_vector(doc_id, embedding, metadata)

                    processed += 1

                    if processed % 10 == 0:
                        click.echo(f"  Processed: {processed}, Skipped: {skipped}, Errors: {errors}")

                except Exception as e:
                    click.echo(f"  Error processing {doc_id}: {e}", err=True)
                    errors += 1

        # Final summary
        click.echo("\n" + "=" * 60)
        click.echo("EMBEDDING GENERATION COMPLETE")
        click.echo("=" * 60)
        click.echo(f"Successfully processed: {processed}")
        click.echo(f"Skipped (already embedded): {skipped}")
        click.echo(f"Errors: {errors}")

        # Vector store stats
        stats = vector_store.get_stats()
        click.echo(f"\nTotal vectors in store: {stats['total_vectors']}")

        if stats['sources']:
            click.echo("\nVectors by source:")
            for src, count in stats['sources'].items():
                click.echo(f"  {src}: {count}")

        click.echo("\n✓ Embeddings generated successfully!")

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('search')
@click.argument('query')
@click.option(
    '--provider',
    default='sentence-transformers',
    type=click.Choice(['openai', 'voyage', 'sentence-transformers']),
    help='Embedding provider (must match the one used for indexing)'
)
@click.option(
    '--top-k',
    default=5,
    type=int,
    help='Number of results to return'
)
@click.option(
    '--source',
    default=None,
    help='Filter by source (mbox, teams, etc.)'
)
def search(query, provider, top_k, source):
    """
    Search the knowledge base with a natural language query

    Examples:
        python -m agata.kb search "Gaia DR3 query configuration"
        python -m agata.kb search "TESS data download" --top-k=10
        python -m agata.kb search "come configurare TESS" --provider=sentence-transformers
    """
    import os

    # Check API keys based on provider
    if provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        click.echo("Error: OPENAI_API_KEY environment variable not set", err=True)
        sys.exit(1)

    if provider == 'voyage' and not os.getenv('VOYAGE_API_KEY'):
        click.echo("Error: VOYAGE_API_KEY environment variable not set", err=True)
        sys.exit(1)

    try:
        click.echo("=" * 60)
        click.echo(f"Searching: {query}")
        click.echo("=" * 60)

        # Initialize services
        click.echo(f"Using provider: {provider}")
        embedding_service = EmbeddingService(provider=provider)
        vector_store = VectorStore()

        # Check if there are vectors
        total_vectors = vector_store.count_vectors()
        if total_vectors == 0:
            click.echo("Error: No embeddings found. Run 'generate-embeddings' first.", err=True)
            sys.exit(1)

        click.echo(f"Searching {total_vectors} documents...\n")

        # Generate query embedding
        query_embedding = embedding_service.embed(query)

        # Search
        filters = {'source': source} if source else None
        results = vector_store.search(query_embedding, top_k=top_k, filters=filters)

        if not results:
            click.echo("No results found.")
            sys.exit(0)

        # Display results
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            click.echo(f"{i}. Score: {result['score']:.4f}")
            click.echo(f"   Subject: {metadata.get('subject', '(no subject)')}")
            click.echo(f"   From: {metadata.get('from_name', '')} <{metadata.get('from_email', '')}>")
            click.echo(f"   Date: {metadata.get('date', 'unknown')}")
            click.echo(f"   Label: {metadata.get('label', 'unknown')}")
            click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('ask')
@click.argument('question')
@click.option(
    '--provider',
    default='sentence-transformers',
    type=click.Choice(['openai', 'voyage', 'sentence-transformers']),
    help='Embedding provider (must match the one used for indexing)'
)
@click.option(
    '--top-k',
    default=5,
    type=int,
    help='Number of emails to use as context'
)
def ask(question, provider, top_k):
    """
    Ask a question and get an AI-powered answer using RAG (Retrieval-Augmented Generation)

    Examples:
        python -m agata.kb ask "Come si compila il documento per AAVSO?"
        python -m agata.kb ask "What are the requirements for AAVSO submission?"
        python -m agata.kb ask "Come analizzare una stella variabile?" --top-k=10
    """
    try:
        click.echo("=" * 60)
        click.echo(f"Question: {question}")
        click.echo("=" * 60)

        # Initialize services
        embedding_service = EmbeddingService(provider=provider)
        vector_store = VectorStore()

        # Check if there are vectors
        total_vectors = vector_store.count_vectors()
        if total_vectors == 0:
            click.echo("Error: No embeddings found. Run 'generate-embeddings' first.", err=True)
            sys.exit(1)

        click.echo(f"\n🔍 Searching {total_vectors} emails for relevant context...")

        # Generate query embedding
        query_embedding = embedding_service.embed(question)

        # Search for relevant emails
        results = vector_store.search(query_embedding, top_k=top_k)

        if not results:
            click.echo("No relevant emails found.")
            sys.exit(0)

        click.echo(f"✓ Found {len(results)} relevant emails\n")

        # Load full email content
        from pathlib import Path
        import json

        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            email_id = metadata.get('email_id')

            # Load full email
            email_file = Path('/var/www/astrogen/kb_data/gmail_parsed') / f"{email_id}.json"
            if email_file.exists():
                with open(email_file, 'r') as f:
                    email_data = json.load(f)

                context_parts.append(f"""
Email {i} (Score: {result['score']:.3f})
Subject: {email_data.get('subject', 'No subject')}
From: {email_data.get('from', {}).get('name', 'Unknown')} <{email_data.get('from', {}).get('email', '')}>
Date: {email_data.get('date', 'Unknown')}

Content:
{email_data.get('body_text', '')[:1000]}
---
""")

        context_text = '\n'.join(context_parts)

        # Build prompt for LLM
        prompt = f"""Sei un assistente esperto in astronomia e analisi di stelle variabili.

Basandoti SOLO sulle seguenti email, rispondi alla domanda dell'utente in modo chiaro e dettagliato.
Se le informazioni non sono sufficienti, dillo chiaramente.

EMAIL RILEVANTI:
{context_text}

DOMANDA: {question}

Rispondi in italiano (o nella lingua della domanda) in modo chiaro e strutturato.
Cita le email quando possibile (es: "Secondo l'email del [data]...").
"""

        click.echo("🤖 Generating answer with Cerebras LLM...\n")
        click.echo("=" * 60)

        # Use Cerebras LLM (already configured in .env)
        from agata.moduli.variable_stars.services.llm_client import LLMClient

        llm = LLMClient()
        result = llm.generate(prompt, temperature=0.3, max_tokens=1000)
        answer = result['response_text']

        click.echo(answer)
        click.echo("=" * 60)

        # Show sources
        click.echo("\n📚 Sources (emails used):")
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            click.echo(f"  {i}. {metadata.get('subject', '(no subject)')} - Score: {result['score']:.3f}")
            click.echo(f"     From: {metadata.get('from_name', 'Unknown')} ({metadata.get('date', 'unknown')})")

        click.echo("\n✓ Answer generated successfully!")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('parse-teams')
@click.option(
    '--teams-dir',
    default='/var/www/astrogen/kb_data/canali teams',
    help='Root directory of Teams channel export'
)
@click.option(
    '--channel',
    default='Stelle variabili',
    help='Channel subdirectory name'
)
def parse_teams(teams_dir, channel):
    """
    Parse Teams channel export (Microsoft Graph JSON messages)

    Examples:
        python -m agata.kb parse-teams
        python -m agata.kb parse-teams --teams-dir="/path/to/canali teams" --channel="Stelle variabili"
    """
    try:
        from agata.kb.services.parsers.teams_parser import TeamsParserService

        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - Teams Parser")
        click.echo("=" * 60)
        click.echo(f"\nParsing Teams channel: {channel}")
        click.echo(f"Directory: {teams_dir}")

        parser = TeamsParserService()
        stats = parser.parse_teams_directory(teams_dir, channel_name=channel)

        summary = parser.get_summary()
        click.echo(f"\nStars found: {summary['stars_found']}")
        if summary['type_distribution']:
            click.echo("\nVariable types:")
            for vtype, count in summary['type_distribution'].items():
                click.echo(f"  {vtype}: {count}")

        click.echo("\n✓ Teams parsing complete!")

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('reparse')
@click.option(
    '--gmail-dir',
    default='/var/www/astrogen/kb_data/gmail_parsed',
    help='Directory with parsed email JSONs'
)
@click.option(
    '--teams-dir',
    default='/var/www/astrogen/kb_data/teams_parsed',
    help='Directory with parsed Teams JSONs'
)
def reparse(gmail_dir, teams_dir):
    """
    Re-parse existing email/Teams JSONs with improved HTML cleaning.
    Updates body_text in-place using BeautifulSoup.

    Examples:
        python -m agata.kb reparse
    """
    import json
    from bs4 import BeautifulSoup

    click.echo("=" * 60)
    click.echo("AGATA Knowledge Base - Re-parse with Clean HTML")
    click.echo("=" * 60)

    updated = 0
    skipped = 0

    gmail_path = Path(gmail_dir)
    if gmail_path.exists():
        json_files = [f for f in gmail_path.glob('*.json') if f.name != 'index.json']
        click.echo(f"\nRe-parsing {len(json_files)} email files...")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                body = data.get('body_text', '')
                if not body:
                    skipped += 1
                    continue

                # Check if body contains HTML tags
                if '<' in body and '>' in body:
                    soup = BeautifulSoup(body, 'html.parser')
                    for tag in soup(['script', 'style']):
                        tag.decompose()
                    clean = soup.get_text(separator='\n', strip=True)
                    import re as _re
                    clean = _re.sub(r'\n{3,}', '\n\n', clean)
                    data['body_text'] = clean.strip()[:15000]
                    data['body_length'] = len(clean.strip())

                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    updated += 1
                else:
                    skipped += 1

            except Exception as e:
                click.echo(f"  Error: {json_file.name}: {e}")

    # Same for Teams
    teams_path = Path(teams_dir)
    teams_updated = 0
    if teams_path.exists():
        json_files = [f for f in teams_path.glob('*.json') if f.name != 'index.json']
        click.echo(f"\nRe-parsing {len(json_files)} Teams message files...")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                body = data.get('body_text', '')
                if body and '<' in body and '>' in body:
                    soup = BeautifulSoup(body, 'html.parser')
                    for tag in soup(['script', 'style', 'attachment']):
                        tag.decompose()
                    clean = soup.get_text(separator='\n', strip=True)
                    import re as _re
                    clean = _re.sub(r'\n{3,}', '\n\n', clean)
                    data['body_text'] = clean.strip()[:15000]
                    data['body_length'] = len(clean.strip())

                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    teams_updated += 1

            except Exception as e:
                click.echo(f"  Error: {json_file.name}: {e}")

    click.echo(f"\n✓ Re-parse complete:")
    click.echo(f"  Emails cleaned: {updated}")
    click.echo(f"  Emails skipped (already clean): {skipped}")
    click.echo(f"  Teams cleaned: {teams_updated}")


@kb.command('build-star-index')
def build_star_index_cmd():
    """
    Build star-based knowledge index from all parsed emails and Teams messages.
    Maps each GrAGVar star to related messages, corrections, and metadata.

    Examples:
        python -m agata.kb build-star-index
    """
    try:
        from agata.kb.services.star_index import build_star_index, get_index_summary

        click.echo("=" * 60)
        click.echo("AGATA Knowledge Base - Build Star Index")
        click.echo("=" * 60)

        index = build_star_index()

        summary = get_index_summary()
        click.echo(f"\nSummary:")
        click.echo(f"  Stars with expert reviews: {summary['stars_with_expert']}")
        click.echo(f"  Stars with corrections: {summary['stars_with_corrections']}")

        click.echo("\n✓ Star index built successfully!")

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@kb.command('rebuild-all')
@click.option(
    '--provider',
    default='sentence-transformers',
    type=click.Choice(['openai', 'voyage', 'sentence-transformers']),
    help='Embedding provider'
)
@click.option(
    '--skip-mbox-parse', is_flag=True, default=False,
    help='Skip MBOX re-parsing (if already done)'
)
def rebuild_all(provider, skip_mbox_parse):
    """
    Full rebuild: re-parse MBOX + parse Teams + clean HTML + regenerate embeddings + build star index.

    Examples:
        python -m agata.kb rebuild-all
        python -m agata.kb rebuild-all --skip-mbox-parse
    """
    import json
    from agata.kb.services.parsers.teams_parser import TeamsParserService
    from agata.kb.services.star_index import build_star_index

    click.echo("=" * 60)
    click.echo("AGATA Knowledge Base - FULL REBUILD")
    click.echo("=" * 60)

    # Step 1: Re-parse MBOX if not skipped
    if not skip_mbox_parse:
        click.echo("\n[1/5] Re-parsing MBOX emails...")
        mbox_dir = Path('/var/www/astrogen/kb_data/mbox_raw')
        if mbox_dir.exists() and list(mbox_dir.glob('*.mbox')):
            parser = MboxParserService()
            parser.parse_multiple_mbox_files(str(mbox_dir))
        else:
            click.echo("  No MBOX files found, skipping")
    else:
        click.echo("\n[1/5] Skipping MBOX parse (--skip-mbox-parse)")

    # Step 2: Parse Teams
    click.echo("\n[2/5] Parsing Teams messages...")
    teams_dir = Path('/var/www/astrogen/kb_data/canali teams')
    if teams_dir.exists():
        teams_parser = TeamsParserService()
        teams_parser.parse_teams_directory(str(teams_dir))
    else:
        click.echo("  No Teams directory found, skipping")

    # Step 3: Re-parse (clean HTML)
    click.echo("\n[3/5] Cleaning HTML in parsed files...")
    ctx = click.Context(reparse)
    ctx.invoke(reparse, gmail_dir='/var/www/astrogen/kb_data/gmail_parsed',
               teams_dir='/var/www/astrogen/kb_data/teams_parsed')

    # Step 4: Clear old embeddings and regenerate
    click.echo("\n[4/5] Regenerating embeddings...")
    vector_store = VectorStore()
    old_count = vector_store.count_vectors()
    click.echo(f"  Clearing {old_count} old vectors...")
    vector_store.clear_all()

    # Generate new embeddings for all sources
    embedding_service = EmbeddingService(provider=provider)

    # Collect all documents
    all_docs = []

    # Emails
    gmail_dir = Path('/var/www/astrogen/kb_data/gmail_parsed')
    if gmail_dir.exists():
        for jf in gmail_dir.glob('*.json'):
            if jf.name != 'index.json':
                all_docs.append(('mbox', jf))

    # Teams
    teams_parsed_dir = Path('/var/www/astrogen/kb_data/teams_parsed')
    if teams_parsed_dir.exists():
        for jf in teams_parsed_dir.glob('*.json'):
            if jf.name != 'index.json':
                all_docs.append(('teams', jf))

    # Documents
    docs_dir = Path('/var/www/astrogen/kb_data/documents_parsed')
    if docs_dir.exists():
        for jf in docs_dir.glob('*.json'):
            if jf.name != 'index.json':
                all_docs.append(('document', jf))

    click.echo(f"  Embedding {len(all_docs)} documents...")
    processed = 0
    errors = 0

    for source, doc_file in all_docs:
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_id = data.get('id', doc_file.stem)

            # Build text for embedding
            text_parts = []
            if source == 'mbox':
                if data.get('subject'):
                    text_parts.append(f"Subject: {data['subject']}")
                if data.get('from', {}).get('name'):
                    text_parts.append(f"From: {data['from']['name']}")
                text_parts.append(data.get('body_text', ''))
                metadata = {
                    'source': 'mbox',
                    'doc_id': doc_id,
                    'subject': data.get('subject', ''),
                    'from_email': data.get('from', {}).get('email', ''),
                    'from_name': data.get('from', {}).get('name', ''),
                    'date': data.get('date'),
                    'label': data.get('label', ''),
                    'body_text': data.get('body_text', '')[:1500],
                    'body_length': data.get('body_length', 0),
                }
            elif source == 'teams':
                if data.get('subject'):
                    text_parts.append(f"Subject: {data['subject']}")
                if data.get('from_name'):
                    text_parts.append(f"From: {data['from_name']}")
                text_parts.append(data.get('body_text', ''))
                metadata = {
                    'source': 'teams',
                    'doc_id': doc_id,
                    'subject': data.get('subject', ''),
                    'from_name': data.get('from_name', ''),
                    'date': data.get('date'),
                    'star_id': data.get('star_id'),
                    'variable_type': data.get('variable_type'),
                    'body_text': data.get('body_text', '')[:1500],
                    'body_length': data.get('body_length', 0),
                }
            else:
                if data.get('title'):
                    text_parts.append(f"Title: {data['title']}")
                text_parts.append(data.get('content', ''))
                metadata = {
                    'source': 'document',
                    'doc_id': doc_id,
                    'title': data.get('title', ''),
                    'date': data.get('date'),
                    'tags': data.get('tags', []),
                    'content_length': data.get('content_length', 0),
                }

            full_text = '\n\n'.join(t for t in text_parts if t)
            if not full_text.strip():
                continue

            embedding = embedding_service.embed(full_text)
            vector_store.store_vector(doc_id, embedding, metadata)
            processed += 1

            if processed % 50 == 0:
                click.echo(f"  Processed: {processed}/{len(all_docs)}")

        except Exception as e:
            errors += 1
            if errors <= 5:
                click.echo(f"  Error: {doc_file.name}: {e}")

    click.echo(f"  Embedded: {processed}, Errors: {errors}")

    # Step 5: Build star index
    click.echo("\n[5/5] Building star index...")
    build_star_index()

    click.echo("\n" + "=" * 60)
    click.echo("REBUILD COMPLETE")
    click.echo("=" * 60)
    click.echo(f"  Vectors in store: {vector_store.count_vectors()}")
    click.echo("\n✓ Full rebuild finished!")


if __name__ == '__main__':
    kb()
