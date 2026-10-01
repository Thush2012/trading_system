import subprocess
import time
import sys
import os
from dotenv import load_dotenv

# Ensure local environment variables are loaded
load_dotenv()

from core.logger import setup_system_logger
from core.notifier import TelegramNotifier
from core.config import Config

log = setup_system_logger("DeployWatcher")
notifier = TelegramNotifier(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_current_git_hash() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_DIR)
        return out.decode().strip()
    except Exception as e:
        log.error(f"Failed to read local git hash: {e}")
        return ""

def check_for_updates() -> bool:
    try:
        # Check remote main branch without applying changes
        subprocess.check_call(["git", "fetch", "origin", "main"], cwd=PROJECT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_DIR).decode().strip()
        remote_hash = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=PROJECT_DIR).decode().strip()
        return local_hash != remote_hash
    except Exception as e:
        log.error(f"Git remote check error: {e}")
        return False

def pull_latest_code() -> str:
    subprocess.check_call(["git", "pull", "origin", "main"], cwd=PROJECT_DIR)
    return get_current_git_hash()[:7]

def main():
    log.info("Continuous deployment watcher online. Monitoring GitHub repo...")
    python_bin = sys.executable

    # Spawn main.py as a detached background process
    bot_proc = subprocess.Popen([python_bin, "main.py"], cwd=PROJECT_DIR)
    current_commit = get_current_git_hash()[:7]

    notifier.send_alert(
        f"🚀 *Zero-Window Background Engine Live*\n\n"
        f"• Commit Version: `{current_commit}`\n"
        f"• Auto-deploy: Polling GitHub every 60s\n"
        f"• UI: 100% headless via Telegram"
    )

    while True:
        try:
            time.sleep(60)

            # Health auto-recovery: restart if main.py unexpectedly terminated
            if bot_proc.poll() is not None:
                log.warning("Trading process exited unexpectedly. Restarting engine...")
                bot_proc = subprocess.Popen([python_bin, "main.py"], cwd=PROJECT_DIR)

            # Check for new GitHub commits
            if check_for_updates():
                log.info("New commit detected on GitHub. Hot-reloading...")
                notifier.send_alert("📦 *Update Detected on GitHub*\nPulling new changes and restarting engine...")

                # Graceful termination
                bot_proc.terminate()
                try:
                    bot_proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    bot_proc.kill()

                # Pull fresh code
                new_commit = pull_latest_code()

                # Update any modified pip dependencies
                req_file = os.path.join(PROJECT_DIR, "requirements.txt")
                if os.path.exists(req_file):
                    subprocess.call([python_bin, "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_DIR)

                # Spin up new instance with updated code
                bot_proc = subprocess.Popen([python_bin, "main.py"], cwd=PROJECT_DIR)
                notifier.send_alert(f"✅ *Hot-Reload Complete*\n• Engine active on commit: `{new_commit}`")

        except Exception as err:
            log.error(f"Watcher loop exception: {err}")
            time.sleep(10)

if __name__ == "__main__":
    main()