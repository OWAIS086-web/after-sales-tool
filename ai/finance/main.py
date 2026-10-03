"""
Main Application Entry Point
Runs the LangChain SQL Agent with interactive query interface.
"""

import argparse
import logging
import sys
from typing import Optional

from db_manager import DatabaseManager
from sql_agent import SQLAgent
from finance_utils import (check_environment_variables, display_result,
                           display_startup_info, display_tables, load_config,
                           load_environment, setup_logging, validate_config)

logger = logging.getLogger(__name__)


class SQLAgentApplication:
    """Main application class for the SQL Agent."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the application.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = None
        self.db_manager = None
        self.agent = None
    
    def setup(self):
        """Set up the application components."""
        # Load environment variables
        load_environment()
        
        # Load configuration
        logger.info("Loading configuration...")
        self.config = load_config(self.config_path)
        validate_config(self.config)
        
        # Setup logging
        logging_config = self.config.get('logging', {})
        setup_logging(logging_config)
        
        # Check environment variables
        env_vars = check_environment_variables()
        provider = self.config.get('langchain', {}).get('llm', {}).get('provider', 'openai').lower()
        
        # Check for appropriate API key based on provider
        if provider == 'openai' and not env_vars.get('OPENAI_API_KEY'):
            logger.warning("OPENAI_API_KEY not found in environment variables")
            print("\n⚠️  Warning: OPENAI_API_KEY not set. Please set it in your .env file or environment.")
        elif provider == 'gemini' and not env_vars.get('GOOGLE_API_KEY'):
            logger.warning("GOOGLE_API_KEY not found in environment variables")
            print("\n⚠️  Warning: GOOGLE_API_KEY not set. Please set it in your .env file or environment.")
        elif provider == 'groq' and not env_vars.get('GROQ_API_KEY'):
            logger.warning("GROQ_API_KEY not found in environment variables")
            print("\n⚠️  Warning: GROQ_API_KEY not set. Please set it in your .env file or environment.")
        elif provider == 'deepseek' and not env_vars.get('DEEPSEEK_API_KEY'):
            logger.warning("DEEPSEEK_API_KEY not found in environment variables")
            print("\n⚠️  Warning: DEEPSEEK_API_KEY not set. Please set it in your .env file or environment.")
        
        # Initialize database manager
        logger.info("Initializing database manager...")
        self.db_manager = DatabaseManager(self.config['database'])
        
        # Test database connection
        if not self.db_manager.test_connection():
            raise RuntimeError("Failed to connect to database")
        
        # Initialize SQL agent
        logger.info("Initializing SQL agent...")
        self.agent = SQLAgent(self.db_manager, self.config['langchain'])
        self.agent.initialize()
        
        # Display startup information
        tables = self.agent.get_available_tables()
        display_startup_info(self.config, tables)
        
        logger.info("Application setup completed successfully")
    
    def run_single_query(self, question: str):
        """
        Run a single query and display the result.
        
        Args:
            question: Natural language question
        """
        result = self.agent.query(question)
        display_result(result)
    
    def run_interactive(self):
        """Run the agent in interactive mode."""
        print("Interactive SQL Agent Mode")
        print("Type your questions in natural language.")
        print("Commands: 'tables' - show tables, 'quit'/'exit' - quit application\n")
        
        while True:
            try:
                # Get user input
                question = input("📝 Enter your question: ").strip()
                
                if not question:
                    continue
                
                # Handle special commands
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye! 👋")
                    break
                
                elif question.lower() == 'tables':
                    tables = self.agent.get_available_tables()
                    display_tables(tables)
                    continue
                
                elif question.lower() == 'info':
                    print("\nTable Information:")
                    print(self.agent.get_table_info())
                    continue
                
                elif question.lower() == 'help':
                    self.display_help()
                    continue
                
                # Process the query
                result = self.agent.query(question)
                display_result(result)
            
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Goodbye! 👋")
                break
            
            except Exception as e:
                logger.error(f"Error in interactive mode: {e}")
                print(f"\n❌ Error: {e}\n")
    
    def display_help(self):
        """Display help information."""
        help_text = """
╔════════════════════════════════════════════════════════════════════════════╗
║                           SQL Agent Help                                   ║
╚════════════════════════════════════════════════════════════════════════════╝

Commands:
  tables          - Show all available tables
  info            - Show detailed table information
  help            - Show this help message
  quit/exit/q     - Exit the application

Example Questions:
  • "How many records are in the customers table?"
  • "Show me the top 5 products by sales"
  • "What is the total revenue for last month?"
  • "List all customers from New York"
  • "What are the column names in the orders table?"

Tips:
  • Be specific in your questions
  • You can reference multiple tables in a single question
  • The agent will automatically generate and execute SQL queries
  • Results are limited to improve performance
        """
        print(help_text)
    
    def cleanup(self):
        """Clean up resources."""
        if self.db_manager:
            self.db_manager.close()
        logger.info("Application cleanup completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LangChain SQL Agent - Natural Language Database Interface"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--query',
        type=str,
        help='Run a single query and exit'
    )
    parser.add_argument(
        '--tables',
        action='store_true',
        help='List all available tables and exit'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize application
        app = SQLAgentApplication(config_path=args.config)
        app.setup()
        
        # Handle different modes
        if args.tables:
            # Show tables and exit
            tables = app.agent.get_available_tables()
            display_tables(tables)
        
        elif args.query:
            # Run single query and exit
            app.run_single_query(args.query)
        
        else:
            # Run interactive mode
            app.run_interactive()
        
        # Cleanup
        app.cleanup()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye! 👋")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
