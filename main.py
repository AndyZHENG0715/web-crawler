"""
Entrypoint for the Hong Kong Policy Address web crawler.
Loads config, runs crawl, then indexing (chunk+embed+optional upsert).
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

from crawler.config import load_config
from crawler.policy_address import crawl_policy_address
from crawler.indexer import index_documents

console = Console()


def setup_logging(config):
    """Set up logging with rich formatting."""
    # Create logs directory
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level.upper()))
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Rich console handler
    if config.logging.show_progress:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True
        )
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized - Level: {config.logging.level}, File: {log_file}")


async def main():
    """Main crawler execution."""
    parser = argparse.ArgumentParser(
        description="Hong Kong Policy Address Web Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config configs/config.yaml
  python main.py --config configs/config.yaml --crawl-only
  python main.py --config configs/config.yaml --index-only
        """
    )
    parser.add_argument(
        "--config", 
        type=str, 
        default="configs/config.yaml",
        help="Path to config file (default: configs/config.yaml)"
    )
    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="Only crawl documents, skip indexing"
    )
    parser.add_argument(
        "--index-only", 
        action="store_true",
        help="Only run indexing (requires existing crawl data)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true", 
        help="Validate configuration without crawling"
    )
    
    args = parser.parse_args()
    
    try:
        # Load and validate configuration
        console.print("[bold blue]Loading configuration...[/bold blue]")
        config = load_config(args.config)
        console.print(f"✅ Configuration loaded from {args.config}")
        
        # Setup logging
        setup_logging(config)
        
        # Validate configuration
        if not config.seeds:
            console.print("[red]❌ Error: No seed URLs configured[/red]")
            return 1
            
        if not config.allowed_hosts:
            console.print("[red]❌ Error: No allowed hosts configured[/red]")
            return 1
            
        # Show configuration summary
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Seed URLs: {len(config.seeds)}")
        console.print(f"  Allowed hosts: {', '.join(config.allowed_hosts)}")
        console.print(f"  Max pages: {config.max_pages}")
        console.print(f"  Rate limit: {config.rate_limits.per_host_rps} RPS per host")
        console.print(f"  OpenAI embeddings: {'✅' if config.openai.enabled else '❌'}")
        console.print(f"  Pinecone storage: {'✅' if config.pinecone.enabled else '❌'}")
        
        if args.dry_run:
            console.print("\n[green]✅ Configuration validation complete (dry run)[/green]")
            return 0
            
        # Start processing
        start_time = time.time()
        documents = []
        
        # Crawling phase
        if not args.index_only:
            console.print("\n[bold green]🕷️  Starting crawl phase...[/bold green]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                disable=not config.logging.show_progress
            ) as progress:
                task = progress.add_task("Crawling documents...", total=None)
                
                try:
                    documents = await crawl_policy_address(config)
                    progress.update(task, description=f"Crawled {len(documents)} documents")
                    
                except KeyboardInterrupt:
                    console.print("\n[yellow]⚠️  Crawling interrupted by user[/yellow]")
                    return 1
                except Exception as e:
                    console.print(f"\n[red]❌ Crawling failed: {e}[/red]")
                    logging.exception("Crawling failed")
                    return 1
            
            console.print(f"✅ Crawling complete: {len(documents)} documents")
            
            if not documents:
                console.print("[yellow]⚠️  No documents were crawled[/yellow]")
                if not args.crawl_only:
                    console.print("[yellow]Skipping indexing phase[/yellow]")
                return 0
        
        # Indexing phase
        if not args.crawl_only:
            console.print("\n[bold blue]📚 Starting indexing phase...[/bold blue]")
            
            if args.index_only:
                console.print("[yellow]⚠️  Index-only mode: using documents from crawl results[/yellow]")
                # In a real implementation, you might load documents from a previous crawl
                # For now, we'll just show an error
                console.print("[red]❌ Index-only mode not implemented yet[/red]")
                console.print("[yellow]💡 Run without --index-only to crawl and index in one go[/yellow]")
                return 1
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                disable=not config.logging.show_progress
            ) as progress:
                task = progress.add_task("Processing documents...", total=None)
                
                try:
                    stats = await index_documents(config, documents)
                    progress.update(task, description=f"Indexed {stats.get('total_chunks', 0)} chunks")
                    
                except Exception as e:
                    console.print(f"\n[red]❌ Indexing failed: {e}[/red]")
                    logging.exception("Indexing failed")
                    return 1
            
            # Show indexing results
            console.print("✅ Indexing complete:")
            console.print(f"  📄 Documents: {stats.get('total_documents', 0)}")
            console.print(f"  📝 Chunks: {stats.get('total_chunks', 0)}")
            console.print(f"  🧠 Embeddings: {stats.get('chunks_with_embeddings', 0)}")
            console.print(f"  📁 Output: {stats.get('jsonl_path', 'N/A')}")
            
            if config.pinecone.enabled:
                if stats.get('pinecone_upload'):
                    console.print("  🌲 Pinecone: ✅ Upload successful")
                else:
                    console.print("  🌲 Pinecone: ❌ Upload failed")
        
        # Final summary
        elapsed_time = time.time() - start_time
        console.print(f"\n[bold green]🎉 All done! Total time: {elapsed_time:.1f}s[/bold green]")
        
        # Show next steps
        console.print("\n[bold]Next steps:[/bold]")
        if documents:
            console.print(f"  • Review documents in {config.storage.output_jsonl}")
        if config.openai.enabled and config.pinecone.enabled:
            console.print(f"  • Query your vector database using the Pinecone index: {config.pinecone.index_name}")
        console.print(f"  • Check logs in {config.logging.file}")
        
        return 0
        
    except FileNotFoundError as e:
        console.print(f"[red]❌ Configuration file not found: {e}[/red]")
        console.print("[yellow]💡 Copy configs/config.example.yaml to configs/config.yaml[/yellow]")
        return 1
        
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        logging.exception("Unexpected error in main")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]💥 Fatal error: {e}[/red]")
        sys.exit(1)
