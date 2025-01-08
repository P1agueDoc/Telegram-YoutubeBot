import telebot
import subprocess
import os
import re
import urllib.parse

def sanitize_filename(filename):
    # Replace non-ASCII characters with underscores
    sanitized = re.sub(r'[^\x00-\x7F]+', '_', filename)
    # Remove invalid characters for file paths
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
    return sanitized

def extract_video_id(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.netloc == "youtu.be":
        return parsed_url.path[1:]  # Extract video ID from short URL
    elif parsed_url.netloc in ["www.youtube.com", "youtube.com"]:
        query = urllib.parse.parse_qs(parsed_url.query)
        return query.get("v", [None])[0]  # Extract video ID from query parameter
    return None

def url_download(url, resolution="best[height<=1080]"):
    output_path = os.path.abspath(r"./save")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    
    video_id = extract_video_id(url)
    if not video_id:
        print("Invalid YouTube URL.")
        return None

    
    print("Fetching video title...")
    title_result = subprocess.run(
        ["yt-dlp", "--cookies", "cookies.txt", "--get-title", f"https://www.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True)
    if title_result.returncode != 0:
        print("Error fetching title:", title_result.stderr)
        return None

    video_title = title_result.stdout.strip()
    print("Video title:", video_title)

    
    sanitized_title = sanitize_filename(video_title)
    print("Sanitized title:", sanitized_title)

    
    print(f"Downloading video with resolution: {resolution}...")
    result = subprocess.run(
        ["yt-dlp", "--cookies", "cookies.txt", "--no-playlist", "-f", resolution, "-o", f"{output_path}/{sanitized_title}.%(ext)s", f"https://www.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True)

    
    print("yt-dlp stdout:", result.stdout)
    print("yt-dlp stderr:", result.stderr)

    
    for line in result.stdout.splitlines():
        if line.startswith("[download] Destination:"):
            file_path = line.split("Destination: ")[1].strip()
            print("Downloaded file path:", file_path)
            return file_path
        elif line.startswith("[download]") and "has already been downloaded" in line:
            file_path = line.split("[download] ")[1].strip()
            file_path = file_path.replace(" has already been downloaded", "")
            print("File already exists:", file_path)
            return file_path

    
    print("No file path found in yt-dlp output.")
    return None

# Telegram bot setup
TELEGRAM_BOT_TOKEN = ''
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Здравствуйте, что бы получить видео, напишите /video 'url видео'")


@bot.message_handler(content_types=['text'])
def button_handler(message):
    if '/video ' in message.text or '/video' in message.text:
        bot.send_message(message.chat.id, "**Загружаю**", parse_mode="Markdown")
        message_url_find = message.text
        url_vid = ''
        if '/video ' in message_url_find:
            url_vid += message_url_find.replace('/video ', '')
        elif '/video' in message_url_find:
            url_vid += message_url_find.replace('/video', '')

        print("Received URL:", url_vid)

        # Check if the URL is part of a playlist
        is_playlist_url = "list=" in url_vid
        if is_playlist_url:
            bot.send_message(message.chat.id, "⚠️ Видео является частью плейлиста. Скачиваю только это видео...")

        
        resolution = "best[height<=1080]"
        bot.send_message(message.chat.id, f"🔄 Скачиваю видео в разрешении 1080p...")
        video_path = url_download(url_vid, resolution=resolution)
        print("Downloaded video path:", video_path)


        if video_path and os.path.exists(video_path):
            
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
            print(f"Video size: {file_size:.2f} MB")

            
            bot.send_message(message.chat.id, f"📏 Размер видео: {file_size:.2f} MB\n🎥 Разрешение: 1080p")

            if file_size > 50:  # Telegram's file size limit is 50 MB
                bot.send_message(message.chat.id, "⚠️ Видео слишком большое (>50 MB). Пробую понизить качество...")
                # Try 720p
                resolution = "best[height<=720]"
                bot.send_message(message.chat.id, f"🔄 Скачиваю видео в разрешении 720p...")
                video_path = url_download(url_vid, resolution=resolution)
                file_size = os.path.getsize(video_path) / (1024 * 1024)
                print(f"720p video size: {file_size:.2f} MB")

                
                bot.send_message(message.chat.id, f"📏 Размер видео: {file_size:.2f} MB\n🎥 Разрешение: 720p")

                if file_size > 50:  # If still too big, try 480p
                    bot.send_message(message.chat.id, "⚠️ Видео всё ещё слишком большое. Пробую качество 480p...")
                    resolution = "best[height<=480]"
                    bot.send_message(message.chat.id, f"🔄 Скачиваю видео в разрешении 480p...")
                    video_path = url_download(url_vid, resolution=resolution)
                    file_size = os.path.getsize(video_path) / (1024 * 1024)
                    print(f"480p video size: {file_size:.2f} MB")

                    
                    bot.send_message(message.chat.id, f"📏 Размер видео: {file_size:.2f} MB\n🎥 Разрешение: 480p")

                    if file_size > 50:  # If still too big, give up
                        bot.send_message(message.chat.id, "❌ Не удалось уменьшить размер видео. Пожалуйста, попробуйте другой URL.")
                        print("Video is still too large after lowering resolution.")
                        return

            # Send the video
            try:
                with open(video_path, 'rb') as video_file:
                    bot.send_video(message.chat.id, video_file)
                print("Video sent successfully.")
            except Exception as e:
                # Handle errors when sending the video
                bot.send_message(message.chat.id, f"❌ Ошибка при отправке видео: {e}")
                print(f"Error sending video: {e}")
        else:
            
            bot.send_message(message.chat.id, "❌ Не удалось загрузить видео. Пожалуйста, проверьте URL и попробуйте снова.")
            print("Video download failed or file not found.")


bot.infinity_polling()
