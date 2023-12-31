from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job
import datetime
import pytz
import mysql.connector
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
user_status = {}
count_koneksi_putus = 0
total_status_down = 0
total_status_up = 0
projectloragroup = -1001607641848  # ID grup ProjectLoraGroup

# Fungsi untuk mengambil data dari database
def get_data_from_database(tanggal_bulan_tahun_str):
    conn = mysql.connector.connect(
        host=config.get('Database', 'host'),
        user=config.get('Database', 'user'),
        password=config.get('Database', 'password'),
        database=config.get('Database', 'database')
    )
    cursor = conn.cursor()

    # Query untuk mengambil data berdasarkan tanggal
    query = "SELECT * FROM data_sensor WHERE tanggal = %s"
    cursor.execute(query, (tanggal_bulan_tahun_str,))

    # Ambil hasil data dari database
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    return data

# Fungsi untuk memasukkan data ke database
def insert_data_to_database(tanggal_bulan_tahun, status_up, status_down, status_lebih_30menit):
    conn = mysql.connector.connect(
        host=config.get('Database', 'host'),
        user=config.get('Database', 'user'),
        password=config.get('Database', 'password'),
        database=config.get('Database', 'database')
    )
    cursor = conn.cursor()

    # Buat objek datetime dari tanggal_bulan_tahun
    tanggal_waktu = datetime.datetime.strptime(tanggal_bulan_tahun, "%Y-%m-%d")

    # Cek apakah data dengan tanggal tertentu sudah ada dalam database
    query_check = "SELECT COUNT(*) FROM data_sensor WHERE tanggal = %s"
    cursor.execute(query_check, (tanggal_waktu,))
    count = cursor.fetchone()[0]

    if count == 0:
        # Jika data dengan tanggal tersebut belum ada, masukkan data baru
        query_insert = """
        INSERT INTO data_sensor (tanggal, status_up, status_down, status_lebih_dari_30_menit) 
        VALUES (%s, %s, %s, %s)
        """
        data_insert = (tanggal_waktu, status_up, status_down, status_lebih_30menit)
        cursor.execute(query_insert, data_insert)
    else:
        # Jika data dengan tanggal tersebut sudah ada, perbarui kolom status
        query_update = """
        UPDATE data_sensor
        SET status_up = %s,
            status_down = %s,
            status_lebih_dari_30_menit = %s
        WHERE tanggal = %s
        """
        data_update = (status_up, status_down, status_lebih_30menit, tanggal_waktu)
        cursor.execute(query_update, data_update)

    conn.commit()

    cursor.close()
    conn.close()

def send_koneksi_putus_message(context):
    global count_koneksi_putus
    user_id = context.job.context
    if user_id in user_status and user_status[user_id]["status"] == "DOWN":
        now = datetime.datetime.now().timestamp()
        if now - user_status[user_id]["timestamp"] >= 20:
            context.bot.send_message(chat_id=projectloragroup, text="Koneksi putus lebih dari 30 menit")
            count_koneksi_putus += 1
            user_status[user_id]["status"] = "DISCONNECTED"
            tanggal_sekarang = datetime.datetime.now().strftime("%Y-%m-%d")
            insert_data_to_database(tanggal_sekarang, total_status_up, total_status_down, count_koneksi_putus)

def send_count_koneksi_putus_message(context):
    global count_koneksi_putus, total_status_down, total_status_up
    now = datetime.datetime.now()
    tanggal_sekarang = now.strftime("%Y-%m-%d")
    context.bot.send_message(chat_id=projectloragroup, text=f"[LAPORAN {tanggal_sekarang}]\nTOTAL >30 Menit: {count_koneksi_putus}\nTOTAL Status DOWN: {total_status_down}\nTOTAL Status UP:{total_status_up}")
    count_koneksi_putus = 0
    total_status_up = 0

def start(update, context):
    update.message.reply_text("Selamat datang")

def forward_message(update, context):
    global total_status_down, total_status_up, count_koneksi_putus
    user_id = update.message.chat_id
    message_text = update.message.text
    print("Received message:", message_text)

    if "DOWN" in message_text.upper():
        if user_id not in user_status or user_status[user_id]["status"] != "DOWN":
            print("Sending message to ProjectLoraGroup...")
            context.bot.send_message(chat_id=projectloragroup, text="Koneksi Terputus❌")
            user_status[user_id] = {"status": "DOWN", "timestamp": datetime.datetime.now().timestamp()}
            context.job_queue.run_repeating(send_koneksi_putus_message, interval=1, first=0, context=user_id)
            total_status_down += 1
            # Simpan data status down ke database
            tanggal_sekarang = datetime.datetime.now().strftime("%Y-%m-%d")
            insert_data_to_database(tanggal_sekarang, total_status_up, total_status_down, count_koneksi_putus)

    elif "UP" in message_text.upper():
        print("Sending message to ProjectLoraGroup...")
        context.bot.send_message(chat_id=projectloragroup, text="Koneksi Kembali Terhubung✅")
        user_status[user_id] = {"status": "UP", "timestamp": datetime.datetime.now().timestamp()}
        context.job_queue.run_repeating(send_koneksi_putus_message, interval=1, first=0, context=user_id)
        total_status_up += 1
        # Simpan data status up ke database
        tanggal_sekarang = datetime.datetime.now().strftime("%Y-%m-%d")
        insert_data_to_database(tanggal_sekarang, total_status_up, total_status_down, count_koneksi_putus)

def report(update, context):
    global total_status_down
    user_input = context.args
    if len(user_input) != 3:
        update.message.reply_text("Format tanggal bulan tahun tidak valid. Gunakan format /report 'tanggal bulan tahun'")
        return

    try:
        tanggal = int(user_input[0])
        bulan = int(user_input[1])
        tahun = int(user_input[2])
        tanggal_bulan_tahun = datetime.datetime(tahun, bulan, tanggal)
        #tanggal_sekarang = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        ####if tanggal_bulan_tahun > tanggal_sekarang:
           ####update.message.reply_text("Tidak ada data")
           #### return  

        tanggal_bulan_tahun_str = tanggal_bulan_tahun.strftime("%Y-%m-%d")

        # Ambil data dari database berdasarkan tanggal
        data = get_data_from_database(tanggal_bulan_tahun_str)

        if data:
            # Jika data ditemukan, gunakan data sesuai dengan format yang diinginkan
            total_status_up = data[1]
            total_status_down = data[2]
            count_koneksi_putus = data[3]

            # Kirim data ke grup ProjectLoraGroup (gunakan data sesuai dengan format yang diinginkan)
            context.bot.send_message(chat_id=projectloragroup, text=f"REPORT {tanggal_bulan_tahun_str}\nTotal >30 Menit  : {count_koneksi_putus}\nTotal Status DOWN: {total_status_down}\nTotal Status UP  : {total_status_up}")
        else:
            # Jika data tidak ditemukan
            update.message.reply_text("Data untuk tanggal yang diminta tidak ditemukan.")

    except ValueError:
        update.message.reply_text("Format tanggal bulan tahun tidak valid. Gunakan format /report 'tanggal bulan tahun'")

def main():
    updater = Updater(token='6385996382:AAFMVIlprDsSmIJXKLO5cXVsvim8RWB-JPY', use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("report", report, pass_args=True))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, forward_message))
    tz = pytz.timezone('Asia/Jakarta')
    job_queue = updater.job_queue
    job_queue.run_daily(send_count_koneksi_putus_message, time=datetime.time(hour=0, minute=7, tzinfo=tz))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

