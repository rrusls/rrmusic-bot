import yt_dlp
import asyncio
import logging 
import sys
from os import getenv
import os
import sqlite3, emoji
import time

from aiogram import Bot, Dispatcher, html, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, URLInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from pathlib import Path
from dotenv import load_dotenv


load_dotenv("TOKEN.env")
TOKEN = os.getenv("TOKEN")

dp = Dispatcher()

path = Path(__file__).resolve().parent
directory = path / "downloads"


        
ydl_options = {
    'outtmpl': f"{directory}/%(title)s.%(id)s.%(ext)s",
    'format': 'm4a/bestaudio/best/mp3',
    'forcetitle': True,
    'forceurl': True,
    'skip_download': True,
    'noplaylist': True,
    'noprogress': False,
    'extract_flat': True,
    #'extractor_args': {
    #    'youtube': {
     #       'player_client': ['web_embedded', 'default']
     #   }
    #},
    #'cookiefile': "cookies.txt",
    #'cookiesfrombrowser': ('brave',),
    'verbose': True,
    'ignoreerrors': True,

}




def get_db(db_name="tracks.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    
    return conn

tracks_db = get_db()
cursor = tracks_db.cursor()

def search_tracks(title):
    query = "SELECT * FROM 'tracks' WHERE title LIKE ? ORDER BY title"
    return cursor.execute(query, (f"%{title}%",)).fetchall()
    
def search_by_id(id):
    query = "SELECT * FROM 'tracks' WHERE id = ?"
    search_ = cursor.execute(query,(id,)).fetchone()
    if search_ is not None:
        return search_
    return "not found"

def add_track(id,title,duration,uploader,thumbnail):
    query = "INSERT INTO 'tracks' (id,title,duration,uploader,file_id,thumbnail) VALUES (?,?,?,?,NULL,?)"
    try:
        cursor.execute(query,(id,title,duration,uploader,thumbnail))
        tracks_db.commit()
        return True
    except Exception as error:
        tracks_db.rollback()
        logging.exception(f"Error while adding track: {error}")
        return False
        
    
    
def insert_file_id(id,file_id): 
    query = "UPDATE 'tracks' SET file_id = ? WHERE id = ?"
    try:
        insert = cursor.execute(query, (file_id,id))
        tracks_db.commit()
        
        if cursor.rowcount == 0:
            return False
        return True
    except Exception as error:
        tracks_db.rollback()
        return f"Error while inserting file_id: {error}"
        
        
        
def sort_entries(entries_raw):
    top_results, bottom_results = [], []     
    key_words = ['official', 'music', 'video']
    for entry in entries_raw:
        if entry == None:
            continue
        if any(word in entry['title'].lower() for word in key_words):
            bottom_results.append(entry)
        else:
            top_results.append(entry)
    final_entries_raw = top_results + bottom_results       
    return final_entries_raw


def yt_dlp_search(text,amount=20):
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        searched_results = ydl.extract_info(f"ytsearch{amount}:{text}")
        filtered_searched_results = []
        
        for entry in searched_results['entries']:
            if entry == None:
                continue
            filtered_searched_results.append(entry)
        
        entries_raw = filtered_searched_results
        final_entries_raw = sort_entries(entries_raw)
        
        return final_entries_raw[:10]
    
def give_ext(entries_raw):
    entries = []
    
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        for entry in entries_raw:
            ext = entry.get('ext')
            if not ext:
                entry['ext'] = 'm4a'
            entries.append(entry)
            
    return entries


def download_track(track_url):
    ydl_options = {
    'outtmpl': f"{directory}/%(title)s.%(id)s.%(ext)s",
    'format': 'm4a/bestaudio/best/mp3',
    'forcetitle': True,
    'forceurl': True,
    'noplaylist': True,
    'noprogress': False,
    'ignoreerrors': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        try:
            info = ydl.extract_info(track_url, download=True)
            filename = ydl.prepare_filename(info)
        except Exception as e:
            logging.exception("yt-dlp error with video")
            return f'yt-dlp error with video: {e}'
        
    try:
        return [info['id'], info['title'], info['duration'], info['uploader'], info['thumbnail'], filename]
    except Exception as return_err:
        return f"Error while downloading a track:{return_err}"


def search_fileid_by_id(id):
    query = "SELECT file_id from tracks WHERE id = ?"
    try:
        search_file_id_by_id = cursor.execute(query,(id,)).fetchone()
        return search_file_id_by_id
    except Exception as e:
        return None


async def build_output(db_search, message,amount_to_search):
    db_tracks = len(db_search)
    try:
        if db_tracks > 5:
            to_slice = db_tracks - (db_tracks - 5)
            db_search = db_search[:to_slice]
                        
        dlp_search = await asyncio.to_thread(yt_dlp_search, message.text, amount=amount_to_search)
        builder = InlineKeyboardBuilder()
        
                    
        found_tracks = db_search + dlp_search 
                    
        #removing duplicates
        unique_found_tracks = {}
        for track in found_tracks:
            unique_found_tracks[track['id']] = track
        unique_found_tracks = list(unique_found_tracks.values())
        sorted_unique_found_tracks = sort_entries(unique_found_tracks)
        
        if len(sorted_unique_found_tracks) == 0:
            await message.answer(f"I'm sorry, nothing found :( Please rephrase your request")
            return
                    
        for track in sorted_unique_found_tracks:
            builder.button(text = f"{track['title']}", callback_data = track['id'])
                        
        builder.adjust(1,1)
                    
        await message.answer(f"Results for: {message.text}", reply_markup=builder.as_markup())
    except Exception as e:
        await message.answer(f"Error with yt-dlp search: {e}")



@dp.message(CommandStart())
async def command_start_handler(message: Message):
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}! Hit the /about to get to know me better.")


@dp.message(Command("about"))
async def command_about_handler(message: Message):
    await message.answer(f"I'm the rrMusic Bot. I help you search for a music you like. For more accurate answers please text me in the format like 'Performer - Track Name'.")
    
    
# Main functions
@dp.message()
async def handle_message(message: Message) -> None:
    if message.content_type != "text" or emoji.emoji_count(message.text) != 0:
        await message.answer("Nothing found. Please make a new request.")
        return
    else:
        await message.answer("Searching...")

    db_search = search_tracks(message.text)
    constamount = 10
    
    try:
        await build_output(db_search, message, constamount)
    except Exception as e:
        await message.answer(f"Error with building keyboard of output: {e}")


@dp.callback_query()
async def send_m4a(callback: types.CallbackQuery)->None:
    await callback.answer()
    id = callback.data
    file_id = search_fileid_by_id(id)
    
    if file_id is None:
        file_id = None
    else:
        file_id = file_id['file_id']
    if file_id is None:
        await callback.message.answer("Downloading...")
        try:
            track_url = f'https://youtube.com/watch?v={id}'
            t = time.perf_counter()
            download = await asyncio.to_thread(download_track, track_url)
            if isinstance(download, str):
                await callback.message.answer("Error while downloading audio. Probably, this video is unavaliable.")
            elif type(download) == list:
                audio_file = FSInputFile(download[-1])
                title = download[1]
                duration = download[2]
                
                if '-' in title or ' – ' in title:
                    title = title.replace(' – ', ' - ')
                    title = title.split(' - ',1)
                    performer = title[0]
                    title = title[1]
                else:
                    performer = download[3]

                thumbnail_link = download[4]
                thumbnail = URLInputFile(thumbnail_link, filename="track-thumbnail")
                
                try:
                    sent_audio = await callback.message.answer_audio(audio=audio_file,title=title, duration=duration, performer=performer,
                                                                 thumbnail=thumbnail)
                    
                except Exception as thumbnail_error:
                    logging.warning(f"Thumbnail upload failed, retrying without it: {thumbnail_error}")
                    sent_audio = await callback.message.answer_audio(audio=audio_file, title=title, duration=duration, performer = performer)                    
                generated_file_id = sent_audio.audio.file_id
                
                try:
                    adding = add_track(id,title,duration,performer,thumbnail_link)
                    if adding:
                        insert_file_id_attempt = insert_file_id(id, generated_file_id)
                        if not insert_file_id_attempt:
                            await callback.message.answer("Error while inserting by a file id")
                except Exception as insert_file_id_err:
                    await callback.message.answer(f"Error while inserting 'file_id' to a new track OR adding a track to db: {insert_file_id_err}")

        except Exception as downloaded_track_err:
            await callback.message.answer(f"Error with downloaded track: {downloaded_track_err}")

    else:
        try:
            sent_audio = await callback.message.answer_audio(audio=file_id)
        except Exception as sent_m4a_by_file_id:
            await callback.message.answer(f"Error while sending m4a by 'file_id':{sent_m4a_by_file_id}")
        
                        

async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())