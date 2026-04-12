import datetime

from telebot import types


def create_user_session(
    bot,
    access_check,
    inline_keyboards,
    update_query,
    clear_query,
    fetch_one,
    fetch_all,
    execute_query,
    execute_insert,
    get_admin_session,
):
    def user_session(message: types.Message): #интерфейс работника
        
        bot.send_message(message.chat.id, 'Main menu', reply_markup=inline_keyboards('user_menu', access_check(message, delete_msg=False)[1]))
        
        @bot.callback_query_handler(func=lambda call: call.data == 'change_mode_on_admin')
        def change_mode_on_user(call):
            if access_check(call)[1]:
                get_admin_session()(call.message)

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
    return user_session
