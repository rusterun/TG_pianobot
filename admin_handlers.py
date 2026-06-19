import datetime
import sqlite3

import pandas as pd
from telebot import types


def create_admin_session(
    bot,
    register_user,
    access_check,
    inline_keyboards,
    sql_to_excel,
    compar_tab_excel_create,
    update_query,
    clear_query,
    db_connect,
    fetch_one,
    fetch_all,
    execute_query,
    get_user_session,
):
    def admin_session(message: types.Message): #интерфейс администратора
        def parse_period(raw_text):
            dates = raw_text.replace(" ", "").split("-")
            if len(dates) != 2:
                return None
            try:
                parsed = [datetime.datetime.strptime(d, "%d.%m.%Y") for d in dates]
            except ValueError:
                return None
            return [dt.strftime("%Y%m%d") for dt in parsed]

        bot.send_message(message.chat.id, 'Main menu (admin mode)', reply_markup=inline_keyboards('admin_menu'))

        @bot.callback_query_handler(func=lambda call: call.data == 'change_mode_on_work')
        def change_mode_on_user(call):
            if access_check(call)[1]:
                get_user_session()(call.message)

        @bot.callback_query_handler(func=lambda call: call.data == 'who_works')
        def who_works(call):
            if access_check(call)[1]:
                user_data = fetch_all('SELECT name, real_time FROM Users WHERE real_time != ""')
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
                user_data = fetch_all('SELECT * FROM Users ORDER BY name') # returns [(id, name, real_time, is_admin), ..., (id, name, real_time, is_admin)]

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
                execute_query('UPDATE Users SET is_admin = ? WHERE id = ?', (change_on, user_id))
                bot.send_message(call.message.chat.id, f'Status is changed', reply_markup=inline_keyboards('hr_management'))

        @bot.callback_query_handler(func=lambda call: 'fire_user_by_id' in call.data)
        def fire_user_by_id(call):
            if access_check(call)[1]:
                user_id = call.data.split('|')[0]
                execute_query('DELETE FROM Users WHERE id = ?', (user_id,))
                bot.send_message(call.message.chat.id, f'The employee is fired', reply_markup=inline_keyboards('hr_management'))

        @bot.callback_query_handler(func=lambda call: 'user_edit_by_id' in call.data)
        def user_by_id_info(call):
            if access_check(call)[1]:
                user_id = int(call.data.split("|")[0])
                user_data = fetch_one('SELECT * FROM Users WHERE id = ?', (user_id,)) # returns (id, name, real_time, is_admin)
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
                reports_data = fetch_all('SELECT * FROM Reports ORDER BY ROWID DESC LIMIT 15')
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
                report_data = fetch_one('SELECT * FROM Reports WHERE rowid = ?', (report_id,))        
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
                report_data = fetch_one('SELECT * FROM Reports WHERE rowid = ?', (report_id,))
                if tabcode == 5:
                    value_dt = datetime.datetime.strptime(str(report_data[5]),"%Y%m%d")
                    value = datetime.datetime.strftime(value_dt,"%d.%m.%Y")
                else: value = report_data[tabcode]
                bot.send_message(call.message.chat.id, f'Send new value.\nCurrent value: {value}')
                bot.register_next_step_handler(call.message, update_report, report_id, tabcode)            

        def update_report(message, report_id, tabcode):
            value = message.text

            key = ['name', 'model', 'part', 'process', 'time_spent', 'report_date'][tabcode]
            if tabcode == 4: 
                if value.isdigit():
                    execute_query(f'UPDATE Reports SET {key} = ? WHERE rowid = ?', (value, report_id))
                else: bot.send_message(message.chat.id, 'Invalid format')
            elif tabcode == 5:
                date = value.replace(" ", "")
                try:
                    value_dt = datetime.datetime.strptime(date,"%d.%m.%Y")
                    value = datetime.datetime.strftime(value_dt,"%Y%m%d")
                    execute_query(f'UPDATE Reports SET {key} = ? WHERE rowid = ?', (value, report_id))
                except ValueError as err:
                    bot.send_message(message.chat.id, 'Invalid format')
            else:
                execute_query(f'UPDATE Reports SET {key} = ? WHERE rowid = ?', (value, report_id))
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
            format_dates = parse_period(message.text)
            if not format_dates:
                bot.send_message(message.chat.id, f'Invalid date format. Date must be in the format dd.mm.yyyy - dd.mm.yyyy', reply_markup=inline_keyboards("dload_reports_menu"))
            else:
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
            format_dates = parse_period(message.text)
            if not format_dates:
                bot.send_message(message.chat.id, f'Invalid date format. The date must be in the dd.mm.yyyy - dd.mm.yyyy format, for example, 19.09.2025 - 19.10.2025', reply_markup=inline_keyboards("dload_reports_menu")) 
            else:
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
                if sorted_by_name: models_data = fetch_all('SELECT * FROM TabModels ORDER BY name') # returns [(id, name, date), ..., (id, name, date)]
                else: models_data = fetch_all('SELECT * FROM TabModels ORDER BY date DESC')

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

                comp_query_data = fetch_one('SELECT query FROM Tmp WHERE rowid = 1')
                if comp_query_data: old_query = comp_query_data[0]
                else: old_query = ""
                bot.send_message(call.message.chat.id, f'Page {page+1}\nSelected: {old_query}', reply_markup=keyboard)

        @bot.callback_query_handler(func=lambda call: 'redirect_to_create_compare' in call.data)
        def dload_compar_tab(call):
            if access_check(call)[1]:
                comp_query_data = fetch_one('SELECT query FROM Tmp WHERE rowid = 1')
                if comp_query_data: old_query = comp_query_data[0]
                models_list = old_query.split('|')
                clear_query(1)
                if compar_tab_excel_create(models_list):
                    with open('comparison.xlsx', 'rb') as file:
                        bot.send_document(call.message.chat.id, file, reply_markup=inline_keyboards("dload_reports_menu"))
                else: bot.send_message(call.message.chat.id, f'Something went wrong', reply_markup=inline_keyboards("dload_reports_menu"))

        @bot.callback_query_handler(func=lambda call: call.data == 'backup_menu')
        def backup_db_menu(call):
            if access_check(call)[1]:
                bot.send_message(call.message.chat.id, 'Database management', reply_markup=inline_keyboards("backup_menu"))

        @bot.callback_query_handler(func=lambda call: call.data == 'download_backup_db')
        def dload_backup_db(call):
            if access_check(call)[1]:
                with open('database.db', 'rb') as file:
                    bot.send_document(call.message.chat.id, file, reply_markup=inline_keyboards("backup_menu"))

        @bot.callback_query_handler(func=lambda call: call.data == 'reset_db_request')
        def reset_db_request(call):
            if access_check(call)[1]:
                keyboard = types.InlineKeyboardMarkup()
                btn_confirm = types.InlineKeyboardButton(text="Confirm reset", callback_data='reset_db_confirm')
                btn_cancel = types.InlineKeyboardButton(text="Cancel", callback_data='backup_menu')
                keyboard.add(btn_confirm)
                keyboard.add(btn_cancel)
                bot.send_message(
                    call.message.chat.id,
                    'This will delete all reports, active tasks, directories, temporary selections and rates. '
                    'The current administrator account will be kept. Continue?',
                    reply_markup=keyboard,
                )

        @bot.callback_query_handler(func=lambda call: call.data == 'reset_db_confirm')
        def reset_db_confirm(call):
            if access_check(call)[1]:
                admin_id = call.message.chat.id
                admin_data = fetch_one('SELECT name FROM Users WHERE id = ?', (admin_id,))
                admin_name = admin_data[0] if admin_data else 'Administrator'
                tables_to_clear = ['Reports', 'TabWorks', 'TabModels', 'TabParts', 'TabProcesses', 'Tmp', 'Rates', 'Users']

                with db_connect() as connection:
                    cursor = connection.cursor()
                    for table_name in tables_to_clear:
                        cursor.execute(f'DELETE FROM {table_name}')
                    cursor.execute(
                        'INSERT OR REPLACE INTO Users (id, name, real_time, is_admin) VALUES (?, ?, "", 1)',
                        (admin_id, admin_name),
                    )
                    connection.commit()

                bot.send_message(call.message.chat.id, 'The database has been reset.', reply_markup=inline_keyboards("to_home"))

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
                part_name = None
                if tab_name == 'TabProcesses' and model_data[3]:
                    part_data = connection.cursor().execute('SELECT name FROM TabParts WHERE rowid = ?', (model_data[3],)).fetchone()
                    part_name = part_data[0] if part_data else None
                connection.close() 
                format_date = str(model_data[2])[6:]+"."+str(model_data[2])[5:7]+"."+str(model_data[2])[:4]
                keyboard = types.InlineKeyboardMarkup()
                btn_edit = types.InlineKeyboardButton(text="Edit", callback_data=f'{model_data[0]}|{model_data[1]}|{tab_name}|row_edit_by_id')
                btn_delete = types.InlineKeyboardButton(text="Delete", callback_data=f'{model_data[0]}|{model_data[1]}|{tab_name}|row_delete_by_id')
                btn_back = types.InlineKeyboardButton(text="Back", callback_data=f'0|0|{tab_name}|admin_rows_list')
                keyboard.add(btn_edit, btn_delete)
                keyboard.add(btn_back)
                part_info = f'\nDetail: {part_name}' if part_name else ''
                bot.send_message(call.message.chat.id, f'Name: {model_data[1]}{part_info}\nEdited: {format_date}', reply_markup=keyboard)
        
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
                tab_name = call.data.split('|')[0]
                if tab_name == 'TabProcesses':
                    parts_data = fetch_all('SELECT rowid, name FROM TabParts ORDER BY name')
                    keyboard = types.InlineKeyboardMarkup()
                    for part in parts_data:
                        keyboard.add(types.InlineKeyboardButton(text=part[1], callback_data=f'{part[0]}|process_part_select'))
                    bot.send_message(call.message.chat.id, 'Choose the detail for the process', reply_markup=keyboard)
                    return
                bot.send_message(call.message.chat.id, f'Send the new name\nTo cancel send "-"')
                bot.register_next_step_handler(call.message, add_row, tab_name)

        @bot.callback_query_handler(func=lambda call: 'process_part_select' in call.data)
        def process_part_select(call):
            if access_check(call)[1]:
                part_id = call.data.split('|')[0]
                bot.send_message(call.message.chat.id, f'Send the new process name\nTo cancel send "-"')
                bot.register_next_step_handler(call.message, add_process_row, part_id)

        def add_process_row(message, part_id):
            name = message.text
            if name == '-':
                keyboard = types.InlineKeyboardMarkup()
                btn_back = types.InlineKeyboardButton(text="Back", callback_data=f'0|0|TabProcesses|admin_rows_list')
                btn_main_menu = types.InlineKeyboardButton(text="Home", callback_data='main_menu')
                keyboard.add(btn_back)
                keyboard.add(btn_main_menu)
                bot.send_message(message.chat.id, f'Canceled', reply_markup=keyboard)
            else:
                today = str(datetime.date.today())
                format_date = ''.join(today.split('-'))
                connection = sqlite3.connect('database.db')
                connection.cursor().execute(
                    'INSERT INTO TabProcesses (name, date, part_id) VALUES (?, ?, ?)',
                    (name, format_date, part_id),
                )
                connection.commit()
                connection.close()
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton(text="Back", callback_data=f'0|0|TabProcesses|admin_rows_list'))
                bot.send_message(message.chat.id, f'"{name}" has been added.', reply_markup=keyboard)

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
    return admin_session
