#!/bin/bash
export DATA_JUICER_PATH="/home/test/data-juicer"
export DISABLE_DATABASE=1 # Set to 1 to disable database

echo "DATA_JUICER_PATH: $DATA_JUICER_PATH"
echo "DISABLE_DATABASE: $DISABLE_DATABASE"

if [ "$DISABLE_DATABASE" != "1" ]; then
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
        echo "🚀 Starting Redis server..."
        redis-server --daemonize yes --port 6379
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
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis connection test successful"
    else
        echo "❌ Redis connection test failed"
        exit 1
    fi
fi


echo "🚀 Starting QA Copilot Web Server..."
python app_deploy.py