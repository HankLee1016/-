from db_config import get_db_connection

try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, donor, amount, donation_date, note FROM donations ORDER BY id LIMIT 50")
    rows = cur.fetchall()
    if not rows:
        print('沒有找到任何捐款資料')
    else:
        print('找到以下捐款資料:')
        for r in rows:
            print(r)
    cur.close()
    conn.close()
except Exception as e:
    print('錯誤:', e)
