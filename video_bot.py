import logging
import os
import yt_dlp
import requests
import io
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Replace with your Telegram Bot Token
TOKEN = "8105395287:AAHp4GSSoAFolqeUxU8mKmgv8UIjlAt9iRw"

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Setup: SQLite
DB_NAME = "videos.db"

def init_db():
    """Initialize the SQLite database and create table if not exists."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            video_url TEXT,
            file_name TEXT,
            download_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_download(original_url, video_url, file_name):
    """Insert a download record into the database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO downloads (original_url, video_url, file_name, download_date)
        VALUES (?, ?, ?, ?)
    ''', (original_url, video_url, file_name, download_date))
    conn.commit()
    conn.close()

# Selenium setup (Headless Chrome)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when user sends /start"""
    await update.message.reply_text("Hi! Send me a URL, and I'll try to download the video from it!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message when user sends /help"""
    await update.message.reply_text("Just send me a URL, and I'll extract the video from the page and log it into our database!")

def extract_video_url(url):
    """
    Try to extract a direct video URL from a page using yt-dlp.
    This supports many popular video sites.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
    
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "extract_flat": False,
        "format": "best",  # Best available quality
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info.get("url")
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
    
    return None

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming URL message, extract video, download it, log to database, and send back to user."""
    original_url = update.message.text
    await update.message.reply_text("🔍 Extracting video... Please wait!")

    video_url = extract_video_url(original_url)

    if not video_url:
        await update.message.reply_text("❌ Couldn't find any video on this page!")
        return

    await update.message.reply_text(f"✅ Found video: {video_url}\nDownloading now...")

    # Download video in chunks (handles large files)
    response = requests.get(video_url, stream=True)
    video_file = io.BytesIO()
    
    for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
        if chunk:
            video_file.write(chunk)
    
    video_file.seek(0)  # Reset pointer for Telegram
    file_name = "video.mp4"
    video_file.name = file_name

    # Log the download to the SQLite database
    insert_download(original_url, video_url, file_name)

    # Send video to user
    await update.message.reply_video(video=video_file, caption="📥 Here's your downloaded video!")

def main():
    """Start the bot and initialize the database."""
    init_db()  # Create the database and table if they don't exist

    application = Application.builder().token(TOKEN).build()

    # Add handlers for commands and messages
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
