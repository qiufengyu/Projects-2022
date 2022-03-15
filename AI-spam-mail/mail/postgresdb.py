from datetime import datetime
import mysql.connector
import logging
from mail.lstm import LSTM

logger = logging.getLogger(__name__)

class PostgresDB():
    def __init__(self, host, user, password, dbname):
        self.db = mysql.connector.connect(host=host, user=user, database=dbname, password=password)
        self.cursor = self.db.cursor(buffered=True)
        self.create_user_table = """create table user_{}
                                  (
                                    id int auto_increment primary key,
                                    `from` varchar(63) not null,
                                    `to` varchar(63) not null,
                                    subject varchar(255) null,
                                    content blob null,
                                    time datetime null,
                                    status int default 0 null
                                  );
                                  """
        self.create_userfriend_table = """create table userfriend_{}
                                      (
                                        id int auto_increment primary key,
                                        friend varchar(63) not null
                                      );
                                  """
        self.select_username = """SELECT * FROM user WHERE `username` = '{}';"""
        self.insert_user = """INSERT INTO user(`username`, `nickname`, `password`) VALUES ('{}', '{}', '{}');"""
        self.select_password = """SELECT password FROM user WHERE `username` = '{}';"""
        self.select_status_count = """SELECT COUNT(id) FROM user_{} WHERE status = {}"""
        self.insert_mail = """INSERT INTO userlog(`from`, `to`, `subject`, `content`, `time`, `status`)
    VALUES ('{}', '{}', '{}', '{}', '{}', 0);"""
        self.insert_sender_mail = """INSERT INTO user_{}(`from`, `to`, `subject`, `content`, `time`, `status`)
    VALUES ('{}', '{}', '{}', '{}', '{}', 3);"""
        self.insert_receiver_mail = """INSERT INTO user_{}(`from`, `to`, `subject`, `content`, `time`, `status`)
        VALUES ('{}', '{}', '{}', '{}', '{}', '{}');"""
        self.select_user_mail_by_id = """SELECT * FROM user_{} WHERE `id` = {};"""
        self.select_new_mails = """SELECT * FROM userlog WHERE `to` = '{}' AND `status` = 0;"""
        self.update_userlog = """UPDATE userlog SET `status` = 1 WHERE `id` = {};"""
        self.update_user_mail_status = """UPDATE user_{} SET `status` = {} WHERE `id` = {};"""
        self.select_inbox = """SELECT * FROM user_{} WHERE `status` < 3 ORDER BY `time` DESC;"""
        self.select_outbox = """SELECT * FROM user_{} WHERE `status` = 3 ORDER BY `time` DESC;"""
        self.select_spambox = """SELECT * FROM user_{} WHERE `status` = 4 ORDER BY `time` DESC;"""
        self.select_deletebox = """SELECT * FROM user_{} WHERE `status` > 4 ORDER BY `time` DESC;"""
        self.delete_mail = """DELETE FROM user_{} WHERE `id` = {};"""
        self.select_userfriend = """SELECT * FROM userfriend_{};"""
        self.insert_userfriend = """INSERT INTO userfriend_{}(friend) VALUES ('{}');"""
        self.delete_userfriend = """DELETE FROM userfriend_{} WHERE `id` = {};"""
        self.lstm_model = LSTM(lr=1e-4, epochs=10, batch_size=100, nnlm='data/nnlm-zh-dim50')

    def check_user(self, username, password, nickname):
        self.cursor.execute(self.select_username.format(username))
        data = self.cursor.fetchone()
        if data is not None:
            return False
        else:
            try:
                print(self.insert_user.format(username, nickname, password))
                self.cursor.execute(self.insert_user.format(username, nickname, password))
                self.cursor.execute(self.create_user_table.format(username))
                self.cursor.execute(self.create_userfriend_table.format(username))
                self.db.commit()
            except Exception as e:
                print(e)
                self.db.rollback()
                return False
        return True

    def valid_user(self, username):
        self.cursor.execute(self.select_password.format(username))
        data = self.cursor.fetchone()
        if data and type(data) == tuple:
            return data[0]
        return None

    def get_user_mail_count(self, username, status):
        self.cursor.execute(self.select_status_count.format(username,status))
        data = self.cursor.fetchone()
        if data:
            return int(data[0])
        else:
            return 0

    def get_new_mails(self, username):
        self.cursor.execute(self.select_new_mails.format(username))
        data = self.cursor.fetchall()
        user_friend = self.get_user_friend_set(username)
        cnt = 0
        if data is not None:
            for d in data:
                cnt += 1
                self.cursor.execute(self.update_userlog.format(d[0]))
                # insert into user_username
                d_sender = str(d[1])
                d_receiver = str(d[2])
                d_subject = str(d[3]).replace("'", "''")
                d_content = str(d[4], encoding="utf-8").replace("'", "''")
                d_time = d[5]
                d_time_str = d_time.strftime("%Y-%m-%d %H:%M:%S")
                status = 1
                content_temp = d_subject + "\n" + d_content
                # 有用户好友关系，直接认为不是垃圾邮件
                # 否则使用算法进行识别
                if d_sender not in user_friend:
                    r = self.lstm_model.test_one(content_temp, saved_model='mail/lstm')
                    if r == 1:
                        status = 4
                        logger.info("Mark mail from {} at {} as spam by bayes".format(d_sender, d_time_str))
                    else:
                        logger.info("Mark mail from {} at {} as ham by bayes".format(d_sender, d_time_str))
                self.cursor.execute(self.insert_receiver_mail.format(username, d_sender, d_receiver, d_subject, d_content, d_time_str, status))
        self.db.commit()
        return cnt

    def get_user_inbox(self, username):
        self.cursor.execute(self.select_inbox.format(username))
        data = self.cursor.fetchall()
        if data:
            return data
        else:
            return None

    def send_an_mail(self, username, receiver, subject, content):
        dt = datetime.today()
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(self.select_username.format(receiver))
        r = self.cursor.fetchone()
        if r:
            self.cursor.execute(self.insert_mail.format(username, receiver, subject, content, dt_str))
            self.cursor.execute(self.insert_sender_mail.format(username, username, receiver, subject, content, dt_str))
            self.db.commit()
            return True
        else:
            return False

    def update_mail_status(self, username, mailid, status):
        a = self.cursor.execute(self.update_user_mail_status.format(username, status, mailid))
        self.db.commit()
        return True if a else False

    def get_user_outbox(self, username):
        self.cursor.execute(self.select_outbox.format(username))
        data = self.cursor.fetchall()
        if data:
            return data
        else:
            return None

    def get_user_spambox(self, username):
        self.cursor.execute(self.select_spambox.format(username))
        data = self.cursor.fetchall()
        if data:
            return data
        else:
            return None

    def get_user_deletebox(self, username):
        self.cursor.execute(self.select_deletebox.format(username))
        data = self.cursor.fetchall()
        if data:
            return data
        else:
            return None

    def delete_user_mail(self, username, mid):
        a = self.cursor.execute(self.delete_mail.format(username, mid))
        self.db.commit()
        return True if a else False

    def get_user_mail_by_id(self, username, mid):
        self.cursor.execute(self.select_user_mail_by_id.format(username, mid))
        data = self.cursor.fetchone()
        if data:
            return data
        else:
            return None

    def get_user_friend_list(self, username):
        self.cursor.execute(self.select_userfriend.format(username))
        data = self.cursor.fetchall()
        userfriend = []
        if data:
            for d in data:
                dd = {}
                dd["id"] = int(d[0])
                dd["friend"] = str(d[1])
                userfriend.append(dd)
        return userfriend

    def get_user_friend_set(self, username):
        self.cursor.execute(self.select_userfriend.format(username))
        data = self.cursor.fetchall()
        userfriendset = set()
        if data:
            for d in data:
                userfriendset.add(str(d[1]))
        return userfriendset

    def delete_user_friend(self, username, wordid):
        a = self.cursor.execute(self.delete_userfriend.format(username, wordid))
        self.db.commit()
        return True if a else False

    def insert_user_friend(self, username, word):
        a = self.cursor.execute(self.insert_userfriend.format(username, word))
        self.db.commit()
        return True if a else False
