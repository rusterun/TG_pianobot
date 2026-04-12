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
    btn_download_all_reports = types.InlineKeyboardButton(text="Doqnload all reports",
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

    connection = sqlite3.connect('database.db')
    user_data = connection.cursor().execute(f'SELECT * FROM Users WHERE id = {message.chat.id}').fetchone() # поиск пользователя по базе данных для дальнейшего определения
    connection.close()
    
    if not user_data: #если пользователь не найден в базе

            reply_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            button_restart = types.KeyboardButton(text="/start")
            reply_keyboard.add(button_restart)
            bot.send_message(chat_id=message.chat.id, text=f'Welcome. You are not logged in.\nYour id: `{message.chat.id}` \nTo continue, please provide your id to the administrator.', reply_markup=reply_keyboard, parse_mode='MARKDOWN')


    elif user_data[3]: admin_session(message) # если is_admin == True // админ панель
    
    elif not user_data[3]: user_session(message) # если это обычный сотрудник


def admin_session(message: types.Message): #интерфейс администратора

    bot.send_message(message.chat.id, 'Main menu (admin mode)', reply_markup=inline_keyboards('admin_menu'))

    @bot.callback_query_handler(func=lambda call: call.data == 'change_mode_on_work')
    def change_mode_on_user(call):
        if access_check(call)[1]:
            user_session(call.message)

    @bot.callback_query_handler(func=lambda call: call.data == 'who_works')
    def who_works(call):
        if access_check(call)[1]:
            connection = sqlite3.connect('database.db')
            user_data = connection.cursor().execute(f'SELECT name, real_time FROM Users WHERE real_time != ""').fetchall()
            connection.close()
            if user_data:
                text = ""
                for row in user_data:
                    text += f'{row[0]}: {row[1]}\n'
            else: text = "There are no running tasks"
            bot.send_message(call.message.chat.id, text, reply_markup=inline_keyboards('to_home'))


    @bot.callback_query_handler(func=lambda call: call.data == 'hr_management')
    def hr_management_menu(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, 'Staff', reply_markup=inline_keyboards('hr_management'))

    @bot.callback_query_handler(func=lambda call: call.data == 'add_user')
    def add_user(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, "Enter user's ID")
            bot.register_next_step_handler(call.message, get_id)

    def get_id(message):
        _id = message.text
        if _id.isdigit():
            bot.send_message(message.chat.id, "Enter user's name\nEnter '-' for cancel")        
            bot.register_next_step_handler(message, user_added, _id)
        else:
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="Cancel", callback_data='hr_management')
            keyboard.add(btn_back)
            bot.send_message(message.chat.id, 'The telegram ID consists only of numbers.', reply_markup=keyboard)        

    def user_added(message, _id):
        name = message.text
        if name == '-':
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="HR management", callback_data='hr_management')
            btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
            keyboard.add(btn_back)
            keyboard.add(btn_main_menu)
            bot.send_message(message.chat.id, f'Canceled', reply_markup=keyboard)               
        else:
            register_user(_id, name, 0)
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="HR management", callback_data='hr_management')
            btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
            keyboard.add(btn_back)
            keyboard.add(btn_main_menu)
            bot.send_message(message.chat.id, f'{name} has been successfully added to the system', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'personal_list' in call.data)
    def personal_list(call):
        if access_check(call)[1]:
            page=int(call.data.split('|')[0])
            keyboard = types.InlineKeyboardMarkup()
            connection = sqlite3.connect('database.db')
            user_data = connection.cursor().execute(f'SELECT * FROM Users ORDER BY name').fetchall() # returns [(id, name, real_time, is_admin), ..., (id, name, real_time, is_admin)]
            connection.close()

            if user_data:
                userlist = [ user_data[i : i + 30] for i in range(0, len(user_data), 30) ]
                num_pages = len(userlist)             
                for row in userlist[page]:
                    if call.message.chat.id != row[0]:
                        btn_name = types.InlineKeyboardButton(text=f"👨‍✈️ {row[1]}", callback_data=f'{row[0]}|user_edit_by_id') if row[3] else types.InlineKeyboardButton(text=f"👨‍🔧 {row[1]}", callback_data=f'{row[0]}|user_edit_by_id')
                        keyboard.add(btn_name)
            if page<(num_pages-1) and page>0: 
                btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|personal_list')
                btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|personal_list')
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='hr_management')
                keyboard.add(btn_prev_page, btn_back, btn_next_page)
            elif page<(num_pages-1) and page==0: 
                btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|personal_list')
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='hr_management')
                keyboard.add(btn_back, btn_next_page)
            elif page==(num_pages-1) and page>0: 
                btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|personal_list')
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='hr_management')
                keyboard.add(btn_prev_page, btn_back)
            elif page==(num_pages-1) and page==0: 
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='hr_management')
                keyboard.add(btn_back)
            bot.send_message(call.message.chat.id, f'Userlist. Page {page+1}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'change_rank_of_user' in call.data)
    def change_rank(call):
        if access_check(call)[1]:
            user_id = int(call.data.split('|')[0])
            is_admin = int(call.data.split('|')[1])
            change_on = 0 if is_admin else 1
            connection = sqlite3.connect('database.db')
            connection.cursor().execute(f'UPDATE Users SET is_admin = {change_on} WHERE id = {user_id}')
            connection.commit()
            connection.close()
            bot.send_message(call.message.chat.id, f'Status is changed', reply_markup=inline_keyboards('hr_management'))

    @bot.callback_query_handler(func=lambda call: 'fire_user_by_id' in call.data)
    def fire_user_by_id(call):
        if access_check(call)[1]:
            user_id = call.data.split('|')[0]
            connection = sqlite3.connect('database.db')
            connection.cursor().execute(f'DELETE FROM Users WHERE id = {user_id}')
            connection.commit()
            connection.close()
            bot.send_message(call.message.chat.id, f'The employee is fired', reply_markup=inline_keyboards('hr_management'))

    @bot.callback_query_handler(func=lambda call: 'user_edit_by_id' in call.data)
    def user_by_id_info(call):
        if access_check(call)[1]:
            user_id = int(call.data.split("|")[0])
            connection = sqlite3.connect('database.db')
            user_data = connection.cursor().execute(f'SELECT * FROM Users WHERE id = {user_id}').fetchone() # returns (id, name, real_time, is_admin)
            connection.close()
            user_mode = "[Administrator]" if user_data[3] else "[User]"
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='hr_management')
            btn_fire = types.InlineKeyboardButton(text=f"Fire", callback_data=f'{user_data[0]}|fire_user_by_id')
            btn_change_rank = types.InlineKeyboardButton(text=f"Make user", callback_data=f'{user_data[0]}|{user_data[3]}|change_rank_of_user') if user_data[3] else types.InlineKeyboardButton(text=f"Make admin", callback_data=f'{user_data[0]}|{user_data[3]}|change_rank_of_user')
            keyboard.add(btn_fire, btn_change_rank)
            keyboard.add(btn_back)
            bot.send_message(call.message.chat.id, f'{user_data[1]} | {user_mode}', reply_markup=keyboard)



    @bot.callback_query_handler(func=lambda call: call.data == 'reports')
    def reports_menu(call):
        if access_check(call)[1]:
            btn_to_rep_downloads = types.InlineKeyboardButton(text="Download reports", callback_data='download_reports')      
            connection = sqlite3.connect('database.db')
            reports_data = connection.cursor().execute(f'SELECT * FROM Reports ORDER BY ROWID DESC LIMIT 15').fetchall()
            connection.close()
            keyboard = types.InlineKeyboardMarkup()
            for rep_data in reports_data:
                str_date = str(rep_data[5])[6:8]+'.'+str(rep_data[5])[4:6]+'.'+str(rep_data[5])[:4]
                rep_btn = types.InlineKeyboardButton(text=f"{rep_data[0]}: {rep_data[1]} {str_date}", callback_data=f'{rep_data[6]}| report_info_by_id')
                keyboard.add(rep_btn)
            btn_find_rep_by_id = types.InlineKeyboardButton(text="Find by ID", callback_data='find_report_by_id')
            btn_settings = types.InlineKeyboardButton(text="Settings", callback_data='reports_settings')
            btn_home = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
            keyboard.add(btn_to_rep_downloads, btn_find_rep_by_id)
            keyboard.add(btn_settings)
            keyboard.add(btn_home)
            bot.send_message(call.message.chat.id, 'Reports', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data == 'find_report_by_id')
    def find_rep_by_id(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, 'Enter report ID')
            bot.register_next_step_handler(call.message, redirect_report_id_from_msg)
    
    @bot.callback_query_handler(func=lambda call: 'report_info_by_id' in call.data)
    def redirect_report_id(call):
        if access_check(call)[1]:
            report_id = call.data.split('|')[0]
            report_by_id_info(call.message, report_id)

    def redirect_report_id_from_msg(message):
        report_id = message.text
        report_by_id_info(message, report_id)
        

    def report_by_id_info(message, report_id):
        keyboard = types.InlineKeyboardMarkup()
        btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
        btn_back = types.InlineKeyboardButton(text="Reports", callback_data='reports')
        keyboard.add(btn_back, btn_main_menu)      
        if report_id.isdigit():         
            connection = sqlite3.connect('database.db')
            report_data = connection.cursor().execute(f'SELECT * FROM Reports WHERE rowid = {report_id}').fetchone()
            connection.close()        
            btn_change_name = types.InlineKeyboardButton(text="Edit name", callback_data=f'{report_id}|0|report_editing')     
            btn_change_piano = types.InlineKeyboardButton(text="Edit piano", callback_data=f'{report_id}|1|report_editing')     
            btn_change_part = types.InlineKeyboardButton(text="Edit detail", callback_data=f'{report_id}|2|report_editing')     
            btn_change_proccess = types.InlineKeyboardButton(text="Edit proccess", callback_data=f'{report_id}|3|report_editing')     
            btn_change_time = types.InlineKeyboardButton(text="Edit time", callback_data=f'{report_id}|4|report_editing')     
            btn_change_date = types.InlineKeyboardButton(text="Edit date", callback_data=f'{report_id}|5|report_editing')     
            if report_data: 
                keyboard.add(btn_change_name, btn_change_piano)   
                keyboard.add(btn_change_part, btn_change_proccess)   
                keyboard.add(btn_change_time, btn_change_date)   
                bot.send_message(message.chat.id, f'Name: {report_data[0]}\nPiano: {report_data[1]}\nDetail/Task: {report_data[2]}\nProcess: {report_data[3]}\nTime(minutes): {report_data[4]}\nDate: {str(report_data[5])[6:]}.{str(report_data[5])[4:6]}.{str(report_data[5])[:4]}\n', reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, f'Report not found', reply_markup=keyboard)
        else: 
            bot.send_message(message.chat.id, f'The report ID must be an integer without any other characters.', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'report_editing' in call.data)
    def report_editing_name(call):
        if access_check(call)[1]:
            report_id = call.data.split('|')[0]
            tabcode = int(call.data.split('|')[1])
            connection = sqlite3.connect('database.db')
            report_data = connection.cursor().execute(f'SELECT * FROM Reports WHERE rowid = {report_id}').fetchone()
            connection.close()
            if tabcode == 5:
                value_dt = datetime.datetime.strptime(str(report_data[5]),"%Y%m%d")
                value = datetime.datetime.strftime(value_dt,"%d.%m.%Y")
            else: value = report_data[tabcode]
            bot.send_message(call.message.chat.id, f'Send new value.\nCurrent value: {value}')
            bot.register_next_step_handler(call.message, update_report, report_id, tabcode)            

    def update_report(message, report_id, tabcode):
        value = message.text

        key = ['name', 'model', 'part', 'process', 'time_spent', 'report_date'][tabcode]
        connection = sqlite3.connect('database.db')
        if tabcode == 4: 
            if value.isdigit(): connection.cursor().execute(f'UPDATE Reports SET {key} = {value} WHERE rowid = {report_id}')
            else: bot.send_message(message.chat.id, 'Invalid format')
        elif tabcode == 5:
            date = value.replace(" ", "")
            try:
                value_dt = datetime.datetime.strptime(date,"%d.%m.%Y")
                value = datetime.datetime.strftime(value_dt,"%Y%m%d")
                connection.cursor().execute(f'UPDATE Reports SET {key} = {value} WHERE rowid = {report_id}')
            except ValueError as err:
                bot.send_message(message.chat.id, 'Invalid format')
        else: connection.cursor().execute(f'UPDATE Reports SET {key} = "{value}" WHERE rowid = {report_id}')         
        connection.commit()
        connection.close()
        report_by_id_info(message, report_id)     

            

    @bot.callback_query_handler(func=lambda call: call.data == 'download_reports')
    def downloading_reports_menu(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, f'Download reports menu', reply_markup=inline_keyboards("dload_reports_menu"))

    @bot.callback_query_handler(func=lambda call: call.data == 'dload_all_reports')
    def downloading_all_reports(call):
        if access_check(call)[1]:
            with db_connect() as connection:
                sql_out = pd.read_sql_query(
                    'SELECT name, model, part, process, time_spent, report_date, rowid FROM Reports',
                    connection,
                )
            if sql_to_excel(sql_out): 
                with open('reports.xlsx', 'rb') as file:
                    bot.send_document(call.message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
            else: bot.send_message(call.message.chat.id, f'There is no data on the reports or an error occurred', reply_markup=inline_keyboards("dload_reports_menu"))

    @bot.callback_query_handler(func=lambda call: call.data == 'dload_period')
    def creating_reports_by_period(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, 'Enter the period for which the general report will be generated in the format dd.mm.yyyy - dd.mm.yyyy, for example 19.09.2025 - 19.10.2025 (spaces are not important, you can do without them, the main thing is that the separator is "-")')
            bot.register_next_step_handler(call.message, download_reports_by_period)

    def download_reports_by_period(message):
        dates = message.text.replace(" ", "").split("-")
        try:
            for input_date in dates: datetime.datetime.strptime(input_date,"%d.%m.%Y")
            if len(dates) != 2: datetime.datetime.strptime('провоцирую ошибку йопта',"%d.%m.%Y")
        except ValueError as err:
            bot.send_message(message.chat.id, f'Invalid date format. Date must be in the format dd.mm.yyyy - dd.mm.yyyy', reply_markup=inline_keyboards("dload_reports_menu"))
        else:
            format_dates = [date.split(".")[-1]+date.split(".")[1]+date.split(".")[0] for date in dates]
            with db_connect() as connection:
                sql_out = pd.read_sql_query(
                    'SELECT name, model, part, process, time_spent, report_date, rowid FROM Reports WHERE report_date >= ? AND report_date <= ?',
                    connection,
                    params=(format_dates[0], format_dates[1]),
                )
            if sql_to_excel(sql_out): 
                with open('reports.xlsx', 'rb') as file:
                    bot.send_document(message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
            else: bot.send_message(message.chat.id, f'There are no reports available for the specified period.', reply_markup=inline_keyboards("dload_reports_menu"))      
    
    @bot.callback_query_handler(func=lambda call: call.data == 'dload_user')
    def creating_reports_by_user(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, 'Enter the username exactly as it appears in the database, including spaces if any, for example John Ivanov')
            bot.register_next_step_handler(call.message, download_reports_by_user)

    def download_reports_by_user(message):
        with db_connect() as connection:
            sql_out = pd.read_sql_query(
                'SELECT name, model, part, process, time_spent, report_date, rowid FROM Reports WHERE name = ?',
                connection,
                params=(message.text,),
            )
        if sql_to_excel(sql_out): 
            with open('reports.xlsx', 'rb') as file:
                bot.send_document(message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
        elif message.text == "-": bot.send_message(message.chat.id, f'Операция отменена', reply_markup=inline_keyboards("dload_reports_menu"))
        else: bot.send_message(message.chat.id, f'There are no reports for this user, or an error occurred. Please check that the name is correct and try again.', reply_markup=inline_keyboards("dload_reports_menu"))

    @bot.callback_query_handler(func=lambda call: call.data == 'dload_user_period')
    def creating_reports_by_user_period(call):
        if access_check(call)[1]:
            bot.send_message(call.message.chat.id, 'Enter the username exactly as it appears in the database, including spaces if any, for example John Ivanov')
            bot.register_next_step_handler(call.message, get_name_for_up_dload)
    
    def get_name_for_up_dload(message): #up - user/period
        username = message.text
        if username == '-':
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="Back", callback_data='download_reports')
            keyboard.add(btn_back)
            bot.send_message(message.chat.id, f'Canceled', reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, f'The search will be performed by name: {username}\nEnter the period for which you want to display the report in the format dd.mm.yyyy - dd.mm.yyyy, for example 20.09.2025 - 20.10.2025')        
            bot.register_next_step_handler(message, dload_reports_by_user_period, username)        

    def dload_reports_by_user_period(message, username):
        dates = message.text.replace(" ", "").split("-")
        try:
            for input_date in dates: datetime.datetime.strptime(input_date,"%d.%m.%Y")
            if len(dates) != 2: datetime.datetime.strptime('провоцирую ошибку йопта',"%d.%m.%Y")
        except ValueError as err:
            bot.send_message(message.chat.id, f'Invalid date format. The date must be in the dd.mm.yyyy - dd.mm.yyyy format, for example, 19.09.2025 - 19.10.2025', reply_markup=inline_keyboards("dload_reports_menu")) 
        else:
            format_dates = [date.split(".")[-1]+date.split(".")[1]+date.split(".")[0] for date in dates]          
            with db_connect() as connection:
                sql_out = pd.read_sql_query(
                    'SELECT name, model, part, process, time_spent, report_date, rowid FROM Reports WHERE report_date >= ? AND report_date <= ? AND name = ?',
                    connection,
                    params=(format_dates[0], format_dates[1], username),
                )
            if sql_to_excel(sql_out): 
                with open('reports.xlsx', 'rb') as file:
                    bot.send_document(message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
            else: bot.send_message(message.chat.id, f'There is no user reporting data for the specified period.', reply_markup=inline_keyboards("dload_reports_menu"))
                   

    @bot.callback_query_handler(func=lambda call: 'compar_menu' in call.data)
    def compar_tab_menu(call):
        if access_check(call)[1]:
            comp_query = call.data.split('|')[0]
            if comp_query: update_query(comp_query, 1)
            page=int(call.data.split('|')[1])
            sorted_by_name = int(call.data.split('|')[2])
            keyboard = types.InlineKeyboardMarkup()
            connection = sqlite3.connect('database.db')
            if sorted_by_name: models_data = connection.cursor().execute(f'SELECT * FROM TabModels ORDER BY name').fetchall() # returns [(id, name, date), ..., (id, name, date)]
            else: models_data = connection.cursor().execute(f'SELECT * FROM TabModels ORDER BY date DESC').fetchall()
            connection.close()

            if models_data:
                models_list = [ models_data[i : i + 30] for i in range(0, len(models_data), 30) ]
                num_pages = len(models_list)
                for row in models_list[page]:
                    btn_name = types.InlineKeyboardButton(text=f"{row[1]}", callback_data=f'{row[1]}|{page}|{sorted_by_name}|compar_menu')
                    keyboard.add(btn_name)
                if page<(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'|{page-1}|{sorted_by_name}|compar_menu')
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'|{page+1}|{sorted_by_name}|compar_menu')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_prev_page, btn_back, btn_next_page)
                elif page<(num_pages-1) and page==0: 
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'|{page+1}|{sorted_by_name}|compar_menu')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_back, btn_next_page)
                elif page==(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'|{page-1}|{sorted_by_name}|compar_menu')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_prev_page, btn_back)
                elif page==(num_pages-1) and page==0: 
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_back)
            btn_sort = types.InlineKeyboardButton(text="Sort by date", callback_data=f'|{page}|0|compar_menu') if sorted_by_name else types.InlineKeyboardButton(text="Sort by name", callback_data=f'|{page}|1|compar_menu')
            btn_continue = types.InlineKeyboardButton(text="Create report", callback_data=f'redirect_to_create_compare')
            keyboard.add(btn_sort)
            keyboard.add(btn_continue)

            connection = sqlite3.connect('database.db')
            comp_query_data = connection.cursor().execute(f'SELECT query FROM Tmp WHERE rowid = 1').fetchone()
            connection.close()
            if comp_query_data: old_query = comp_query_data[0]
            else: old_query = ""
            bot.send_message(call.message.chat.id, f'Page {page+1}\nSelected: {old_query}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'redirect_to_create_compare' in call.data)
    def dload_compar_tab(call):
        if access_check(call)[1]:
            connection = sqlite3.connect('database.db')
            comp_query_data = connection.cursor().execute(f'SELECT query FROM Tmp WHERE rowid = 1').fetchone()
            connection.close()
            if comp_query_data: old_query = comp_query_data[0]
            models_list = old_query.split('|')
            clear_query(1)
            if compar_tab_excel_create(models_list):
                with open('comparison.xlsx', 'rb') as file:
                    bot.send_document(message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
            else: bot.send_message(message.chat.id, f'Something went wrong', reply_markup=inline_keyboards("dload_reports_menu"))

    @bot.callback_query_handler(func=lambda call: call.data == 'backup_menu')
    def dload_backup_db(call):
        if access_check(call)[1]:
            with open('database.db', 'rb') as file:
                bot.send_document(call.message.chat.id, file, reply_markup=inline_keyboards("to_home"))

    @bot.callback_query_handler(func=lambda call: call.data == 'reports_settings')
    def report_settings_menu(call):
        if access_check(call)[1]:
            keyboard = types.InlineKeyboardMarkup()
            btn_piano_list = types.InlineKeyboardButton(text="List of pianos", callback_data='0|0|TabModels|admin_rows_list')
            btn_parts_list = types.InlineKeyboardButton(text="List of details", callback_data='0|0|TabParts|admin_rows_list')
            btn_processes_list = types.InlineKeyboardButton(text="List of processes", callback_data='0|0|TabProcesses|admin_rows_list')
            btn_reports = types.InlineKeyboardButton(text="Back", callback_data='reports')
            keyboard.add(btn_piano_list, btn_parts_list)
            keyboard.add(btn_processes_list, btn_reports)
            bot.send_message(call.message.chat.id, 'Reports. Settings.', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'admin_rows_list' in call.data)
    def rows_list_menu(call):
        if access_check(call)[1]:
            page=int(call.data.split('|')[0])
            tab_name = call.data.split('|')[2]
            sorted_by_name = int(call.data.split('|')[1])
            keyboard = types.InlineKeyboardMarkup()
            connection = sqlite3.connect('database.db')
            if sorted_by_name: models_data = connection.cursor().execute(f'SELECT * FROM {tab_name} ORDER BY name').fetchall() # returns [(id, name, date), ..., (id, name, date)]
            else: models_data = connection.cursor().execute(f'SELECT * FROM {tab_name} ORDER BY date DESC').fetchall()
            connection.close()

            if models_data:
                models_list = [ models_data[i : i + 30] for i in range(0, len(models_data), 30) ]
                num_pages = len(models_list)
                for row in models_list[page]:
                    if call.message.chat.id != row[0]:
                        btn_name = types.InlineKeyboardButton(text=f"{row[1]}", callback_data=f'{row[0]}|{tab_name}|row_info_by_id')
                        keyboard.add(btn_name)
                if page<(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|{sorted_by_name}|{tab_name}|admin_rows_list')
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|{sorted_by_name}|{tab_name}|admin_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_prev_page, btn_back, btn_next_page)
                elif page<(num_pages-1) and page==0: 
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|{sorted_by_name}|{tab_name}|admin_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_back, btn_next_page)
                elif page==(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|{sorted_by_name}|{tab_name}|admin_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_prev_page, btn_back)
                elif page==(num_pages-1) and page==0: 
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                    keyboard.add(btn_back)
            else:
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='reports_settings')
                keyboard.add(btn_back)

            btn_sort = types.InlineKeyboardButton(text="Sort by date", callback_data=f'{page}|0|{tab_name}|admin_rows_list') if sorted_by_name else types.InlineKeyboardButton(text="Sort by name", callback_data=f'{page}|1|{tab_name}|admin_rows_list')
            btn_add = types.InlineKeyboardButton(text="Add", callback_data=f'{tab_name}|row_add')
            keyboard.add(btn_sort)
            keyboard.add(btn_add)
            bot.send_message(call.message.chat.id, f'Page {page+1}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'row_info_by_id' in call.data)
    def row_info_by_id(call):
        if access_check(call)[1]:
            model_id = int(call.data.split('|')[0])
            tab_name = call.data.split('|')[1]
            connection = sqlite3.connect('database.db')
            model_data = connection.cursor().execute(f'SELECT * FROM {tab_name} WHERE rowid = {model_id}').fetchone() #(id, name, date)
            connection.close() 
            format_date = str(model_data[2])[6:]+"."+str(model_data[2])[5:7]+"."+str(model_data[2])[:4]
            keyboard = types.InlineKeyboardMarkup()
            btn_edit = types.InlineKeyboardButton(text="Edit", callback_data=f'{model_data[0]}|{model_data[1]}|{tab_name}|row_edit_by_id')
            btn_delete = types.InlineKeyboardButton(text="Delete", callback_data=f'{model_data[0]}|{model_data[1]}|{tab_name}|row_delete_by_id')
            btn_back = types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list')
            keyboard.add(btn_edit, btn_delete)
            keyboard.add(btn_back)
            bot.send_message(call.message.chat.id, f'Name: {model_data[1]}\nEdited: {format_date}', reply_markup=keyboard)
    
    @bot.callback_query_handler(func=lambda call: 'row_delete_by_id' in call.data)
    def row_delete_by_id(call):
        if access_check(call)[1]:
            model_id = int(call.data.split('|')[0])
            model_name = call.data.split('|')[1]
            tab_name = call.data.split('|')[2]
            connection = sqlite3.connect('database.db')
            connection.cursor().execute(f'DELETE FROM {tab_name} WHERE rowid = {model_id}')
            connection.commit()
            connection.close()
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list'))                        
            bot.send_message(call.message.chat.id, f'"{model_name}" was deleted.', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'row_edit_by_id' in call.data)
    def row_edit_by_id(call):
        if access_check(call)[1]:
            model_id = int(call.data.split('|')[0])
            model_name = call.data.split('|')[1]
            tab_name = call.data.split('|')[2]
            bot.send_message(call.message.chat.id, f'Send a new name for the {model_name}\nTo cancel send "-"')
            bot.register_next_step_handler(call.message, update_row, model_id, tab_name)

    def update_row(message, model_id, tab_name):
        name = message.text
        if name == '-':
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list')
            btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
            keyboard.add(btn_back)
            keyboard.add(btn_main_menu)
            bot.send_message(message.chat.id, f'Canceled', reply_markup=keyboard)
        else:
            today = str(datetime.date.today())
            format_date = ''.join(today.split('-'))
            connection = sqlite3.connect('database.db')
            connection.cursor().execute(f'UPDATE {tab_name} SET name = "{name}", date = {format_date} WHERE rowid = {model_id}')
            connection.commit()
            connection.close()
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list')) 
            bot.send_message(message.chat.id, f'The name has been changed to "{name}"', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'row_add' in call.data)
    def model_add_menu(call):
        if access_check(call)[1]:
            tab_name = tab_name = call.data.split('|')[0]
            bot.send_message(call.message.chat.id, f'Send the new name\nTo cancel send "-"')
            bot.register_next_step_handler(call.message, add_row, tab_name)

    def add_row(message, tab_name):
        name = message.text
        if name == '-':
            keyboard = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list')
            btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
            keyboard.add(btn_back)
            keyboard.add(btn_main_menu)
            bot.send_message(message.chat.id, f'Canceled', reply_markup=keyboard)
        else:
            today = str(datetime.date.today())
            format_date = ''.join(today.split('-'))
            connection = sqlite3.connect('database.db')
            connection.cursor().execute(f'INSERT INTO {tab_name} (name, date) VALUES ("{name}", {format_date})')
            connection.commit()
            connection.close()
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list'))
            bot.send_message(message.chat.id, f'"{name}" has been added.', reply_markup=keyboard)


def user_session(message: types.Message): #интерфейс работника
    
    bot.send_message(message.chat.id, 'Main menu', reply_markup=inline_keyboards('user_menu', access_check(message, delete_msg=False)[1]))
    
    @bot.callback_query_handler(func=lambda call: call.data == 'change_mode_on_admin')
    def change_mode_on_user(call):
        if access_check(call)[1]:
            admin_session(call.message)

    @bot.callback_query_handler(func=lambda call: 'user_rows_list' in call.data)
    def rows_list_menu(call):
        if access_check(call)[0]:
            tabnames = ["TabModels", "TabParts", "TabProcesses"]
            user_messages = ["Choose what you're going to work on", "Choose the detail", "Choose the type of work"]
            user_id = call.message.chat.id
            page=int(call.data.split('|')[0])
            sorted_by_name = int(call.data.split('|')[1])
            stage = int(call.data.split('|')[2])
            query = call.data.split('|')[3]
            tab_name = tabnames[stage]
            user_message = user_messages[stage]
            keyboard = types.InlineKeyboardMarkup()
            connection = sqlite3.connect('database.db')
            if sorted_by_name: models_data = connection.cursor().execute(f'SELECT * FROM {tab_name} ORDER BY name').fetchall() # returns [(id, name, date), ..., (id, name, date)]
            else: models_data = connection.cursor().execute(f'SELECT * FROM {tab_name} ORDER BY date DESC').fetchall()
            connection.close()

            if stage == 0: clear_query(user_id)
            if query: update_query(query, user_id)                                               

            if models_data:
                models_list = [ models_data[i : i + 30] for i in range(0, len(models_data), 30) ]
                num_pages = len(models_list)
                for row in models_list[page]:
                    if stage < 2:
                        btn_name = types.InlineKeyboardButton(text=f"{row[1]}", callback_data=f'0|{sorted_by_name}|{stage+1}|{row[1]}|user_rows_list')
                    else:
                        btn_name = types.InlineKeyboardButton(text=f"{row[1]}", callback_data=f'{row[1]}|send_query_new_work')
                    keyboard.add(btn_name)
                if page<(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|{sorted_by_name}|{stage}||user_rows_list')
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|{sorted_by_name}|{stage}||user_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='main_menu')
                    keyboard.add(btn_prev_page, btn_back, btn_next_page)
                elif page<(num_pages-1) and page==0: 
                    btn_next_page = types.InlineKeyboardButton(text=f"➡️", callback_data=f'{page+1}|{sorted_by_name}|{stage}||user_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data='main_menu')
                    keyboard.add(btn_back, btn_next_page)
                elif page==(num_pages-1) and page>0: 
                    btn_prev_page = types.InlineKeyboardButton(text=f"⬅️", callback_data=f'{page-1}|{sorted_by_name}|{stage}||user_rows_list')
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data=f'main_menu')
                    keyboard.add(btn_prev_page, btn_back)
                elif page==(num_pages-1) and page==0: 
                    btn_back = types.InlineKeyboardButton(text=f"Back", callback_data=f'main_menu')
                    keyboard.add(btn_back)
            else:
                btn_back = types.InlineKeyboardButton(text=f"Back", callback_data=f'main_menu')
                keyboard.add(btn_back)                
            btn_sort = types.InlineKeyboardButton(text="Sort by date", callback_data=f'{page}|0|{stage}||user_rows_list') if sorted_by_name else types.InlineKeyboardButton(text="Sort by name", callback_data=f'{page}|1|{stage}||user_rows_list')
            keyboard.add(btn_sort)
            if stage == 0:
                btn_other = types.InlineKeyboardButton(text="Other", callback_data=f'pick_other_work')           
                keyboard.add(btn_other)

            bot.send_message(call.message.chat.id, f'{user_message}\nСтраница {page+1}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data == 'pick_other_work')
    def other_work(call):
        if access_check(call)[0]:
            bot.send_message(call.message.chat.id, 'Write the task name')
            bot.register_next_step_handler(call.message, get_workname)

    def get_workname(message):
        query = f'Other|{message.text}'
        update_query(query, message.chat.id)
        bot.send_message(message.chat.id, 'Write a comment / task description')
        bot.register_next_step_handler(message, get_comment)

    def get_comment(message):
        update_query(message.text, message.chat.id)
        keyboard = types.InlineKeyboardMarkup()
        btn_ok = types.InlineKeyboardButton(text="ok", callback_data=f'|send_query_new_work')           
        keyboard.add(btn_ok)        
        bot.send_message(message.chat.id, 'OK', reply_markup=keyboard)    

    @bot.callback_query_handler(func=lambda call: 'send_query_new_work' in call.data)
    def send_new_work(call):
        if access_check(call)[0]:
            if call.data.split('|')[0]: update_query(call.data.split('|')[0], call.message.chat.id)
            user_data = fetch_one('SELECT name FROM Users WHERE id = ?', (call.message.chat.id,))
            name = user_data[0]
            start_time = int(datetime.datetime.now().timestamp())
            main_query = fetch_one('SELECT query FROM Tmp WHERE rowid = ?', (call.message.chat.id,))[0].split('|')
            query_tuple = tuple([name] + main_query + [start_time, call.message.chat.id])
            work_id = execute_insert(
                'INSERT INTO TabWorks (name, model, part, process, last_start, user_id) VALUES (?, ?, ?, ?, ?, ?)',
                query_tuple,
            )
            execute_query(
                'UPDATE Users SET real_time = ? WHERE id = ?',
                (f'{query_tuple[1]}\n{query_tuple[2]}\n{query_tuple[3]}', call.message.chat.id),
            )
            keyboard = types.InlineKeyboardMarkup()
            btn_pause = types.InlineKeyboardButton(text=f"Pause", callback_data=f'{work_id}|pause_work')
            btn_finish = types.InlineKeyboardButton(text=f"Finish", callback_data=f'{work_id}|finish_work')
            keyboard.add(btn_pause, btn_finish)
            clear_query(call.message.chat.id)
            bot.send_message(call.message.chat.id, f'You are working on:\n{query_tuple[1]}\n{query_tuple[2]}\n{query_tuple[3]}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'pause_work' in call.data)
    def pause_work(call):
        if access_check(call)[0]:
            work_id = int(call.data.split('|')[0])
            pause_time = int(datetime.datetime.now().timestamp())
            work_data = fetch_one('SELECT last_start, time_spent FROM TabWorks WHERE rowid = ?', (work_id,))
            time_spent = (pause_time - int(work_data[0]))//60 + int(work_data[1])
            execute_query('UPDATE TabWorks SET time_spent = ? WHERE rowid = ?', (time_spent, work_id))
            execute_query('UPDATE Users SET real_time = "" WHERE id = ?', (call.message.chat.id,))
            user_session(call.message)

    @bot.callback_query_handler(func=lambda call: call.data == 'continue_task')
    def continue_work_menu(call):
        if access_check(call)[0]:
            user_id = call.message.chat.id
            keyboard = types.InlineKeyboardMarkup()
            works_data = fetch_all('SELECT * FROM TabWorks WHERE user_id = ? ORDER BY last_start DESC', (user_id,)) #(name, model, part, process, time_spent, last_start, user_id, rowid)
            btn_back = types.InlineKeyboardButton(text=f"Back", callback_data=f'main_menu')
            if works_data:
                for row in works_data:
                    btn_name = types.InlineKeyboardButton(text=f"{row[1]}, {row[3]}", callback_data=f'{row[-1]}|work_info_by_id')
                    keyboard.add(btn_name)
                keyboard.add(btn_back)
                bot.send_message(call.message.chat.id, f'List of started tasks', reply_markup=keyboard)            
            else:
                keyboard.add(btn_back)
                bot.send_message(call.message.chat.id, f'No data on started tasks', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'work_info_by_id' in call.data)
    def continue_work_by_id(call):
        if access_check(call)[0]:
            work_id = int(call.data.split('|')[0])
            start_time = int(datetime.datetime.now().timestamp())
            execute_query('UPDATE TabWorks SET last_start = ? WHERE rowid = ?', (start_time, work_id))
            work_data = fetch_one('SELECT * FROM TabWorks WHERE rowid = ? ORDER BY last_start DESC', (work_id,)) #(name, model, part, process, time_spent, last_start, user_id, rowid)
            execute_query(
                'UPDATE Users SET real_time = ? WHERE id = ?',
                (f'{work_data[1]}\n{work_data[2]}\n{work_data[3]}', call.message.chat.id),
            )
            keyboard = types.InlineKeyboardMarkup()
            btn_pause = types.InlineKeyboardButton(text=f"Pause", callback_data=f'{work_id}|pause_work')
            btn_finish = types.InlineKeyboardButton(text=f"Finish", callback_data=f'{work_id}|finish_work')
            keyboard.add(btn_pause, btn_finish)
            bot.send_message(call.message.chat.id, f'You are working on: \n{work_data[1]}\n{work_data[2]}\n{work_data[3]}', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: 'finish_work' in call.data)
    def finish_work_by_id(call):
        if access_check(call)[0]:
            work_id = int(call.data.split('|')[0])
            wd = fetch_one('SELECT * FROM TabWorks WHERE rowid = ? ORDER BY last_start DESC', (work_id,)) #(name, model, part, process, time_spent, last_start, user_id, rowid)
            execute_query('DELETE FROM TabWorks WHERE rowid = ?', (work_id,))
            today = str(datetime.date.today())
            format_date = ''.join(today.split('-'))
            time_spent = (int(datetime.datetime.now().timestamp()) - int(wd[5]))//60 + int(wd[4])
            execute_query(
                'INSERT INTO Reports (name, model, part, process, time_spent, report_date) VALUES (?, ?, ?, ?, ?, ?)',
                (wd[0], wd[1], wd[2], wd[3], time_spent, format_date),
            )
            execute_query('UPDATE Users SET real_time = "" WHERE id = ?', (call.message.chat.id,))
            user_session(call.message)                   

bot.infinity_polling(skip_pending=True)
