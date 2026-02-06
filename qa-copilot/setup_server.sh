#!/bin/bash

# Session store type: "json" (default) or "redis"
export SESSION_STORE_TYPE="${SESSION_STORE_TYPE:-json}"

echo "SESSION_STORE_TYPE: $SESSION_STORE_TYPE"

# Check required environment variables
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "❌ Error: DASHSCOPE_API_KEY is required but not set"
    echo "   Please export DASHSCOPE_API_KEY before running this script"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITHUB_TOKEN is required but not set"
    echo "   Please export GITHUB_TOKEN before running this script"
    exit 1
fi

# Setup Redis if SESSION_STORE_TYPE is "redis"
if [ "$SESSION_STORE_TYPE" = "redis" ]; then
    echo "🔧 Redis mode enabled, setting up Redis..."
    
    # Set Redis configuration defaults if not provided
    export REDIS_HOST="${REDIS_HOST:-localhost}"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export REDIS_DB="${REDIS_DB:-0}"
    export REDIS_MAX_CONNECTIONS="${REDIS_MAX_CONNECTIONS:-10}"
    
    echo "   REDIS_HOST: $REDIS_HOST"
    echo "   REDIS_PORT: $REDIS_PORT"
    echo "   REDIS_DB: $REDIS_DB"
    
    # Check if Redis is installed
    if ! command -v redis-server &> /dev/null; then
        echo "📦 Installing Redis..."
        if command -v apt-get &> /dev/null; then
            # Ubuntu/Debian
            sudo apt-get update
            sudo apt-get install -y redis-server
        elif command -v yum &> /dev/null; then
            # CentOS/RHEL
            sudo yum install -y redis
        elif command -v brew &> /dev/null; then
            # macOS
            brew install redis
        else
            echo "❌ Unsupported package manager. Please install Redis manually."
            exit 1
        fi
        echo "✅ Redis installed successfully"
    else
        echo "✅ Redis is already installed"
    fi

    # Check if Redis is running
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "🚀 Starting Redis server on port $REDIS_PORT..."
        redis-server --daemonize yes --port "$REDIS_PORT"
        sleep 2
        
        # Verify Redis is running
        if pgrep -x "redis-server" > /dev/null; then
            echo "✅ Redis server started successfully"
        else
            echo "❌ Failed to start Redis server"
            exit 1
        fi
    else
        echo "✅ Redis server is already running"
    fi

    # Test Redis connection
    if redis-cli -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "✅ Redis connection test successful"
    else
        echo "❌ Redis connection test failed"
        echo "   Please check if Redis is running on port $REDIS_PORT"
        exit 1
    fi
else
    echo "📁 JSON mode enabled (default)"
    echo "   Session files will be stored in: ${SESSION_STORE_DIR:-./sessions}"
    echo "   TTL: ${SESSION_TTL_SECONDS:-21600} seconds"
    echo "   Cleanup interval: ${SESSION_CLEANUP_INTERVAL:-1800} seconds"
fi

# Logs configuration
export DJ_COPILOT_ENABLE_LOGGING="${DJ_COPILOT_ENABLE_LOGGING:-false}"

echo "🚀 Starting QA Copilot Web Server..."
python app_deploy.py
