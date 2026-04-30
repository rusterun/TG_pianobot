from telebot import TeleBot, types
from time import sleep
import openpyxl, sqlite3, json, datetime
import pandas as pd
import numpy as np
from openpyxl.styles.borders import Border, Side
from openpyxl.styles import Font
import os

DB_PATH = "database.db"



os_admin_id = os.getenv("ADMIN_ID")
token = os.getenv("BOT_TOKEN")

bot = TeleBot(token) # токен из BotFather в tg, задаётся во время запуска бота через docker

auth_dict = {

    "admin_name": "Administrator",
    "admin_id": int(os_admin_id)
}

def db_connect():
    return sqlite3.connect(DB_PATH)


def fetch_one(query, params=()):
    with db_connect() as connection:
        return connection.execute(query, params).fetchone()


def fetch_all(query, params=()):
    with db_connect() as connection:
        return connection.execute(query, params).fetchall()


def execute_query(query, params=()):
    with db_connect() as connection:
        cursor = connection.execute(query, params)
        connection.commit()
        return cursor


def execute_insert(query, params=()):
    with db_connect() as connection:
        cursor = connection.execute(query, params)
        connection.commit()
        return cursor.lastrowid


def register_user(user_id, user_name, is_admin=0):
    execute_query(
        'INSERT OR REPLACE INTO Users (id, name, is_admin) VALUES (?, ?, ?)',
        (user_id, user_name, is_admin),
    )
    keyboard = types.InlineKeyboardMarkup()
    btn_main_menu = types.InlineKeyboardButton(text="Continue", callback_data='main_menu')
    keyboard.add(btn_main_menu)
    bot.send_message(user_id, f'Authorization successful', reply_markup=keyboard)

def access_check(call, delete_msg=True):
    if type(call) == types.Message:
        message = call
        if delete_msg: bot.delete_message(message.chat.id, message.message_id)
        user_data = fetch_one('SELECT is_admin FROM Users WHERE id = ?', (message.chat.id,)) # returns (id, name, real_time, is_admin)
        is_user = bool(user_data)
        if is_user: is_admin = bool(user_data[0])
        else: is_admin = False
        return (is_user, is_admin)

    elif type(call) == types.CallbackQuery:
        if delete_msg: bot.delete_message(call.message.chat.id, call.message.message_id)
        user_data = fetch_one('SELECT is_admin FROM Users WHERE id = ?', (call.message.chat.id,)) # returns (id, name, real_time, is_admin)
        is_user = bool(user_data)
        if is_user: is_admin = bool(user_data[0])
        else: is_admin = False
        return (is_user, is_admin)        

def update_query(query, q_id):
    query_data = fetch_one('SELECT query FROM Tmp WHERE rowid = ?', (q_id,))
    if not query_data:
        execute_query('INSERT OR REPLACE INTO Tmp (query, rowid) VALUES (?, ?)', (query, q_id))
    else:
        old_query = query_data[0]
        execute_query(
            'INSERT OR REPLACE INTO Tmp (query, rowid) VALUES (?, ?)',
            (f'{old_query}|{query}', q_id),
        )

def clear_query(q_id):
    execute_query('DELETE FROM Tmp WHERE rowid = ?', (q_id,))

def compar_tab_excel_create(models_list):
    try:
        if not models_list:
            return False
        placeholders = ", ".join(["?"] * len(models_list))
        with db_connect() as connection:
            sql_query_df = pd.read_sql_query(
                f'SELECT model, part, process, time_spent FROM Reports WHERE model IN ({placeholders})',
                connection,
                params=models_list,
            )

        for model in models_list:
            sql_query_df[model] = sql_query_df.apply(lambda x: x['time_spent'] if x['model'] == model else 0, axis=1)
        sql_query_df.drop('model', inplace=True, axis=1)
        sql_query_df.drop('time_spent', inplace=True, axis=1)

        sql_query_grouped = sql_query_df.groupby(['part', 'process']).agg('sum')


        sql_query_T = sql_query_grouped.T

        for part in sql_query_grouped.index.levels[0]:
            sql_query_T[(part, 'Total')] = sql_query_T[part].T.agg('sum')

        sql_query_grouped = sql_query_T.T

        mean_col_grouped = sql_query_grouped.T.agg(lambda x: np.mean([n for n in x if n!=0]))
        sql_query_grouped['mean'] = mean_col_grouped
        sql_query_grouped = sql_query_grouped.groupby(['part', 'process']).agg(lambda x: '{:02d}:{:02d}'.format(*np.divmod(x.sum().round(0).astype(int), 60)) if x.sum() != 0 else "-")
        sql_query_grouped.to_excel("comparison.xlsx", index=False, sheet_name="Comp")
        
        with pd.ExcelWriter(
                            "comparison.xlsx",
                            mode="a",
                            engine="openpyxl",
                            if_sheet_exists="replace",
                        ) as writer:

            sql_query_grouped.to_excel(writer, sheet_name="Comp")
        
        return True
    except: return False

def sql_to_excel(sql_query_df):
    if sql_query_df.empty: return False

    else:

        model_sum_time = sql_query_df.groupby(['model']).agg(time=('time_spent', lambda x: '{:02d}:{:02d}'.format(*np.divmod(x.sum().round(0).astype(int), 60))))
        sql_out_piano_wst = sql_query_df.copy()

        person_sum_time = sql_query_df.groupby(['name']).agg(time=('time_spent', lambda x: '{:02d}:{:02d}'.format(*np.divmod(x.sum().round(0).astype(int), 60))))
        sql_out_person_wst = sql_query_df.copy()

        piano_stat_df = sql_out_piano_wst.groupby(['model', 'part', 'process', 'name', 'report_date']).agg(
                                                                            time=('time_spent', lambda x: '{:02d}:{:02d}'.format(*np.divmod(x.sum().round(0).astype(int), 60))),
                                                                            date=('report_date', lambda x: pd.to_datetime(pd.Series([x.max()]), format= '%Y%m%d').dt.date)                                                                       
                                                                            )
        person_stat_df = sql_out_person_wst.groupby(['name', 'model', 'part', 'process', 'report_date']).agg(
                                                                        time=('time_spent', lambda x: '{:02d}:{:02d}'.format(*np.divmod(x.sum().round(0).astype(int), 60))),
                                                                        date=('report_date', lambda x: pd.to_datetime(pd.Series([x.max()]), format= '%Y%m%d').dt.date)                                                                       
                                                                        )
        
        #print(piano_stat_df)
        piano_stat_df.fillna(0)


        sql_query_df['report_date'] = pd.to_datetime(sql_query_df['report_date'], format= '%Y%m%d').dt.date
        sql_query_df['time_spent'] = sql_query_df['time_spent'].apply(lambda x: '{:02d}:{:02d}'.format(*divmod(x, 60)))
        try:
            sql_query_df.to_excel("reports.xlsx", index=False, sheet_name="Reports")
        except: return False


        try:
            with pd.ExcelWriter(
                    "reports.xlsx",
                    mode="a",
                    engine="openpyxl",
                    if_sheet_exists="replace",
                ) as writer:

                thin_border = Border(left=Side(style='thin'),
                     right=Side(style='thin'),
                     top=Side(style='thin'),
                     bottom=Side(style='thin'))

                piano_stat_df.to_excel(writer, sheet_name="By Piano")
                person_stat_df.to_excel(writer, sheet_name="By Person")
                s1 = writer.sheets['Reports']
                s2 = writer.sheets['By Piano']
                s3 = writer.sheets['By Person']

                s1['G1'] = 'report id'
                s1['F1'] = 'report date'
                s1['E1'] = 'time'
                s1.column_dimensions['A'].width = 20
                s1.column_dimensions['B'].width = 12
                s1.column_dimensions['C'].width = 12   
                s1.column_dimensions['D'].width = 15
                s1.column_dimensions['F'].width = 11

                s2.delete_cols(5, 1)
                s2.column_dimensions['B'].width = 13
                s2.column_dimensions['C'].width = 16
                s2.column_dimensions['D'].width = 20
                s2.column_dimensions['F'].width = 11
                s2['G1'] = 'sum of time'
                s2['G1'].border = thin_border
                s2['G1'].font = Font(bold=True)
                smi=0  
                for cell in s2['C']: cell.alignment = openpyxl.styles.Alignment(wrap_text = True, vertical='top', horizontal="center")
                for cell in s2['A']: 
                    cell.alignment = openpyxl.styles.Alignment(wrap_text = True, vertical='top', horizontal="center")
                    if (type(cell) == type(s2['A1'])) and cell != s2['A1']:
                        s2[f'G{cell.row}'] = model_sum_time.iloc[smi].values[0]
                        s2[f'G{cell.row}'].border = thin_border
                        s2[f'G{cell.row}'].font = Font(bold=True)
                        smi+=1
                        
                s3.delete_cols(5, 1)
                s3.column_dimensions['A'].width = 20
                s3.column_dimensions['C'].width = 13
                s3.column_dimensions['D'].width = 16
                s3.column_dimensions['F'].width = 11
                s3.column_dimensions['G'].width = 11
                s3['G1'] = 'sum of time'
                s3['G1'].border = thin_border
                s3['G1'].font = Font(bold=True)
                sti=0
                for cell in s3['D']: cell.alignment = openpyxl.styles.Alignment(wrap_text = True, vertical='top', horizontal="center")
                for cell in s3['A']: 
                    cell.alignment = openpyxl.styles.Alignment(wrap_text = True, vertical='top', horizontal="center")
                    if (type(cell) == type(s3['A1'])) and cell != s3['A1']:
                        s3[f'G{cell.row}'] = person_sum_time.iloc[sti].values[0]
                        s3[f'G{cell.row}'].border = thin_border
                        s3[f'G{cell.row}'].font = Font(bold=True)
                        sti+=1


                return True
        except: return False  

@bot.message_handler(commands=['id']) # незаметная фича на случай, если вам понадобится узнать свой id, напишите боту /id ( команда работает у всех, даже у тех, кого нет в базе )
def send_id(message: types.Message):
    bot.send_message(chat_id=message.chat.id, text=f'Your id: `{message.chat.id}`', parse_mode='MARKDOWN')

@bot.message_handler(func=lambda message: message.text == "reset administrator" and message.chat.id == auth_dict['admin_id']) # команда для восстановления администратора, пишется без / в начале, как другие команды, чтобы скрыть от пользователей
def reset_admin(message: types.Message):                                         # просто напишите в чат боту "reset administrator" без кавычек с аккаунта администратора и права для администратора, указанного в auth.json восстановятся

    admin_name = auth_dict['admin_name'] # имя первого админа, которое занесётся в общую БД, меняется в файле auth.json ( записывается в кавычках )
    admin_id = auth_dict['admin_id'] # tg id первого админа, меняется в файле auth.json ( число без кавычек )
    register_user(admin_id, admin_name, 1)


    bot.send_message(chat_id=admin_id, text="The administrator's authority has been restored", reply_markup=inline_keyboards('to_home')) #уведомление отправляется не написавшему команду, а восстановленному администратору

# все виды расположения кнопок в меню, чтобы потом их вызывать в зависимости от меню
def inline_keyboards(section = None, is_admin = False):
    keyboard = types.InlineKeyboardMarkup()
    btn_main_menu = types.InlineKeyboardButton(text="Home",
                                                     callback_data='main_menu')
    btn_who_works = types.InlineKeyboardButton(text="Who works now",
                                                     callback_data='who_works')
    btn_reports = types.InlineKeyboardButton(text="Reports",
                                                     callback_data='reports')
    btn_hr_manage = types.InlineKeyboardButton(text="HR management",
                                                     callback_data='hr_management')
    btn_backup_menu = types.InlineKeyboardButton(text="Backup .DB",
                                                     callback_data='backup_menu')
    btn_change_mode_on_work = types.InlineKeyboardButton(text="User mode",
                                                     callback_data='change_mode_on_work')
    btn_start_new_task = types.InlineKeyboardButton(text="Start a new task",
                                                     callback_data='0|0|0||user_rows_list')
    btn_continiue_task = types.InlineKeyboardButton(text="Continue the task",
                                                     callback_data='continue_task')
    btn_change_mode_on_admin = types.InlineKeyboardButton(text="Admin mode",
                                                     callback_data='change_mode_on_admin')
    btn_show_personal_list = types.InlineKeyboardButton(text="List of employees",
                                                     callback_data='0|personal_list')
    btn_add_user = types.InlineKeyboardButton(text="Add user by ID",
                                                     callback_data='add_user')
    btn_download_reports_for_period = types.InlineKeyboardButton(text="For period download reports",
                                                     callback_data='dload_period')
    btn_download_reports_by_user = types.InlineKeyboardButton(text="For user download reports",
                                                     callback_data='dload_user')
    btn_download_reports_by_user_for_period = types.InlineKeyboardButton(text="For user and period download reports",
                                                     callback_data='dload_user_period')
    btn_download_all_reports = types.InlineKeyboardButton(text="Download all reports",
                                                     callback_data='dload_all_reports')
    btn_compar_tab = types.InlineKeyboardButton(text="Comparison table",
                                                     callback_data=f'|0|0|compar_menu')

    if section == "to_home":
        keyboard.add(btn_main_menu)

    if section == "admin_menu":
        keyboard.add(btn_who_works, btn_reports)
        keyboard.add(btn_hr_manage, btn_backup_menu)
        keyboard.add(btn_change_mode_on_work)

    if section == "user_menu":
        keyboard.add(btn_start_new_task, btn_continiue_task)
        if is_admin: keyboard.add(btn_change_mode_on_admin)

    if section == "hr_management":
        keyboard.add(btn_show_personal_list)
        keyboard.add(btn_add_user)
        keyboard.add(btn_main_menu)

    if section == "dload_reports_menu":
        keyboard.add(btn_download_reports_for_period)
        keyboard.add(btn_download_reports_by_user)
        keyboard.add(btn_download_reports_by_user_for_period)
        keyboard.add(btn_download_all_reports)
        keyboard.add(btn_compar_tab)
        keyboard.add(btn_reports, btn_main_menu)      

    return keyboard

@bot.callback_query_handler(func=lambda call: call.data == 'main_menu')
def redirect_to_home(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    welcome(call.message)

@bot.message_handler(commands=['start'])
def welcome(message: types.Message):
    user_data = fetch_one('SELECT * FROM Users WHERE id = ?', (message.chat.id,)) # поиск пользователя по базе данных для дальнейшего определения
    
    if not user_data: #если пользователь не найден в базе

            reply_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            button_restart = types.KeyboardButton(text="/start")
            reply_keyboard.add(button_restart)
            bot.send_message(chat_id=message.chat.id, text=f'Welcome. You are not logged in.\nYour id: `{message.chat.id}` \nTo continue, please provide your id to the administrator.', reply_markup=reply_keyboard, parse_mode='MARKDOWN')


    elif user_data[3]: admin_session(message) # если is_admin == True // админ панель
    
    elif not user_data[3]: user_session(message) # если это обычный сотрудник


from admin_handlers import create_admin_session
from user_handlers import create_user_session

session_refs = {}

admin_session = create_admin_session(
    bot=bot,
    register_user=register_user,
    access_check=access_check,
    inline_keyboards=inline_keyboards,
    sql_to_excel=sql_to_excel,
    compar_tab_excel_create=compar_tab_excel_create,
    update_query=update_query,
    clear_query=clear_query,
    db_connect=db_connect,
    fetch_one=fetch_one,
    fetch_all=fetch_all,
    execute_query=execute_query,
    get_user_session=lambda: session_refs["user"],
)

user_session = create_user_session(
    bot=bot,
    access_check=access_check,
    inline_keyboards=inline_keyboards,
    update_query=update_query,
    clear_query=clear_query,
    fetch_one=fetch_one,
    fetch_all=fetch_all,
    execute_query=execute_query,
    execute_insert=execute_insert,
    get_admin_session=lambda: session_refs["admin"],
)

session_refs["admin"] = admin_session
session_refs["user"] = user_session

bot.infinity_polling(skip_pending=True)
