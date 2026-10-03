"""
Utilities Module
Helper functions for configuration loading, logging setup, and display utilities.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import colorlog
import pandas as pd
import yaml
from dotenv import load_dotenv
from tabulate import tabulate


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def load_environment():
    """Load environment variables from .env file."""
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        print("Environment variables loaded from .env")
    else:
        print("No .env file found, using system environment variables")


def setup_logging(config: Optional[Dict[str, Any]] = None):
    """
    Set up logging configuration.
    
    Args:
        config: Logging configuration dictionary
    """
    if config is None:
        config = {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'console': True,
            'file': None
        }
    
    log_level = getattr(logging, config.get('level', 'INFO').upper())
    log_format = config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Setup color logging for console
    if config.get('console', True):
        console_handler = colorlog.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(console_handler)
    
    # Setup file logging
    log_file = config.get('file')
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    logging.info("Logging configured successfully")


def display_result(result: Dict[str, Any], format_type: str = "pretty"):
    """
    Display query results in a formatted way.
    
    Args:
        result: Result dictionary from the agent
        format_type: Display format ('pretty', 'simple', 'json')
    """
    print("\n" + "="*80)
    
    if result.get('success'):
        print("✓ Query executed successfully\n")
        print("Result:")
        print("-" * 80)
        
        output = result.get('output', '')
        print(output)
        
        # Display intermediate steps if available
        if result.get('intermediate_steps'):
            print("\n" + "-" * 80)
            print("Intermediate Steps:")
            print("-" * 80)
            for i, step in enumerate(result['intermediate_steps'], 1):
                if isinstance(step, tuple) and len(step) >= 2:
                    action, observation = step[0], step[1]
                    print(f"\nStep {i}:")
                    print(f"  Action: {action}")
                    print(f"  Observation: {observation}")
    else:
        print("✗ Query failed\n")
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("="*80 + "\n")


def display_tables(tables: list, title: str = "Available Tables"):
    """
    Display a list of tables in a formatted way.
    
    Args:
        tables: List of table names
        title: Title for the display
    """
    print(f"\n{title}")
    print("="*80)
    
    if not tables:
        print("No tables found.")
        return
    
    # Display in columns
    num_columns = 3
    rows = [tables[i:i+num_columns] for i in range(0, len(tables), num_columns)]
    
    for row in rows:
        print("  ".join(f"{table:<25}" for table in row))
    
    print(f"\nTotal: {len(tables)} tables")
    print("="*80 + "\n")


def display_table_info(table_info: dict):
    """
    Display detailed information about a table.
    
    Args:
        table_info: Dictionary containing table information
    """
    print(f"\nTable: {table_info['name']}")
    print("="*80)
    
    # Display columns
    print("\nColumns:")
    columns_data = []
    for col in table_info['columns']:
        columns_data.append([
            col['name'],
            str(col['type']),
            'Yes' if col.get('nullable', True) else 'No',
            col.get('default', 'N/A')
        ])
    
    print(tabulate(
        columns_data,
        headers=['Name', 'Type', 'Nullable', 'Default'],
        tablefmt='grid'
    ))
    
    # Display primary keys
    if table_info['primary_keys'].get('constrained_columns'):
        print(f"\nPrimary Keys: {', '.join(table_info['primary_keys']['constrained_columns'])}")
    
    # Display foreign keys
    if table_info['foreign_keys']:
        print("\nForeign Keys:")
        for fk in table_info['foreign_keys']:
            print(f"  {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    
    print("="*80 + "\n")


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate the configuration dictionary.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if valid, raises exception otherwise
    """
    # Check required sections
    required_sections = ['database', 'langchain']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Check database configuration
    db_config = config['database']
    if 'type' not in db_config:
        raise ValueError("Database type not specified in configuration")
    
    # Check LangChain configuration
    lc_config = config['langchain']
    if 'llm' not in lc_config:
        raise ValueError("LLM configuration not specified")
    
    return True


def check_environment_variables() -> Dict[str, bool]:
    """
    Check if required environment variables are set.
    
    Returns:
        Dictionary with variable names and their status
    """
    required_vars = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY') is not None,
        'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY') is not None,
        'GROQ_API_KEY': os.getenv('GROQ_API_KEY') is not None,
        'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY') is not None,
        # Add other required variables as needed
    }
    
    return required_vars


def display_startup_info(config: Dict[str, Any], tables: list):
    """
    Display startup information.
    
    Args:
        config: Configuration dictionary
        tables: List of available tables
    """
    print("\n" + "="*80)
    print(" "*25 + "LangChain SQL Agent")
    print("="*80)
    
    print(f"\nDatabase Type: {config['database']['type']}")
    print(f"LLM Provider: {config['langchain']['llm']['provider']}")
    print(f"LLM Model: {config['langchain']['llm']['model']}")
    print(f"Available Tables: {len(tables)}")
    
    print("\n" + "="*80 + "\n")
