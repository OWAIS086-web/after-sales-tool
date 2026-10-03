#!/bin/bash
# Redis Setup Script for Production Conversational Memory
# Run this script to install and configure Redis on your TensorDock Linux instance

set -e  # Exit on error

echo "======================================================================"
echo "Redis Setup for Production Conversational Memory"
echo "======================================================================"
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This script is designed for Linux systems (TensorDock)"
    echo "For Windows, please use: https://github.com/microsoftarchive/redis/releases"
    exit 1
fi

# Check if Redis is already installed
if command -v redis-server &> /dev/null; then
    echo "✅ Redis is already installed"
    redis-server --version
    echo ""
else
    echo "📦 Installing Redis..."
    echo ""

    # Update package list
    sudo apt-get update -qq

    # Install Redis
    sudo apt-get install -y redis-server

    echo "✅ Redis installed successfully"
    redis-server --version
    echo ""
fi

# Configure Redis for production
echo "⚙️  Configuring Redis..."

# Backup original config
if [ ! -f /etc/redis/redis.conf.backup ]; then
    sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
    echo "   Backed up original config to /etc/redis/redis.conf.backup"
fi

# Set maxmemory policy (evict old sessions when memory is full)
sudo sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
echo "   Set maxmemory policy to allkeys-lru (evict old sessions first)"

# Set maxmemory limit (256MB for conversation memory)
if ! grep -q "^maxmemory 256mb" /etc/redis/redis.conf; then
    echo "maxmemory 256mb" | sudo tee -a /etc/redis/redis.conf > /dev/null
    echo "   Set maxmemory limit to 256MB"
fi

# Enable persistence (save sessions to disk)
sudo sed -i 's/^# save ""/save 900 1\nsave 300 10\nsave 60 10000/' /etc/redis/redis.conf
echo "   Enabled RDB persistence (sessions saved to disk)"

# Restart Redis to apply changes
echo ""
echo "🔄 Restarting Redis..."
sudo systemctl restart redis-server

# Enable Redis to start on boot
sudo systemctl enable redis-server
echo "   Enabled Redis to start on boot"

# Check Redis status
echo ""
echo "📊 Redis Status:"
sudo systemctl status redis-server --no-pager | head -10

# Test Redis connection
echo ""
echo "🧪 Testing Redis connection..."
if redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis is running and responding"
else
    echo "❌ Redis is not responding"
    exit 1
fi

# Display Redis info
echo ""
echo "📈 Redis Memory Usage:"
redis-cli info memory | grep -E "used_memory_human|maxmemory_human"

echo ""
echo "======================================================================"
echo "✅ Redis setup complete!"
echo "======================================================================"
echo ""
echo "Redis is now ready for production conversational memory."
echo ""
echo "Configuration:"
echo "  - Maxmemory: 256MB (adjust if needed in /etc/redis/redis.conf)"
echo "  - Eviction policy: allkeys-lru (removes oldest sessions first)"
echo "  - Persistence: RDB snapshots enabled"
echo "  - Auto-start: Enabled (starts on system boot)"
echo ""
echo "Useful commands:"
echo "  - Check status:  sudo systemctl status redis-server"
echo "  - Restart:       sudo systemctl restart redis-server"
echo "  - Stop:          sudo systemctl stop redis-server"
echo "  - Monitor:       redis-cli monitor"
echo "  - Stats:         redis-cli info"
echo ""
echo "Your conversational memory system is ready to use!"
echo "======================================================================"
