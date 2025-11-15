# Epica - B2B Procurement Platform with AI Assistant

Django-based SaaS platform for managing customer tickets, supplier quotes, and orders with an intelligent AI assistant.

## 🚀 Tech Stack

- **Backend:** Django 4.2.24 + Python 3.9
- **Database:** PostgreSQL
- **AI:** OpenAI GPT-4o-mini (Function calling)
- **Frontend:** Bootstrap 5 + Bootstrap Icons
- **Deployment:** Nginx + Gunicorn on Ubuntu
- **Domain:** https://epica.com.tr

## 📁 Key Project Structure

```
epica/
├── ai_assistant/              # AI Assistant App
│   ├── services/
│   │   ├── agent.py          # OpenAI agent with function calling
│   │   ├── actions.py        # 9 AI functions (tickets, orders, suppliers)
│   │   ├── retriever.py      # RAG for context retrieval
│   │   └── embedder.py       # Text embeddings
│   ├── models.py             # Conversation, Message, AIAction
│   └── views.py              # Chat API endpoints
├── core/                      # Main business logic
│   ├── models.py             # Ticket, Quote, Supplier, Category
│   └── views.py              # Portal views
├── billing/                   # Orders and invoicing
│   └── models.py             # Order, OrderItem
├── accounts/                  # Multi-tenant auth
│   └── models.py             # Organization, User, Role
└── templates/
    └── ai_assistant/
        └── chat.html         # Chat UI with search/delete features
```

## 🤖 AI Assistant Features

- **9 Functions:** search_tickets, get_ticket_stats, update_ticket_status, search_suppliers, 
  get_supplier_stats, get_quote_stats, search_customer_orders, search_product_orders, get_order_stats
- **Language Detection:** Auto-detects Turkish/English
- **Feedback System:** Thumbs up/down for training
- **Direct Links:** All responses include clickable URLs
- **Category Search:** Search orders by product or category
- **Conversation Management:** Search and delete conversations

## ⚙️ Setup

```bash
# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Add: OPENAI_API_KEY=your_key_here

# Database
python manage.py migrate

# Run server
python manage.py runserver
```

## 🐳 Docker (PostgreSQL)

```bash
docker compose up --build
```

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test ai_assistant
python manage.py test core
```

## 🚀 Deployment

### Production Server
- **Host:** 78.46.162.116 (Hetzner)
- **Path:** /opt/epica
- **Service:** systemd (epica.service)
- **Web Server:** Nginx → Gunicorn (port 8000)
- **SSL:** Let's Encrypt (certbot)

### Deploy Commands

```bash
# Quick deploy (use VS Code task "Deploy to Production")
ssh -i ~/.ssh/id_ed25519_lethe_epica root@78.46.162.116 \
  'cd /opt/epica && git pull && source venv/bin/activate && \
   python manage.py collectstatic --noinput && systemctl restart epica'

# Check service status
ssh -i ~/.ssh/id_ed25519_lethe_epica root@78.46.162.116 \
  'systemctl status epica'

# View logs
ssh -i ~/.ssh/id_ed25519_lethe_epica root@78.46.162.116 \
  'journalctl -u epica -f'
```

## 🔧 VS Code Tasks

Use Command Palette (Cmd+Shift+P) → "Run Task":
- `Run Django Server` - Start development server
- `Run Tests` - Execute test suite
- `Make Migrations` - Create database migrations
- `Migrate Database` - Apply migrations
- `Deploy to Production` - One-click deploy
- `Git Push and Deploy` - Push and auto-deploy

## 📊 AI Assistant API Endpoints

```
GET  /ai/                           - Chat interface
POST /ai/                           - Create new conversation
POST /ai/send/<conversation_id>/   - Send message to AI
GET  /ai/conversation/<id>/        - Get conversation history
DELETE /ai/chat/<id>/delete/       - Delete conversation
POST /ai/message/<id>/feedback/    - Submit feedback (thumbs up/down)
```

## 🎯 AI Functions Reference

| Function | Description | Parameters |
|----------|-------------|------------|
| `search_tickets` | Search tickets by query/status | query, status, limit |
| `get_ticket_stats` | Get ticket statistics | period |
| `update_ticket_status` | Change ticket status | ticket_id, new_status |
| `search_suppliers` | Find suppliers by name | query |
| `get_supplier_stats` | Supplier count by category | - |
| `get_quote_stats` | Quote stats by supplier | period |
| `search_customer_orders` | Find orders by customer | customer_name |
| `search_product_orders` | Find orders by product/category | product_query |
| `get_order_stats` | Order statistics | period |

## 🔑 Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=epica.com.tr,www.epica.com.tr

# Database
DATABASE_URL=postgres://user:pass@localhost/epica

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## 📝 Contributing

For AI Agent to work better in VS Code:
1. Use `@workspace` mention for project-wide context
2. Reference specific files: `@ai_assistant/services/actions.py`
3. Provide clear, specific instructions
4. All settings are in `.vscode/` folder

## 📄 License

MIT
