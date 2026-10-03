# 🚀 After-Sales Tool (Lucid Marketing Intelligence)

A powerful AI-driven conversational intelligence platform for after-sales management and customer engagement. Built with advanced NLP, multi-platform data aggregation, and intelligent query processing.

**Status:** Production-Ready | **Version:** 1.0.0 | **License:** Proprietary

---

## 📋 Features

### 🤖 AI Intelligence
- **Multi-Model LLM Integration**: Support for OpenAI, Google Gemini, Groq, and Grok APIs
- **Advanced Query Classification**: Automatic intent detection and query routing
- **DMS Engine**: Intelligent data management system with multi-tier query decomposition
- **Cross-Platform Aggregation**: Unified data retrieval from multiple sources (Reddit, PakWheels, WhatsApp)
- **Semantic Caching**: Efficient result caching with semantic similarity matching

### 📊 Data Management
- **Vector Database**: ChromaDB-powered RAG (Retrieval-Augmented Generation)
- **SQL Query Generation**: AI-powered SQL generation with validation
- **Entity Extraction**: Intelligent extraction of dates, filters, and business entities
- **Multi-Database Support**: MSSQL, SQLite with abstraction layer

### 🌐 Multi-Channel Integration
- **Reddit Integration**: Real-time data scraping and analysis
- **WhatsApp Integration**: Conversation management and sentiment analysis
- **PakWheels Integration**: Vehicle marketplace data aggregation
- **Email Pipeline**: Automated email processing and analysis

### 🔐 Security & Scalability
- **Docker Deployment**: Containerized production setup
- **Redis Caching**: High-performance session and data caching
- **GitHub Actions CI/CD**: Automated testing and deployment
- **Self-Hosted Runner**: Secure on-premise deployment support
- **Role-Based Access Control**: User authentication and authorization

### 📈 Admin Dashboard
- **Scheduler Management**: Configure automated tasks and workflows
- **Analytics**: Real-time insights and performance metrics
- **Configuration Management**: Dynamic system configuration
- **Error Monitoring**: Centralized error tracking and notifications

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask with Flask-SocketIO for real-time updates
- **LLM Integration**: LangChain, Transformers, sentence-transformers
- **Data Processing**: SQLAlchemy, Pandas, OpenPyXL
- **Vector DB**: ChromaDB with ONNX embeddings
- **Caching**: Redis

### Frontend
- **Templates**: Jinja2
- **Real-time Communication**: Socket.IO
- **Static Assets**: JavaScript, CSS

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **CI/CD**: GitHub Actions
- **Databases**: MSSQL Server, SQLite
- **Deployment**: Self-hosted runners, Cloud-ready

### ML/NLP
- **Transformers**: Hugging Face transformers library
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLMs**: OpenAI GPT, Google Gemini, Groq, Grok APIs
- **Web Scraping**: Beautiful Soup, Selenium, PRAW

---

## 📦 Installation

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- Redis
- MSSQL Server (for DMS engine) or SQLite (for development)
- Git

### Local Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/OWAIS086-web/after-sales-tool.git
cd after-sales-tool
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and database credentials
```

5. **Start Redis (required)**
```bash
# Option 1: Using Docker
docker run -d -p 6379:6379 redis:latest

# Option 2: Using local Redis installation
redis-server
```

6. **Initialize database**
```bash
python seed_dealership_data.py
```

7. **Run the application**
```bash
python app.py
```

Access at: http://localhost:5000

---

## 🐳 Docker Deployment

### Quick Start with Docker Compose
```bash
docker-compose up -d
```

This starts:
- Flask application (port 10000)
- Redis cache (port 6379)

### Production Deployment
```bash
# Build image
docker build -t after-sales-tool:latest .

# Run with environment variables
docker run -d \
  -p 10000:10000 \
  -e FLASK_ENV=production \
  -e OPENAI_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --name after-sales-tool \
  after-sales-tool:latest
```

---

## ⚙️ Configuration

### Environment Variables
```bash
# LLM APIs
OPENAI_API_KEY=your_openai_key
XAI_API_KEY=your_grok_key
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key

# Database (MSSQL for production, SQLite for dev)
DMS_MSSQL_SERVER=mssql-server
DMS_MSSQL_DATABASE=SazgarDMSDW
DMS_MSSQL_USERNAME=dmsai
DMS_MSSQL_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_app_password
FROM_EMAIL=noreply@yourdomain.com

# Flask
FLASK_ENV=development  # or production
DEBUG=False
```

### Configuration Files
- `config/config.yml` - System configuration (scheduler, logging, database)
- `.env` - Environment secrets

---

## 📚 Project Structure

```
after-sales-tool/
├── ai/
│   ├── conversation_manager.py       # Chat history management
│   ├── cross_platform/               # Multi-source data aggregation
│   ├── dealership_engine/            # Dealership-specific logic
│   ├── dms_engine/                   # Data management system
│   │   ├── agents/                   # Query agents (router, decomposition, etc.)
│   │   ├── metadata/                 # Schema metadata management
│   │   └── dms_pipeline.py           # Main DMS orchestration
│   └── dms_engine_sqlite/            # SQLite variant for development
│
├── controllers/                      # Route controllers
├── models/                           # Database models
├── services/                         # Business logic services
├── middleware/                       # Flask middleware
├── utils/                            # Utility functions
├── templates/                        # Jinja2 templates
├── static/                           # CSS, JavaScript, images
├── data/                             # ChromaDB, pickled data, SQLite
├── logs/                             # Application logs
├── config/                           # Configuration files
├── scheduler/                        # Task scheduling
├── test/                             # Test suite
├── Dockerfile                        # Docker image definition
├── docker-compose.yml                # Docker Compose configuration
├── requirements.txt                  # Python dependencies
├── app.py                            # Flask application entry point
└── README.md                         # This file
```

---

## 🚀 API Endpoints

### Chat Endpoints
- `POST /api/chat` - Send message and get response
- `GET /api/chat/history` - Retrieve chat history
- `DELETE /api/chat/clear` - Clear chat session

### Data Endpoints
- `GET /api/data/dealership` - Fetch dealership data
- `GET /api/data/customers` - Get customer data
- `GET /api/data/vehicles` - List vehicles
- `POST /api/data/search` - Advanced search

### Admin Endpoints
- `GET /admin/dashboard` - Admin dashboard
- `GET /admin/scheduler` - Scheduler configuration
- `POST /admin/scheduler/update` - Update scheduler settings
- `GET /admin/logs` - View application logs
- `GET /admin/health` - System health check

---

## 🧪 Testing

Run tests with pytest:
```bash
# All tests
pytest test/

# Specific test file
pytest test/test_query_classifier.py

# With coverage
pytest test/ --cov=ai --cov-report=html
```

---

## 📖 Documentation

- [Server Setup Guide](./SERVER_SETUP.md) - Production deployment documentation
- [DMS Engine README](./ai/dms_engine/README.md) - Data management system details
- [API Documentation](./docs/) - Detailed API reference

---

## 🔄 CI/CD Pipeline

GitHub Actions workflow automatically:
1. Runs tests on every push
2. Builds Docker image
3. Pushes to Docker Hub
4. Deploys to production server

Trigger deployment with git push:
```bash
git push origin main
```

---

## 🐛 Troubleshooting

### Common Issues

**Redis Connection Error**
```bash
# Ensure Redis is running
redis-cli ping  # Should return PONG

# Or with Docker
docker ps | grep redis
```

**Database Connection Error**
```bash
# Check MSSQL/SQLite connection
python -c "from ai.dms_engine.db_adapter import get_db_connection; conn = get_db_connection(); print('Connected!')"
```

**LLM API Errors**
- Verify API keys in `.env`
- Check API rate limits and quota
- Confirm internet connectivity

### View Logs
```bash
# Application logs
tail -f logs/app.log

# With Docker
docker logs -f after-sales-tool
```

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit pull request

---

## 📄 License

This project is proprietary and confidential. Unauthorized copying or distribution is prohibited.

---

## 👥 Team

- **Project Lead**: Obaidullah Nasir
- **Architecture**: Enterprise AI Solutions
- **Deployment**: Production Server (Lahore Office)

---

## 📞 Support

For issues, questions, or contributions, please:
1. Check existing [issues](https://github.com/OWAIS086-web/after-sales-tool/issues)
2. Create new issue with detailed description
3. Contact the development team

---

## 🎯 Roadmap

- [x] Multi-LLM support
- [x] Cross-platform data aggregation
- [x] DMS engine with query decomposition
- [x] Redis caching layer
- [x] Docker deployment
- [x] GitHub Actions CI/CD
- [ ] Advanced analytics dashboard
- [ ] Real-time notifications
- [ ] Mobile app integration
- [ ] Multi-language support

---

**Last Updated**: January 2026 | **Version**: 1.0.0

Made with ❤️ by the Enterprise AI team
