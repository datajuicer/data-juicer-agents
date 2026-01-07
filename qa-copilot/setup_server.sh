#!/bin/bash
set -euo pipefail
export DJ_HOME_PATH="/home/test/data-juicer-home"
mkdir -p "$DJ_HOME_PATH"

# Helper: add unique lines from a file to root .gitignore
add_gitignore_rules() {
  local source_file="$1"
  local root_ignore="$DJ_HOME_PATH/.gitignore"

  # Ensure root .gitignore exists
  touch "$root_ignore"

  # Read each line from source, skip empty/comment, add if not already present
  while IFS= read -r line || [[ -n "$line" ]]; do
    trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ -z "$trimmed" ]] || [[ "$trimmed" == \#* ]]; then
      continue
    fi
    # Only append if not already in the current root .gitignore
    if ! grep -Fxq "$trimmed" "$root_ignore" 2>/dev/null; then
      echo "$trimmed" >> "$root_ignore"
    fi
  done < "$source_file"

  rm -f "$temp_file"
}

clone_if_missing() {
  local dir_name="$1"
  local repo_url="$2"
  local target_dir="$DJ_HOME_PATH/$dir_name"

  if [[ -d "$target_dir/.git" ]]; then
    echo "[OK] already exist: $target_dir"
  else
    echo "[DO] It doesn't exist. Start cloning: $repo_url -> $target_dir"
    git clone --depth 1 "$repo_url" "$target_dir"

    # If the cloned repo has a .gitignore, merge its rules into root .gitignore
    # Skip this step if dir_name is "data-juicer-agents"
    if [[ "$dir_name" != "data-juicer-agents" ]]; then
      local repo_gitignore="$target_dir/.gitignore"
      if [[ -f "$repo_gitignore" ]]; then
        echo "[INFO] Adding .gitignore rules from $dir_name"
        add_gitignore_rules "$repo_gitignore"
      fi
    fi
  fi
}

# Clone repos — each new clone will auto-contribute to root .gitignore
clone_if_missing "data-juicer"          "https://github.com/datajuicer/data-juicer.git"
clone_if_missing "data-juicer-sandbox"  "https://github.com/datajuicer/data-juicer-sandbox.git"
clone_if_missing "data-juicer-agents"   "https://github.com/datajuicer/data-juicer-agents.git"
clone_if_missing "data-juicer-hub"      "https://github.com/datajuicer/data-juicer-hub.git"

export DISABLE_DATABASE=1 # Set to 1 to disable database

echo "DJ_HOME_PATH: $DJ_HOME_PATH"
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

# Logs
export DJ_COPILOT_ENABLE_LOGGING="${DJ_COPILOT_ENABLE_LOGGING:-false}"

echo "🚀 Starting QA Copilot Web Server..."
python app_deploy.py
