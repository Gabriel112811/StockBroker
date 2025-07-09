import sqlite3
#Alte Testdatei
#@Fabius

connection = sqlite3.connect("StockBroker.db")
cursor = connection.cursor()
def create_table():
    cursor.execute("CREATE TABLE all_users ( username VARCHAR(32) UNIQUE,password_hash VARCHAR(64), email VARCHAR(64) UNIQUE)")

def test_db():
    res = cursor.execute("SELECT username FROM all_users")
    if(res.fetchone() == None):
        print("yesssss")


def get_all_users() -> list[dict]:
    sql_command = "SELECT username, password_hash, email, geld FROM all_users"
    keys = ["username", "password_hash", "email", "geld"]
    cursor.execute(sql_command)
    out = [{k: v for k, v in zip(keys, values)} for values in cursor.fetchall()]
    return out


def test_account():
    cursor.execute("INSERT INTO all_users VALUES ('fabius', '3bc49b73e2fb201924d9dcce5fb6d6fd7cfbf58c49be8cc46439c05dc634b151', 'fabius.werner@outlook.de')")
    cursor.execute("SELECT username FROM all_users WHERE username == 'fabius'")
    print(cursor.fetchone())
# def test_insert():
#    sql_command="""INSERT INTO all_users (username, password_hash, email) \
#                VALUES ('backend','3bc49b73','fabius.werner@outlook.de') """
#    result_print(connection.execute(sql_command))
#
# def test_execute():
#     sql_command="""SELECT username FROM all_users WHERE username='backend'"""
#     result_print(connection.execute(sql_command))
#
# def result_print(cursor:sqlite3.Cursor):
#     print(cursor.fetchall())
#
# test_execute()


# get_all()
# test_account()
# get_all()
print(get_all())
connection.commit()
connection.close()
